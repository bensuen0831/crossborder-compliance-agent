"""Verify fresh source artifacts; keep only safe small reports and image hashes."""
import argparse,hashlib,json,pathlib,re,subprocess,tarfile,zipfile
R=pathlib.Path('/workspace/kb01-g1r1');REPO='bensuen0831/crossborder-compliance-agent';S='4593a355d0711a9ba955b1624926a2ec71d60430'

def sha_bytes(raw):return hashlib.sha256(raw).hexdigest()
def sha_path(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  while c:=f.read(1048576):h.update(c)
 return h.hexdigest()

class Counted:
 def __init__(self,f):self.f=f;self.h=hashlib.sha256();self.n=0
 def read(self,n=-1):
  c=self.f.read(n);self.h.update(c);self.n+=len(c);return c

def inspect_oci(stream):
 measured={};documents={};reader=Counted(stream)
 with tarfile.open(fileobj=reader,mode='r|') as archive:
  for item in archive:
   if not item.isfile() or item.name.startswith('/') or '..' in pathlib.PurePosixPath(item.name).parts:
    raise ValueError('UNSAFE_OCI_MEMBER')
   if item.name in ('index.json','oci-layout'):
    raw=archive.extractfile(item).read();assert len(raw)<1048576;documents[item.name]=json.loads(raw)
   else:
    assert re.fullmatch('blobs/sha256/[0-9a-f]{64}',item.name)
    h=hashlib.sha256();small=bytearray();total=0
    source=archive.extractfile(item)
    while c:=source.read(1048576):
     h.update(c);total+=len(c)
     if item.size<1048576:small.extend(c)
    assert h.hexdigest()==item.name.split('/')[-1] and total==item.size
    measured['sha256:'+h.hexdigest()]={'size':total}
    if small:
     try:documents['sha256:'+h.hexdigest()]=json.loads(small)
     except (ValueError,UnicodeError):pass
 while reader.read(1048576):pass
 assert documents['oci-layout']['imageLayoutVersion']=='1.0.0'
 entries=documents['index.json']['manifests'];assert len(entries)==1
 selected=entries[0];manifest=documents[selected['digest']]
 for desc in [selected,manifest['config'],*manifest['layers']]:
  assert measured[desc['digest']]['size']==desc['size']
 return {'archive_sha256':reader.h.hexdigest(),'bytes':reader.n,'manifest_digest':selected['digest'],'config_digest':manifest['config']['digest'],'verified_blobs':measured,'platform':selected.get('platform')}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');args=parser.parse_args()
 ci=json.loads((R/('ci-artifacts-available.json' if args.partial else 'ci-complete.json')).read_text());assert ci['source_sha']==S
 if not args.partial:assert ci['success_workflows']==12 and ci['verified_job_checkouts']>=22
 cache=R/'verified-reports';cache.mkdir(exist_ok=True);zips=R/'zip-scratch';zips.mkdir(exist_ok=True)
 saved=R/'artifact-records';saved.mkdir(exist_ok=True)
 records=[];jsons={};images={}
 for run in ci['runs']:
  for artifact in run['artifacts']:
   assert not artifact['expired'] and artifact['digest'].startswith('sha256:')
   prior=saved/(str(artifact['id'])+'.json')
   if prior.exists():
    row=json.loads(prior.read_text());assert row['digest']==artifact['digest'] and 'sha256:'+row['downloaded_zip_sha256']==artifact['digest']
    for item in row['members']:
     if 'retained_report' in item:
      path=R/item['retained_report'];assert sha_path(path)==item['sha256']
      if item['path'].endswith('.json'):
       try:jsons[(artifact['name'],pathlib.PurePosixPath(item['path']).name)]=json.loads(path.read_text())
       except ValueError:pass
    if row.get('oci'):images[artifact['name']]=row['oci']
    records.append(row);continue
   path=zips/(str(artifact['id'])+'.zip');h=hashlib.sha256();n=0
   process=subprocess.Popen(['gh','api',f'repos/{REPO}/actions/artifacts/{artifact["id"]}/zip'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   with path.open('wb') as output:
    while c:=process.stdout.read(1048576):
     h.update(c);n+=len(c);assert n<2*1024**3;output.write(c)
   error=process.stderr.read();assert process.wait()==0,error[:300]
   assert 'sha256:'+h.hexdigest()==artifact['digest'],artifact['id']
   row={'run_id':run['id'],**artifact,'downloaded_zip_sha256':h.hexdigest(),'downloaded_bytes':n,'members':[]}
   with zipfile.ZipFile(path) as archive:
    for member in archive.infolist():
     if member.is_dir():continue
     parts=pathlib.PurePosixPath(member.filename).parts
     assert not member.filename.startswith('/') and '..' not in parts
     if member.filename.endswith('image.oci.tar'):
      with archive.open(member) as source:proof=inspect_oci(source)
      images[artifact['name']]=proof
      row['oci']=proof
      row['members'].append({'path':member.filename,'bytes':member.file_size,'sha256':proof['archive_sha256']})
     else:
      h2=hashlib.sha256();payload=bytearray()
      with archive.open(member) as source:
       while c:=source.read(1048576):
        h2.update(c)
        if member.file_size<25*1024**2 and member.filename.endswith(('.json','.xml','.txt')):payload.extend(c)
      item={'path':member.filename,'bytes':member.file_size,'sha256':h2.hexdigest()}
      if payload:
       target=cache/str(artifact['id'])/member.filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload);item['retained_report']=str(target.relative_to(R))
       if member.filename.endswith('.json'):
        try:jsons[(artifact['name'],pathlib.PurePosixPath(member.filename).name)]=json.loads(payload)
        except ValueError:pass
      row['members'].append(item)
   records.append(row);prior.write_text(json.dumps(row,indent=2));path.unlink();print('Verified artifact',artifact['id'],artifact['name'],flush=True)
 toolchains=[]
 for (name,filename),proof in jsons.items():
  if not name.startswith('kb01-tools-') or filename!='provenance.json':continue
  key=name.removeprefix('kb01-tools-');image=images['toolchain-oci-'+key]
  assert image['archive_sha256']==proof['oci']['archive_sha256'] and image['manifest_digest']==proof['oci']['manifest_digest'] and image['config_digest']==proof['oci']['config_digest']
  assert proof['source_build']['runner_checkout_sha']==S and proof['source_build']['source_dirty'] is False
  assert proof['sbom']['decision']=='PASS' and proof['security']['scan_execution']=='PASS'
  inventory=jsons[(name,'inventory.json')]
  local=json.loads((R/'toolchain/inventory.json').read_text())
  assert inventory['installed_packages']==local['installed_packages']
  assert inventory['critical_binaries']==local['critical_binaries']
  toolchains.append({'artifact_name':name,'provenance':proof,'oci_blob_verification':image,'packages_match_pinned_local_image':True,'critical_binary_hashes_match':True})
 assert len(toolchains)==len(images),(len(toolchains),len(images))
 if not args.partial:assert len(images)>=7,len(images)
 out={'decision':'PASS_ARTIFACT_INTEGRITY_NOT_SECURITY_ACCEPTANCE','source_sha':S,'artifact_zip_digests_verified':len(records),'oci_images_verified':len(images),'artifacts':records,'toolchains':toolchains}
 (R/('artifact-validation-partial.json' if args.partial else 'artifact-validation.json')).write_text(json.dumps(out,indent=2)+'\n');print('Artifact integrity verified',len(records),'images',len(images))

if __name__=='__main__':main()
