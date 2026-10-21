import subprocess,json,pathlib,hashlib,datetime,uuid,re
from urllib.parse import quote,urlsplit
R=pathlib.Path('/workspace/kb01-g1');S='39c3581ca455df4e3ce9760ed2deab8905a5f588';image='sha256:15fbf1cb1c8349e018de488f31ec4ae366b6ecebbbced32934d0127644d787ac'
docker=['docker','--host=unix:///var/run/docker.sock']
def inspect(ref):
 fmt='{"id":{{json .Id}},"created":{{json .Created}},"os":{{json .Os}},"architecture":{{json .Architecture}},"repo_digests":{{json .RepoDigests}},"rootfs_layers":{{json .RootFS.Layers}}}'
 p=subprocess.run(docker+['image','inspect','--format',fmt,ref],capture_output=True,text=True)
 return json.loads(p.stdout) if p.returncode==0 else {'verification':'UNAVAILABLE'}
meta=inspect(image);assert meta.get('id')==image
program=r'''
import json,subprocess,pathlib,hashlib
from urllib.parse import urlsplit
fmt='${binary:Package}\t${Version}\t${Architecture}\t${source:Package}\t${source:Version}\n'
rows=subprocess.check_output(['/usr/bin/dpkg-query','-W','-f',fmt],text=True)
packages=[]
for line in rows.splitlines():
 name,version,architecture,source,source_version=line.split('\t');packages.append(dict(name=name,version=version,architecture=architecture,source_package=source,source_version=source_version))
binary={}
for name in ['/usr/bin/python3.13','/usr/bin/bsdtar','/usr/bin/clamscan','/usr/bin/freshclam','/usr/bin/sigtool','/usr/bin/pdfinfo','/usr/bin/pdftotext','/usr/bin/pdftoppm','/usr/bin/tesseract','/usr/lib/libreoffice/program/oosplash']:
 p=pathlib.Path(name);binary[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
sources=[]
for p in pathlib.Path('/etc/apt/sources.list.d').glob('*.sources'):
 stanzas=[]
 for block in p.read_text().strip().split('\n\n'):
  fields={}
  for line in block.splitlines():
   if line.startswith(('URIs:','Suites:','Components:','Signed-By:')):
    key,value=line.split(':',1)
    if key=='URIs':
     urls=[]
     for value in value.split():
      u=urlsplit(value);assert u.hostname and u.username is None and u.password is None and not u.query and not u.fragment
      urls.append(value)
     fields[key]=urls
    else:fields[key]=value.strip()
  stanzas.append(fields)
 sources.append({'file':str(p),'stanzas':stanzas,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
source_files={}
for relative in ['domain/document_text.py','domain/knowledge_paths.py','infrastructure/native_document_extraction.py','infrastructure/knowledge_native_process.py','infrastructure/knowledge_archive_process.py']:
 p=pathlib.Path('/opt/knowledge-src/crossborder_compliance')/relative;source_files[relative]=hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps({'packages':packages,'binaries':binary,'apt_sources':sources,'parser_source_files':source_files,'debian_version':pathlib.Path('/etc/debian_version').read_text().strip()}))
'''
p=subprocess.run(docker+['run','--rm','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=32','--memory=536870912','--cpus=1','--user=65534','--entrypoint=/usr/bin/python3.13',image,'-c',program],capture_output=True,text=True,timeout=60)
if p.returncode:raise RuntimeError(p.stderr[-1200:])
v=json.loads(p.stdout)
for name,h in v['parser_source_files'].items():assert hashlib.sha256(subprocess.check_output(['git','show',S+':src/crossborder_compliance/'+name])).hexdigest()==h
base=inspect('debian:trixie-slim');base_match=bool(base.get('rootfs_layers')) and meta['rootfs_layers'][:len(base['rootfs_layers'])]==base['rootfs_layers']
source_containerfile=subprocess.check_output(['git','show',S+':scripts/kb01/Containerfile'])
now=datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
identity={'product_head':S,'collected_at':now,'scope':'OBSERVED_LOCAL_G0_REVIEW_TOOL_IMAGE_NOT_EXACT_CI_IMAGE_SBOM','image':meta,'observed_local_base':base,'base_filesystem_prefix_matches':base_match,'base_manifest_builder_attestation':'NOT AVAILABLE; matching local filesystem layers do not replace an attested FROM resolution','containerfile_sha256':hashlib.sha256(source_containerfile).hexdigest(),'package_inventory':v,'published_registry_location':None,'image_retention_restore_test':'NOT EXECUTED','vulnerability_scan':'NOT EXECUTED','official_cvd_database_inventory':'Existing official Browser acceptance CVD hashes/signature verification are separately archived; ClamAV engine version is not a signature database identity.'}
(R/'toolchain_inventory.json').write_text(json.dumps(identity,indent=2))
packages=[{'name':'kb01-g0-tools','SPDXID':'SPDXRef-LocalToolImage','versionInfo':image,'downloadLocation':'NOASSERTION','filesAnalyzed':False,'licenseConcluded':'NOASSERTION','licenseDeclared':'NOASSERTION','copyrightText':'NOASSERTION','comment':'Docker config digest identifies the observed local G0 image. This is not an attested SBOM of the historical CI or a published production release.'}];relations=[{'spdxElementId':'SPDXRef-DOCUMENT','relationshipType':'DESCRIBES','relatedSpdxElement':'SPDXRef-LocalToolImage'}]
for pkg in v['packages']:
 ident='SPDXRef-Package-'+hashlib.sha256((pkg['name']+'@'+pkg['version']+':'+pkg['architecture']).encode()).hexdigest()[:24]
 purl='pkg:deb/debian/'+quote(pkg['name'].split(':')[0],safe='')+'@'+quote(pkg['version'],safe='')+'?arch='+quote(pkg['architecture'],safe='')+'&distro=debian-13'
 packages.append({'name':pkg['name'],'SPDXID':ident,'versionInfo':pkg['version'],'downloadLocation':'NOASSERTION','filesAnalyzed':False,'licenseConcluded':'NOASSERTION','licenseDeclared':'NOASSERTION','copyrightText':'NOASSERTION','sourceInfo':'Observed dpkg package: source '+pkg['source_package']+' '+pkg['source_version']+'; architecture '+pkg['architecture'],'externalRefs':[{'referenceCategory':'PACKAGE-MANAGER','referenceType':'purl','referenceLocator':purl}]})
 relations.append({'spdxElementId':'SPDXRef-LocalToolImage','relationshipType':'CONTAINS','relatedSpdxElement':ident})
bom={'spdxVersion':'SPDX-2.3','dataLicense':'CC0-1.0','SPDXID':'SPDXRef-DOCUMENT','name':'KB01-G1 observed G0 local native-tool package inventory','documentNamespace':'https://spdx.org/spdxdocs/kb01-g1-'+str(uuid.uuid5(uuid.NAMESPACE_URL,image)),'creationInfo':{'creators':['Tool: Codex-G1-dpkg-readonly-inventory'],'created':now},'comment':'Package-level inventory of observed local G0 review image only. NOASSERTION for unverified licenses/downloads. No file-complete software composition, transitive source dependency graph, exact CI binary match, CVE cleanliness, production release provenance or registry retention is asserted.','packages':packages,'relationships':relations}
(R/'local_tool_image_sbom.spdx.json').write_text(json.dumps(bom,indent=2))
print('Observed image',image,'packages',len(v['packages']),'parser source hashes match',len(v['parser_source_files']))
print('Selected versions',[(x['name'],x['version']) for x in v['packages'] if x['name'].split(':')[0] in ['python3.13','libreoffice-writer','poppler-utils','libarchive13t64','libarchive-tools','clamav','clamav-freshclam','tesseract-ocr']])
