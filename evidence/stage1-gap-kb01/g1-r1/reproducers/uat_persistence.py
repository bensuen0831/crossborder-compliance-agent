import argparse,hashlib,json,pathlib,subprocess
from uuid import UUID
import httpx
from sqlalchemy import select
from scripts.kb01.rc1 import environment,settings
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import KnowledgeBinaryAttachmentEntity as A,KnowledgeUploadSessionEntity as U

parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['before','after']);args=parser.parse_args()
root=pathlib.Path('/workspace/kb01-rc1');person=json.loads((root/'personas.json').read_text())['A'];sf=build_session_factory(environment(root,settings(root))['DATABASE_URL'])[1]
with sf() as s:
 rows=s.execute(select(k.KnowledgeDocumentVersionEntity,U).join(A,(A.knowledge_version_id==k.KnowledgeDocumentVersionEntity.knowledge_version_id)&(A.tenant_id==k.KnowledgeDocumentVersionEntity.tenant_id)).join(U,(U.upload_session_id==A.upload_session_id)&(U.tenant_id==A.tenant_id)).where(A.tenant_id==person['tenant_id'],k.KnowledgeDocumentVersionEntity.lifecycle=='ACTIVE').order_by(k.KnowledgeDocumentVersionEntity.knowledge_version_id)).all()
 records=[]
 with httpx.Client(base_url='http://127.0.0.1:18010',timeout=30) as client:
  response=client.post('/m0-demo/login',json={'persona':'A'});assert response.status_code==200
  for version,upload in rows:
   digest=hashlib.sha256();count=0
   with client.stream('GET','/api/v1/admin/knowledge-management/documents/versions/'+version.knowledge_version_id+'/original') as response:
    assert response.status_code==200,(version.knowledge_version_id,response.status_code)
    for chunk in response.iter_bytes(1048576):digest.update(chunk);count+=len(chunk)
   assert digest.hexdigest()==upload.content_sha256 and count==upload.declared_bytes
   records.append({'knowledge_version_id':version.knowledge_version_id,'document_id':version.document_id,'version':version.version,'language':version.language,'format':upload.declared_format,'content_hash':version.content_hash,'object_version':upload.object_version,'original_bytes':count,'original_sha256':digest.hexdigest()})
 assert len(records)>=18 and {'PDF','DOC','DOCX','TXT','HTML','XHTML'}<=set(r['format'] for r in records)
out={'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'dataset':'SYNTHETIC_GOVERNED_TEST_DATA','phase':args.phase,'original_downloads_verified':len(records),'records':records,'complete_semantic_sha256':hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest(),'method':'Canonical ACTIVE KnowledgeVersion plus authorized HTTP original downloads with exact S3 object-version pins; credentials/cookies and raw bodies omitted'}
if args.phase=='after':
 before=json.loads(pathlib.Path('/workspace/kb01-g1r1/uat-documents-before.json').read_text());assert before['records']==records and before['complete_semantic_sha256']==out['complete_semantic_sha256'];out['restart_persistence']='PASS'
pathlib.Path('/workspace/kb01-g1r1/uat-documents-'+args.phase+'.json').write_text(json.dumps(out,indent=2));print(args.phase,len(records),'canonical ACTIVE versions and all six formats; exact authorized original hashes verified')
