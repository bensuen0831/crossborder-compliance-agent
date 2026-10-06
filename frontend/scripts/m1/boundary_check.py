"""Original M1 owner provenance plus current single-host invariants."""
import json
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
BASE = 'f1353372a1d8894535dc71765e3cd62597619fd5'
def git(*args): return subprocess.check_output(['git', *args], cwd=ROOT)
SOURCE = '5b1aaf5df05de458a65ead497536b323ecb16ce9'
paths = git('diff', '--name-only', BASE, SOURCE).decode().splitlines()
allowed = lambda p: p.startswith(('frontend/', 'docs/m1/', 'artifacts/m1/')) or p in ['.github/workflows/m1-alpha.yml', '.github/workflows/m0-h5-preview.yml']
checks = {
 'phase1j_base_ancestry': subprocess.run(['git', 'merge-base', '--is-ancestor', BASE, SOURCE], cwd=ROOT).returncode == 0 and subprocess.run(['git','merge-base','--is-ancestor',SOURCE,'HEAD'],cwd=ROOT).returncode == 0,
 'frontend_only_boundary': all(allowed(p) for p in paths),
 'no_backend_domain_migration_architecture_change': not git('diff', '--name-only', BASE, SOURCE, '--', 'src', 'alembic', 'ARCHITECTURE_RULES.md', 'scripts', 'tests', 'pyproject.toml').strip(),
 'package_and_lock_unchanged': all((ROOT/p).read_bytes() == git('show', BASE+':'+p) for p in ['frontend/package.json','frontend/package-lock.json']),
 'one_package_lock': all(len([p for p in (ROOT/'frontend').rglob(name) if 'node_modules' not in p.parts]) == 1 for name in ['package.json', 'package-lock.json', 'vite.config.ts']),
 'one_react_router': sum(p.read_text().count('createRoot(') for p in (ROOT/'frontend/src').rglob('*.tsx') if '.test.' not in p.name) == 1 and sum(p.read_text().count('<BrowserRouter>') for p in (ROOT/'frontend/src').rglob('*.tsx') if '.test.' not in p.name) == 1,
 'one_i18next_theme': sum(p.read_text().count('.use(initReactI18next)') for p in (ROOT/'frontend/src').rglob('*.ts') if '.test.' not in p.name) == 1,
 'one_transport': 'fetch(' not in (ROOT/'frontend/src/features/intake/api.ts').read_text(),
}
print(json.dumps({'status':'PASS' if all(checks.values()) else 'FAIL','base':BASE,'source':SOURCE,'checks':checks},indent=2))
raise SystemExit(not all(checks.values()))
