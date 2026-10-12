// Real SDK/HTTP segment over an OAuth-owned blank draft; stdin contains private credentials.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { AgentClient } from '../../../sdk/typescript/dist/client.js';
const p=JSON.parse(fs.readFileSync(0,'utf8'));
const sdk=new AgentClient(p.url);
await sdk.authenticate(p.client_id,p.credential);
let draft=await sdk.getIntake(p.project_id);
assert.equal(draft.status,'DRAFT');assert.equal(draft.analysis_snapshot_id,null);
draft=await sdk.updateIntake(p.project_id,{expected_version:draft.version,facts:p.facts},crypto.randomUUID());
const uploaded=await sdk.uploadDocument(p.project_id,new Blob([Buffer.from(p.document_base64,'base64')],{type:p.document_type}),'business.docx',draft.version,crypto.randomUUID());
const version=uploaded.intake_version,doc=uploaded.items[0].document_version_id;
await sdk.parseDocument(p.project_id,doc,version,crypto.randomUUID());
const preview=await sdk.prepareCandidates(p.project_id,version,crypto.randomUUID());
assert(preview.candidates.length>0);assert.deepEqual(await sdk.candidatePreview(p.project_id),preview);
const receipt=await sdk.resolveCandidates(p.project_id,{expected_version:version,candidate_preparation_id:preview.candidate_preparation_id,candidate_universe_digest:preview.candidate_universe_digest,
 decisions:preview.candidates.map(i=>({preparation_candidate_id:i.preparation_candidate_id,action:'ACCEPT'}))},crypto.randomUUID());
const record=await sdk.confirm(p.project_id,version,crypto.randomUUID(),receipt.candidate_decision_set_id);
const accepted=await sdk.startAnalysis(p.project_id,record.analysis_snapshot_id,crypto.randomUUID());
assert.equal(accepted.status,'ACCEPTED');
const status=await sdk.waitForCompletion(record.workflow_run_id,180000,1000);
assert(['COMPLETED','REVIEW_REQUIRED'].includes(status.status));
const result=await sdk.getResult(record.workflow_run_id);
assert.equal(result.cross_border.items[0].status,p.expected);
assert.equal(result.generation_available,false);
const events=[];for await(const event of sdk.events(record.workflow_run_id))events.push(event);
assert.equal(events.at(-1).event_code,status.status==='COMPLETED'?'WORKFLOW_COMPLETED':'REVIEW_REQUIRED');
console.log(JSON.stringify({record,preview,result,terminal_event:events.at(-1).event_code,credentials_archived:false}));
