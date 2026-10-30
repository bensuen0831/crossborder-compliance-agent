"""Local-only delivery orchestration. All business operations use the pinned app."""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, platform, secrets, shutil, signal
import socket, subprocess, sys, tarfile, tempfile, time, urllib.parse, urllib.request, venv

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSETS, APP, RUNTIME, STATE = (ROOT / n for n in ('assets', 'app', '.runtime', '.state'))
EXPECTED = '3d322e864a6c98c34d42657289e421c77f6c9ed1'
PACKAGE_ID = 'stage1-local-20261030-1'
DOCKER = ['docker', '--host=unix:///var/run/docker.sock']

def sha(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()

def private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix('.new')
    with open(tmp, 'w', opener=lambda p, f: os.open(p, f, 0o600)) as out: json.dump(value, out, indent=2)
    os.replace(tmp, path); path.chmod(0o600)

def load(path):
    if path.is_symlink(): raise RuntimeError('SYMLINK_STATE_REFUSED')
    return json.loads(path.read_text())

def verify(*, fetch=False):
    manifest = load(ROOT / 'CHECKSUMS.json')
    downloads = load(ROOT / 'DOWNLOADS.json')['downloadable']
    missing = []
    for name, expected in manifest['files'].items():
        p = pathlib.PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts: raise RuntimeError('UNSAFE_MANIFEST_PATH')
        path = ROOT / name
        if not path.exists():
            if name not in downloads: raise RuntimeError('BUNDLED_FILE_MISSING: ' + name)
            if not fetch: missing.append(name); continue
            row = downloads[name]
            url = urllib.parse.urlsplit(row['url'])
            if url.scheme != 'https' or url.hostname not in {'files.pythonhosted.org','nodejs.org','github.com'}:
                raise RuntimeError('UNTRUSTED_DEPENDENCY_DOWNLOAD_URL')
            if row['sha256'] != expected: raise RuntimeError('DEPENDENCY_MANIFEST_MISMATCH')
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.download-', delete=False) as output:
                    temporary = pathlib.Path(output.name); count = 0
                    with urllib.request.urlopen(row['url'], timeout=60) as response:
                        while chunk := response.read(1024 * 1024):
                            count += len(chunk)
                            if count > row['bytes']: raise RuntimeError('DEPENDENCY_SIZE_OVERFLOW')
                            output.write(chunk)
                if count != row['bytes'] or sha(temporary) != expected: raise RuntimeError('DEPENDENCY_DIGEST_MISMATCH')
                os.replace(temporary, path)
            finally:
                if temporary is not None and temporary.exists(): temporary.unlink()
        if path.is_symlink() or sha(path) != expected: raise RuntimeError('PACKAGE_CHECKSUM_MISMATCH: ' + name)
    if missing:
        print(str(len(missing)) + ' fixed-hash dependencies will be downloaded by setup; existing bundled files verified.')
    else:
        print('Package payload checksums verified. This is not security or legal approval.')
    return not missing

def require_platform():
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise RuntimeError('Use Linux amd64 / Ubuntu24.04 WSL2 or an amd64 Linux VM; see START_HERE.md.')
    if sys.version_info[:2] != (3, 12): raise RuntimeError('Python3.12 is required for bundled CPython3.12 wheels.')

def python(): return str(RUNTIME / 'venv/bin/python')

def environment():
    env = dict(os.environ)
    env.update(PYTHONPATH=str(APP / 'src') + os.pathsep + str(APP), PIP_CACHE_DIR=str(RUNTIME / 'pip-cache'),
               npm_config_cache=str(RUNTIME / 'npm-cache'), PATH=str(RUNTIME / 'node/bin') + os.pathsep + env.get('PATH', ''),
               LANGGRAPH_STRICT_MSGPACK='true')
    return env

def run(command, name, *, cwd=None, env=None, interactive=False):
    logs = STATE / 'logs'; logs.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = logs / (name + '.log')
    if interactive:
        p = subprocess.run(command, cwd=cwd or APP, env=env or environment())
    else:
        with open(path, 'ab', opener=lambda p, f: os.open(p, f, 0o600)) as log:
            p = subprocess.run(command, cwd=cwd or APP, env=env or environment(), stdout=log, stderr=subprocess.STDOUT)
    if p.returncode: raise RuntimeError('STEP_FAILED: ' + name + '; private log: ' + str(path))

def git(*args): return subprocess.check_output(['git', '-C', str(APP), *args], text=True).strip()

def check_source():
    if not (APP / '.git').exists() or git('rev-parse', 'HEAD') != EXPECTED: raise RuntimeError('PRODUCT_HEAD_MISMATCH')
    if git('status', '--porcelain=v1', '--untracked-files=no'): raise RuntimeError('PRODUCT_SOURCE_MODIFIED_NO_AUTOMATIC_RESET')

def extract_files(archive, destination, prefix=None):
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as bundle:
        for item in bundle:
            p = pathlib.PurePosixPath(item.name)
            if p.is_absolute() or '..' in p.parts: raise RuntimeError('UNSAFE_RUNTIME_ARCHIVE')
            parts = p.parts[1:] if prefix else p.parts
            if prefix and (not p.parts or p.parts[0] != prefix): raise RuntimeError('RUNTIME_PREFIX_MISMATCH')
            if not parts: continue
            path = destination.joinpath(*parts)
            if item.isdir(): path.mkdir(parents=True, exist_ok=True); continue
            # Node includes symlinked npm/npx; create only those bounded, internal links.
            if item.issym():
                target = (path.parent / item.linkname).resolve()
                if not target.is_relative_to(destination.resolve()): raise RuntimeError('RUNTIME_SYMLINK_ESCAPE')
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists(): path.symlink_to(item.linkname)
                continue
            if not item.isfile(): raise RuntimeError('NONREGULAR_RUNTIME_ARCHIVE_MEMBER')
            path.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(item) as source, path.open('wb') as out: shutil.copyfileobj(source, out)
            path.chmod(item.mode & 0o755)

def docker(*args):
    env = environment()
    for name in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'): env.pop(name, None)
    return subprocess.run([*DOCKER, *args], env=env, capture_output=True, text=True)

def config():
    p = STATE / 'local.json'
    if p.exists():
        c = load(p)
        if c['package_id'] != PACKAGE_ID or c['source_sha'] != EXPECTED: raise RuntimeError('LOCAL_STATE_VERSION_MISMATCH')
        return c
    c = {'package_id': PACKAGE_ID, 'source_sha': EXPECTED, 'instance': 'stage1-local-' + secrets.token_hex(6),
         'postgres_password': secrets.token_urlsafe(36), 'postgres_port': 26544, 'redis_port': 26384,
         's3_port_offset': 400, 's3_access': secrets.token_hex(16), 's3_secret': secrets.token_urlsafe(36)}
    private(p, c); return c

def port_free(port):
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1', port)) == 0: raise RuntimeError('PORT_IN_USE_REFUSE_REPLACEMENT: ' + str(port))

def container(c, kind, *, start):
    name = c['instance'] + '-' + kind
    p = docker('container', 'inspect', name)
    if p.returncode:
        if not start: return
        port_free(c[kind + '_port'])
        lock = load(APP / 'scripts/kb01/rc1_services.lock.json')[kind]
        run([*DOCKER, 'pull', '--platform', 'linux/amd64', lock['image']], 'pull-' + kind)
        mount = '/var/lib/postgresql/data' if kind == 'postgres' else '/data'
        volume = name + '-data'
        run([*DOCKER, 'volume', 'create', '--label', 'stage1.local.delivery=' + c['instance'], volume], 'volume-' + kind)
        args = [*DOCKER, 'run', '-d', '--platform', 'linux/amd64', '--name', name, '--label', 'stage1.local.delivery=' + c['instance'],
                '-p', '127.0.0.1:' + str(c[kind + '_port']) + (':5432' if kind == 'postgres' else ':6379'),
                '--mount', 'type=volume,src=' + volume + ',dst=' + mount]
        if kind == 'postgres':
            path = STATE / 'postgres.env'
            with open(path, 'w', opener=lambda n,f: os.open(n,f,0o600)) as out:
                out.write('POSTGRES_USER=stage1\nPOSTGRES_DB=stage1_local\nPOSTGRES_PASSWORD=' + c['postgres_password'] + '\n')
            args += ['--env-file', str(path)]
        args += [lock['image']]
        if kind == 'redis': args += ['redis-server', '--appendonly', 'yes']
        run(args, 'create-' + kind); return
    d = json.loads(p.stdout)[0]
    expected = load(APP / 'scripts/kb01/rc1_services.lock.json')[kind]['config_digest']
    if d['Config'].get('Labels', {}).get('stage1.local.delivery') != c['instance'] or d['Image'] != expected:
        raise RuntimeError('CONTAINER_OWNER_OR_IMAGE_MISMATCH')
    if start and not d['State']['Running']: run([*DOCKER, 'start', name], 'resume-' + kind)
    if not start and d['State']['Running']: run([*DOCKER, 'stop', name], 'stop-' + kind)

def ticks(pid):
    try:
        fields = (pathlib.Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
        return None if fields[0] == 'Z' else fields[19]
    except FileNotFoundError: return None

def s3(c, *, start):
    root = STATE / 's3'; root.mkdir(exist_ok=True, mode=0o700)
    marker = root / 'pid.json'
    if marker.exists():
        saved = load(marker)
        if ticks(saved['pid']) == saved['start_ticks']:
            if not start:
                os.killpg(saved['pid'], signal.SIGTERM)
                for _ in range(200):
                    proc = pathlib.Path('/proc') / str(saved['pid']) / 'stat'
                    if ticks(saved['pid']) != saved['start_ticks'] or (proc.exists() and proc.read_text().rsplit(')',1)[1].split()[0] == 'Z'):
                        marker.unlink(); break
                    time.sleep(0.2)
                else: raise RuntimeError('OWN_S3_STOP_TIMEOUT_DATA_RETAINED')
            return
        marker.unlink()
    if not start: return
    offset = c['s3_port_offset']
    for p in (19333+offset, 18080+offset, 18888+offset, 19000+offset): port_free(p)
    binary = RUNTIME / 'seaweed/weed'
    if not binary.exists(): extract_files(ASSETS / 'seaweedfs-4.48-linux-amd64.tar.gz', binary.parent)
    identities = root / 'identities.json'
    private(identities, {'identities':[{'name':'local-stage1','credentials':[{'accessKey':c['s3_access'],'secretKey':c['s3_secret']}],
                                      'actions':['Admin','Read','Write','List','Tagging']}]})
    (root / 'data').mkdir(exist_ok=True)
    args = [str(binary), 'server', '-dir=' + str(root / 'data'), '-ip=127.0.0.1', '-ip.bind=127.0.0.1',
            '-master.port=' + str(19333+offset), '-master.volumeSizeLimitMB=1024', '-volume.port=' + str(18080+offset),
            '-filer.port=' + str(18888+offset), '-s3', '-s3.port=' + str(19000+offset), '-s3.port.lance=0', '-s3.port.iceberg=0',
            '-s3.config=' + str(identities), '-volume.max=40']
    with open(STATE/'logs/s3.log','ab',opener=lambda n,f:os.open(n,f,0o600)) as log:
        p = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    private(marker, {'pid':p.pid,'start_ticks':ticks(p.pid)})
    for _ in range(45):
        try:
            with urllib.request.urlopen('http://127.0.0.1:' + str(19333+offset) + '/dir/status', timeout=2) as response:
                if json.load(response)['Topology']['Max'] == 40: return
        except Exception: pass
        time.sleep(1)
    raise RuntimeError('LOCAL_S3_START_FAILED_SEE_PRIVATE_LOG')

def configure_services(c):
    root = STATE / 'services'; root.mkdir(exist_ok=True, mode=0o700)
    tool = load(ASSETS / 'tool-image.json'); tool['provenance_path'] = str(ASSETS / 'provenance.json')
    private(root / 'tool-image.json', tool)
    private(root / 'private.json', {'instance':c['instance'],'postgres_password':c['postgres_password']})
    p = urllib.parse.quote(c['postgres_password'], safe='')
    variables = {'DATABASE_URL':f'postgresql+psycopg://stage1:{p}@127.0.0.1:{c["postgres_port"]}/stage1_local',
                 'LANGGRAPH_DATABASE_URI':f'postgresql://stage1:{p}@127.0.0.1:{c["postgres_port"]}/stage1_local?sslmode=disable',
                 'REDIS_URL':f'redis://127.0.0.1:{c["redis_port"]}/0',
                 'KB01_TEST_S3_CONFIG':str(root / 's3-client.json')}
    private(root / 'services/service-evidence.json', {'variables':variables, 'scope':'LOCAL_ISOLATED_NO_LEGAL_SEED'})
    private(root / 's3-client.json', {'endpoint_url':f'http://127.0.0.1:{19000+c["s3_port_offset"]}', 'bucket':'stage1-local-storage',
                                    'access_key':c['s3_access'],'secret_key':c['s3_secret']})
    env = environment(); env.update(variables, APP_ENV='LOCAL_SERVER'); return env

def services_up(c):
    if docker('info','--format','{{.ServerVersion}}').returncode: raise RuntimeError('Local Docker socket unavailable. Start Docker/WSL integration; do not expose TCP Docker.')
    container(c, 'postgres', start=True); container(c, 'redis', start=True); s3(c, start=True)
    env = configure_services(c)
    # The readiness probe never prints its DSN or credentials.
    run([python(), '-c', 'import os,time,psycopg;\nfor i in range(60):\n try:\n  c=psycopg.connect(os.environ["LANGGRAPH_DATABASE_URI"]);c.close();break\n except Exception:\n  if i==59:raise SystemExit("OWN_POSTGRES_NOT_READY")\n  time.sleep(1)'], 'postgres-ready', env=env)
    return env

def business(action, *args, interactive=False):
    command = [python(), 'scripts/kb01/business.py', action, '--state-dir', str(STATE / 'business'),
               '--services-state', str(STATE / 'services'), *args]
    run(command, 'business-' + action, interactive=interactive)

def setup():
    require_platform(); verify(fetch=True)
    for name in ('business-backend', 'business-frontend'):
        marker = STATE / 'business' / (name + '.pid.json')
        if marker.exists():
            old = load(marker)
            if ticks(old['pid']) == old['start_ticks']:
                raise RuntimeError('STOP_OWN_SERVICES_BEFORE_SETUP')
    for binary in ('git','docker'):
        if not shutil.which(binary): raise RuntimeError('Install prerequisite: ' + binary + '; see START_HERE.md')
    STATE.mkdir(exist_ok=True,mode=0o700); STATE.chmod(0o700); (STATE/'logs').mkdir(exist_ok=True,mode=0o700)
    RUNTIME.mkdir(exist_ok=True)
    if not APP.exists():
        subprocess.run(['git','init','-q',str(APP)],check=True)
        run(['git','fetch','--no-tags',str(ASSETS/'source.bundle'),'HEAD'],'source-fetch')
        run(['git','checkout','--detach',EXPECTED],'source-checkout')
    check_source()
    if not (RUNTIME/'node/bin/node').exists(): extract_files(ASSETS/'node-v24.19.0-linux-x64.tar.xz',RUNTIME/'node',prefix='node-v24.19.0-linux-x64')
    if not pathlib.Path(python()).exists(): venv.EnvBuilder(with_pip=True).create(RUNTIME/'venv')
    print('Installing bundled exact Python dependencies into private venv…', flush=True)
    run([python(),'-m','pip','install','--no-index','--find-links',str(ASSETS/'wheels'),'-r',str(ASSETS/'requirements.lock')],'venv-install')
    run([python(),'-m','pip','install','--no-build-isolation','--no-deps','-e','.'],'app-install')
    print('Installing frontend from package-lock (first setup needs Internet)…', flush=True)
    run(['npm','ci','--prefix','frontend','--no-audit','--no-fund'],'frontend-install')
    c=config();env=services_up(c)
    if not (STATE/'setup.json').exists():
        run([python(),'-m','alembic','upgrade','head'],'migration-fresh-owned-db',env=env)
        business('init')
        private(STATE/'setup.json',{'source_sha':EXPECTED,'migration_head':'0024_kb01_import_manifest_records','initial_setup_completed':True})
    print('Setup complete. No laws/models/approvals/results seeded. Create a local account next:\n  ./START.sh account --username tester --role business')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['setup','verify','start','stop','status','account','grant-project'])
    parser.add_argument('--username');parser.add_argument('--role',choices=['business','knowledge-author','configuration-reviewer','configuration-publisher','workflow-reviewer','acceptance-expert','acceptance-publisher']);parser.add_argument('--project-id')
    a=parser.parse_args();require_platform()
    if a.action=='verify': verify();return
    if a.action=='setup': setup();return
    check_source()
    if not (STATE/'setup.json').exists():raise RuntimeError('Run ./START.sh setup first.')
    c=config()
    if a.action=='start':
        services_up(c);business('start');business('status',interactive=True)
        print('Open http://127.0.0.1:15174/intake on THIS local machine. File/real-model/legal gates remain enforced.')
    elif a.action=='stop':
        business('stop',interactive=True);s3(c,start=False);container(c,'postgres',start=False);container(c,'redis',start=False)
        print('Own services stopped. ALL data and volumes retained; no reset/delete performed.')
    elif a.action=='status':business('status',interactive=True)
    elif a.action=='account':
        if not a.username or not a.role:raise RuntimeError('--username and --role are required')
        business('account','--username',a.username,'--role',a.role,interactive=True)
    else:
        if not a.username or not a.project_id:raise RuntimeError('--username and --project-id are required')
        business('grant-project','--username',a.username,'--project-id',a.project_id,interactive=True)

if __name__=='__main__':
    try:main()
    except (Exception,KeyboardInterrupt) as e:
        # Runtime DB errors stay in private logs; no DSNs or passwords in terminal output.
        print('LOCAL_TEST_OPERATION_FAILED: '+str(e) if isinstance(e,RuntimeError) else 'LOCAL_TEST_OPERATION_FAILED: '+type(e).__name__,file=sys.stderr)
        raise SystemExit(1)
