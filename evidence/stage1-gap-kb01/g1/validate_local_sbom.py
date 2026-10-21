import urllib.request,json,pathlib,hashlib
from jsonschema import Draft7Validator
R=pathlib.Path('/workspace/kb01-g1')
request=urllib.request.Request('https://api.github.com/repos/spdx/spdx-spec/commits/v2.3',headers={'Accept':'application/vnd.github+json','User-Agent':'KB01-G1-review'})
with urllib.request.urlopen(request,timeout=30) as r: commit=json.load(r)['sha']
url='https://raw.githubusercontent.com/spdx/spdx-spec/'+commit+'/schemas/spdx-schema.json'
with urllib.request.urlopen(url,timeout=30) as r: raw=r.read(2*1024**2+1)
assert len(raw)<=2*1024**2
schema=json.loads(raw);bom=json.loads((R/'local_tool_image_sbom.spdx.json').read_text())
Draft7Validator.check_schema(schema);errors=sorted(Draft7Validator(schema).iter_errors(bom),key=lambda x:str(x.path))
assert not errors,[(list(e.path),e.message) for e in errors[:10]]
ids=[p['SPDXID'] for p in bom['packages']]+[bom['SPDXID']];assert len(ids)==len(set(ids))
for rel in bom['relationships']:assert rel['spdxElementId'] in ids and rel['relatedSpdxElement'] in ids
(R/'sbom_validation.json').write_text(json.dumps({'decision':'PASS','standard':'SPDX-2.3','validation':'Official JSON schema plus package ID uniqueness and relationship target integrity','schema_source_commit':commit,'schema_url':url,'schema_sha256':hashlib.sha256(raw).hexdigest(),'sbom_sha256':hashlib.sha256((R/'local_tool_image_sbom.spdx.json').read_bytes()).hexdigest(),'installed_binary_packages':len(bom['packages'])-1,'scope':'Observed local G0 tool image only; not the historical CI images or a production release','license_and_download_provenance':'NOASSERTION where not independently verified','vulnerability_scan':'NOT EXECUTED'},indent=2))
print('SPDX official schema PASS;',len(ids)-2,'installed packages; exact schema commit',commit)
