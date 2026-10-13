import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import zhCN from '../src/locales/zh-CN.json' with { type: 'json' };
import zhHK from '../src/locales/zh-HK.json' with { type: 'json' };
import enUS from '../src/locales/en-US.json' with { type: 'json' };
const catalogs = { 'zh-CN': zhCN, 'zh-HK': zhHK, 'en-US': enUS };
const manifest = JSON.parse(fs.readFileSync(process.env.STAGE1_UAT_MANIFEST!, 'utf8'));
test.use({ trace: 'off', screenshot: 'off', actionTimeout: 20000 });

for (const outcome of ['DIRECT','CONDITIONAL','LOCALIZATION','REVIEW']) {
  for (const locale of Object.keys(catalogs) as (keyof typeof catalogs)[]) {
    test(`blank project canonical ${outcome} business journey ${locale}`, async ({ page, playwright }) => {
      test.setTimeout(180000);
      const started=Date.now(); const m=catalogs[locale]; const f=manifest[outcome];
      const caseFile={DIRECT:'TC-01',CONDITIONAL:'TC-02',LOCALIZATION:'TC-03',REVIEW:'TC-04'}[outcome as 'DIRECT'|'CONDITIONAL'|'LOCALIZATION'|'REVIEW'];
      const oracle=JSON.parse(fs.readFileSync(`../tests/e2e/stage1/business_cases/${caseFile}.json`,'utf8'));
      expect(oracle.fixture_kind).toBe('SYNTHETIC_GOVERNED_TEST_DATA');
      const errors:string[]=[];
      page.on('pageerror',e=>errors.push(e.message));
      page.on('console',e=>{if(e.type()==='error')errors.push(e.text());});
      page.on('response',r=>{if(r.status()>=400)errors.push(`HTTP ${r.status()} ${new URL(r.url()).pathname}`);});
      await page.addInitScript(value=>localStorage.setItem('stage1-alpha.ui-locale',value),locale);
      const login=await page.request.post('/m0-demo/login',{data:{persona:outcome}});
      expect(login.status()).toBe(200);expect((await login.json()).contexts).toEqual([]);
      expect(f.permissions).not.toContain('metadata:admin');
      await page.goto('/intake');
      await page.getByLabel(m['ui.m2a.projectName']).fill(`Full business ${outcome} ${locale} ${Date.now()}`);
      await page.getByRole('button',{name:m['ui.m2a.create'],exact:true}).click();
      const project=await page.getByTestId('intake-project-id').innerText();
      const before=await (await page.request.get(`/api/v1/projects/${project}/intake`)).json();
      expect(before.status).toBe('DRAFT');expect(before.analysis_snapshot_id).toBeNull();
      const governor=[];
      for(const role of ['ADMIN','REVIEWER']) {
        const ctx=await playwright.request.newContext({baseURL:process.env.M0_FRONTEND_URL??'http://127.0.0.1:5173'});
        expect((await ctx.post('/m0-demo/login',{data:{persona:outcome+'_'+role}})).status()).toBe(200);governor.push(ctx);
      }
      try {
        // Refresh real governed provider health; do not weaken its existing TTL.
        for(const deployment of f.deployments){
          const health=await governor[0].post(`/api/v1/admin/model-providers/models/deployments/${deployment}/test`,{data:{operation:'chat'}});
          expect(health.status()).toBe(200);expect((await health.json()).status).toBe('HEALTHY');
        }
        const published=await governor[0].post('/api/v1/admin/model-usage-policies',{data:{code:`project-${crypto.randomUUID()}`,display_name:'Published project policy',payload:{...f.project_policy_payload,project_id:project}}});
        expect(published.status()).toBe(200);let policy=await published.json();
        for(const [action,actor] of [['submit-review',0],['approve',1],['publish',0]] as const){
          const response=await governor[actor].post(`/api/v1/admin/model-usage-policies/${policy.version_id}/${action}`,{data:{expected_record_version:policy.record_version}});
          expect(response.status()).toBe(200);policy=await response.json();
        }
      } finally {await Promise.all(governor.map(c=>c.dispose()));}
      const next=()=>page.getByRole('button',{name:m['ui.m1.next'],exact:true}).click();
      await page.getByLabel(m['ui.m1.field.scenario']).selectOption(f.intake.business_scenario);
      await page.getByLabel(m['ui.m1.field.product']).selectOption(f.intake.selected_products[0]);await next();
      await page.getByLabel(m['ui.m1.field.source']).selectOption(f.intake.source_locations[0]);
      await page.getByLabel(m['ui.m1.field.destination']).selectOption(f.intake.destination_locations[0]);
      expect(f.intake.source_locations[0]).not.toBe(f.intake.destination_locations[0]);
      await page.getByLabel(m['ui.m1.field.purpose']).fill(f.intake.business_purpose);
      await page.getByLabel(m['ui.m1.field.dataVolume']).fill('3');
      await page.getByRole('button',{name:m['ui.m1.addFlow'],exact:true}).click();
      await page.getByLabel(m['ui.stage1.flow.data_item_canonical_name']).fill('Governed Data');
      await page.getByLabel(m['ui.stage1.flow.source_name']).fill('Business source');
      await page.getByLabel(m['ui.stage1.flow.destination_name']).fill('Business destination');
      await page.getByLabel(m['ui.m1.flow.source_location']).selectOption(f.intake.source_locations[0]);
      await page.getByLabel(m['ui.m1.flow.destination_location']).selectOption(f.intake.destination_locations[0]);
      await page.getByLabel(m['ui.stage1.flow.direction']).selectOption('SOURCE_TO_DESTINATION');await next();
      await page.getByLabel(m['ui.m1.field.description']).fill(f.intake.scenario_description);
      const selection=page.getByLabel(m['ui.phase1kb.selectionMode'],{exact:true});
      const mode=outcome==='CONDITIONAL'?'SINGLE':outcome==='REVIEW'?'MULTI_MODEL':'AUTO';
      await selection.selectOption(mode);
      if(mode!=='AUTO')await page.getByLabel(m['ui.phase1kb.eligibleModels']).selectOption(mode==='SINGLE'?f.models[0]:f.models);
      const save=page.waitForResponse(r=>r.url().endsWith('/intake')&&r.request().method()==='PUT');
      await page.getByRole('button',{name:m['ui.m2a.save'],exact:true}).click();expect((await save).status()).toBe(200);
      await next();await next();
      const binary=execFileSync('python',['-c','from stage1_business_fixtures import genuine_docx; import sys; sys.stdout.buffer.write(genuine_docx(sys.argv[1],semantic_only=sys.argv[2]=="DIRECT"))',project,outcome]);
      await page.getByLabel(m['ui.m2b.select']).setInputFiles({name:'business.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:binary});
      const uploading=page.waitForResponse(r=>r.url().endsWith('/intake/documents')&&r.request().method()==='POST');
      await page.getByRole('button',{name:m['ui.m2b.upload'],exact:true}).click();expect((await uploading).status()).toBe(201);
      await page.getByRole('button',{name:m['ui.m2b.parse'],exact:true}).click();await expect(page.getByTestId('document-input')).toContainText(m['ui.m2b.parsed']);await next();
      const preparing=page.waitForResponse(r=>r.url().endsWith('/candidate-preparation')&&r.request().method()==='POST');
      await page.getByRole('button',{name:m['ui.candidates.prepare'],exact:true}).click();expect((await preparing).status()).toBe(200);
      const candidates=page.getByTestId('candidate-review-item');await expect(candidates.first()).toBeVisible();
      if(outcome==='DIRECT')await expect(candidates.first()).toContainText(m['ui.candidates.aiDerived']);
      for(const item of await candidates.all())await item.getByRole('combobox').selectOption('ACCEPT');
      const deciding=page.waitForResponse(r=>r.url().endsWith('/candidate-decisions')&&r.request().method()==='POST');
      await page.getByRole('button',{name:m['ui.candidates.submit'],exact:true}).click();expect((await deciding).status()).toBe(200);
      await page.getByRole('checkbox',{name:m['ui.m1.confirmFacts']}).check();
      const starting=page.waitForResponse(r=>r.url().endsWith('/workflow')&&r.request().method()==='POST',{timeout:120000});
      await page.getByRole('button',{name:m['ui.m2a.confirmStart'],exact:true}).click();
      const startedResponse=await starting;expect(startedResponse.status()).toBe(200);
      const startedRun=await startedResponse.json();expect(['COMPLETED','REVIEW_REQUIRED']).toContain(startedRun.status);
      await expect(page.getByTestId('workflow-run-id')).toBeVisible({timeout:120000});
      const run=await page.getByTestId('workflow-run-id').innerText();
      const resultResponse=await page.request.get(`/api/v1/workflows/${run}/stage1-result`,{timeout:60000});expect(resultResponse.status()).toBe(200);
      const result=await resultResponse.json();
      expect(result.cross_border.items[0].status).toBe(oracle.expected_formal_outcome);expect(result.generation_available).toBe(false);
      expect(result.flows).toHaveLength(1);expect(result.classification).toHaveLength(2);
      await page.goto(`/results/${run}`);await expect(page.getByTestId('stage1-snapshot-id')).toHaveText(result.analysis_snapshot_id,{timeout:60000});
      await expect(page.getByRole('img',{name:m['ui.m2c.transferMap']})).toBeVisible();
      for(const key of ['workflow','risk','recommendation','path','requirements','obligations','regulations'] as const)await expect(page.getByText(m[`ui.m2c.${key}`],{exact:true}).first()).toBeVisible();
      if(outcome!=='REVIEW'){
        for(const field of ['obligation','candidate_path','risk','recommendation','final_path','document_requirements'])expect(result[field].items.length).toBeGreaterThan(0);
        expect(result.final_path.engine_version).toBe('FORMAL_DECISION_V2_1');
        expect(result.final_path.items[0].support.evidence_ids.length).toBeGreaterThan(0);
      }else expect(result.review_id).toBeTruthy();
      await page.getByRole('button',{name:m['ui.m2c.legalEvidence'],exact:true}).click();
      await expect(page.getByRole('dialog')).toContainText(result.legal_basis[0].citation_locator);
      await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).not.toBeVisible();
      if(outcome==='REVIEW'){
        await page.getByRole('link',{name:m['ui.m2d.openReview'],exact:true}).click();
        await expect(page.getByTestId('review-detail')).toBeVisible();
        const reviewResponse=await page.request.get(`/api/v1/reviews/${result.review_id}`);expect(reviewResponse.status()).toBe(200);
        const task=await reviewResponse.json();expect(task.analysis_snapshot_id).toBe(result.analysis_snapshot_id);expect(task.workflow_run_id).toBe(run);
        expect(task.reason_codes.length).toBeGreaterThan(0);expect(Array.isArray(task.allowed_actions)).toBe(true);
        await expect(page.getByText(m['ui.m2d.history'],{exact:true})).toBeVisible();
        for(const action of task.allowed_actions)await expect(page.getByRole('button',{name:m[`ui.m2d.codes.${action}` as keyof typeof m],exact:true})).toBeVisible();
      }
      if(outcome==='REVIEW'){
        await page.goto(`/results/${run}`);
        await expect(page.getByTestId('stage1-snapshot-id')).toHaveText(result.analysis_snapshot_id,{timeout:60000});
      }
      // Observe the real reload request instead of starting another expensive
      // full historical revalidation concurrently with the workspace reader.
      const reloading=page.waitForResponse(r=>r.url().endsWith(`/workflows/${run}/stage1-result`)&&r.request().method()==='GET',{timeout:60000});
      await page.reload();
      const reread=await reloading;expect(reread.status()).toBe(200);
      await expect(page.getByTestId('stage1-snapshot-id')).toHaveText(result.analysis_snapshot_id,{timeout:60000});
      expect(await reread.json()).toEqual(result);
      expect(await page.locator('body').innerText()).not.toMatch(/ui\.(?:stage1|candidates|m2c|m2d)\./);
      expect(errors).toEqual([]);
      const normalized=execFileSync('python',['-c',`import json,sys
from stage1_semantic_parity import normalize_formal
from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
r=json.load(sys.stdin);f={'sf':build_session_factory(get_settings().database_url)[1],'tenant':r['classification'][0]['tenant_id']}
print(json.dumps(normalize_formal(f,r),sort_keys=True,separators=(',',':')))`],{input:JSON.stringify(result)}).toString().trim();
      const semanticDigest=createHash('sha256').update(normalized).digest('hex');

      await test.info().attach('measured-business',{body:JSON.stringify({outcome,locale,project_id:project,snapshot_id:result.analysis_snapshot_id,workflow_run_id:run,elapsed_ms:Date.now()-started,formal_status:result.cross_border.items[0].status,normalized_formal_sha256:semanticDigest,retries:test.info().retry}),contentType:'application/json'});
    });
  }
}
