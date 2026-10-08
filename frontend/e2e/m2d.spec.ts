import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import zhCN from '../src/locales/zh-CN.json' with { type: 'json' };
import zhHK from '../src/locales/zh-HK.json' with { type: 'json' };
import enUS from '../src/locales/en-US.json' with { type: 'json' };
const catalogs={'zh-CN':zhCN,'zh-HK':zhHK,'en-US':enUS};
type Locale=keyof typeof catalogs;
const manifestPath=process.env.M2D_UAT_MANIFEST;
const manifest=manifestPath?JSON.parse(fs.readFileSync(manifestPath,'utf8')):undefined;
for(const locale of Object.keys(catalogs) as Locale[]) test(`governed same-snapshot approval, request-changes and genuine fact successor in ${locale}`,async({page})=>{
  test.setTimeout(240000);
  expect(manifest).toBeDefined();const messages=catalogs[locale];const values=manifest.REVIEW.intake;
  const missing:string[]=[];page.on('console',msg=>{if(msg.text().includes('I18N_MISSING_KEY'))missing.push(msg.text());});
  await page.addInitScript(v=>localStorage.setItem('stage1-alpha.ui-locale',v),locale);
  expect((await page.request.post('/m0-demo/login',{data:{persona:'REVIEW'}})).status()).toBe(200);
  const next=()=>page.getByRole('button',{name:messages['ui.m1.next'],exact:true}).click();
  async function createReview(label:string,document=false){
    await page.goto('/intake');await page.getByLabel(messages['ui.m2a.projectName']).fill(`M2D ${label} ${locale} ${Date.now()}`);
    await page.getByRole('button',{name:messages['ui.m2a.create'],exact:true}).click();
    const project=await page.getByTestId('intake-project-id').innerText();
    await page.getByLabel(messages['ui.m1.field.scenario']).selectOption(values.business_scenario);
    await page.getByLabel(messages['ui.m1.field.product']).selectOption(values.selected_products[0]);await next();
    for(const field of ['source','destination'] as const) await page.getByLabel(messages[`ui.m1.field.${field}`]).selectOption(values.source_locations[0]);
    await page.getByLabel(messages['ui.m1.field.purpose']).fill(values.business_purpose);await page.getByLabel(messages['ui.m1.field.dataVolume']).fill('3');await next();
    await page.getByLabel(messages['ui.m1.field.description']).fill('Confirmed structured business scenario');
    await page.getByRole('button',{name:messages['ui.m2a.save'],exact:true}).click();
    await expect(page.getByLabel(messages['ui.m1.field.scenario'])).toHaveValue(values.business_scenario);await next();await next();
    if(document){
      const binary=execFileSync('python',['-c',"from docx import Document;import io,sys;d=Document();d.add_paragraph('Purpose: Other purpose');d.core_properties.identifier=sys.argv[1];b=io.BytesIO();d.save(b);sys.stdout.buffer.write(b.getvalue())",project]);
      await page.getByLabel(messages['ui.m2b.select']).setInputFiles({name:'review-source.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:binary});
      await page.getByRole('button',{name:messages['ui.m2b.upload'],exact:true}).click();
      await expect(page.getByTestId('document-input')).toContainText('review-source.docx');
      await page.getByRole('button',{name:messages['ui.m2b.parse'],exact:true}).click();await expect(page.getByTestId('document-input')).toContainText(messages['ui.m2b.parsed']);
    }
    await next();await page.getByRole('checkbox',{name:messages['ui.m1.confirmFacts']}).check();
    await page.getByRole('button',{name:messages['ui.m2a.confirmStart'],exact:true}).click();
    const run=await page.getByTestId('workflow-run-id').innerText();
    const view=await(await page.request.get(`/api/v1/workflows/${run}`)).json();expect(view.status).toBe('REVIEW_REQUIRED');
    const review=await(await page.request.get(`/api/v1/reviews/${view.review_id}`)).json();
    return {project,run,review,snapshot:view.analysis_snapshot_id};
  }
  async function open(value:Awaited<ReturnType<typeof createReview>>){
    await page.goto(`/results/${value.run}`);await page.getByRole('link',{name:messages['ui.m2d.openReview'],exact:true}).click();
    await expect(page.getByTestId('review-id')).toHaveText(value.review.review_id);await expect(page.getByTestId('review-state')).toHaveText(messages['ui.m2d.codes.PENDING']);
  }
  async function act(action:'APPROVE'|'REQUEST_CHANGES'|'SUBMIT_CORRECTION'){
    await page.getByRole('button',{name:messages[`ui.m2d.codes.${action}`],exact:true}).click();
    await page.getByRole('button',{name:messages['ui.m2d.confirm'],exact:true}).click();
    await expect(page.getByRole('dialog')).toHaveCount(0,{timeout:60000});
  }
  // A: real owner interrupt/approval, same snapshot and run, no browser actor.
  const a=await createReview('same');await open(a);
  expect(a.review.allowed_actions).toContain('APPROVE');await act('APPROVE');
  await expect(page.getByTestId('review-state')).toHaveText(messages['ui.m2d.codes.APPROVED']);await page.reload();
  const completed=await(await page.request.get(`/api/v1/workflows/${a.run}`)).json();expect(completed.status).toBe('COMPLETED');expect(completed.analysis_snapshot_id).toBe(a.snapshot);
  const approved=await(await page.request.get(`/api/v1/reviews/${a.review.review_id}`)).json();expect(approved.history).toHaveLength(1);expect(approved.history[0].decided_by).toBe('author');
  expect((await page.request.post(`/api/v1/reviews/${a.review.review_id}/resume`)).status()).toBe(200);
  expect((await(await page.request.get(`/api/v1/reviews/${a.review.review_id}`)).json()).history).toHaveLength(1);
  // B: governed request-changes holds same source and produces no final path.
  const b=await createReview('changes');await open(b);await page.getByLabel(messages['ui.m2d.comment']).fill('Clarification requested');await act('REQUEST_CHANGES');
  await expect(page.getByTestId('review-state')).toHaveText(messages['ui.m2d.codes.CHANGES_REQUESTED']);await page.reload();
  const held=await(await page.request.get(`/api/v1/workflows/${b.run}`)).json();expect(held.status).toBe('REVIEW_REQUIRED');expect(held.analysis_snapshot_id).toBe(b.snapshot);expect(held.result_refs.applicability).toBeUndefined();
  await expect(page.getByTestId('review-state')).toHaveText(messages['ui.m2d.codes.CHANGES_REQUESTED']);
  // C: genuine doc/manual conflict; approved source selection creates S2, S1 unchanged.
  const c=await createReview('correction',true);await open(c);expect(c.review.allowed_actions).not.toContain('APPROVE');
  await expect(page.getByRole('button',{name:messages['ui.m2d.codes.APPROVE'],exact:true})).toHaveCount(0);
  const original=await(await page.request.get(`/api/v1/workflows/${c.run}/stage1-result`)).json();
  const chosen=c.review.choices.find((x:{structured_provenance:unknown[]})=>x.structured_provenance.length);
  expect(chosen).toBeTruthy();expect(c.review.choices.some((x:{source_trace_ids:string[]})=>x.source_trace_ids.length)).toBe(true);
  await page.getByRole('combobox',{name:messages['ui.m2d.selectChoice']}).click();await page.getByText(chosen.display_value,{exact:true}).last().click();await act('SUBMIT_CORRECTION');
  await expect(page.getByTestId('review-state')).toHaveText(messages['ui.m2d.codes.SUPERSEDED']);
  const corrected=await(await page.request.get(`/api/v1/reviews/${c.review.review_id}`)).json();expect(corrected.lineage.successor_snapshot_id).not.toBe(c.snapshot);
  const successor=await(await page.request.get(`/api/v1/workflows/${corrected.lineage.successor_workflow_run_id}/stage1-result`)).json();
  expect(successor.status).toBe('COMPLETED');expect(successor.analysis_snapshot_id).toBe(corrected.lineage.successor_snapshot_id);expect(successor.project.project_id).toBe(c.project);
  expect(await(await page.request.get(`/api/v1/workflows/${c.run}/stage1-result`)).json()).toEqual(original);
  await page.getByRole('link',{name:messages['ui.m2d.newResult'],exact:true}).click();await expect(page.getByTestId('stage1-snapshot-id')).toHaveText(corrected.lineage.successor_snapshot_id,{timeout:60000});
  // Current permission is enforced by backend and UI after a new session.
  expect((await page.request.post('/m0-demo/login',{data:{persona:'REVIEW_READER'}})).status()).toBe(200);await page.goto(`/reviews/${b.review.review_id}`);
  await expect(page.getByText(messages['ui.m2d.readOnly'],{exact:true})).toBeVisible();
  expect((await page.request.post(`/api/v1/reviews/${b.review.review_id}/decisions`,{data:{decision:'REJECT',expected_record_version:2,idempotency_key:'denied'}})).status()).toBe(404);
  expect(missing).toEqual([]);await page.screenshot({path:`test-results/m2d-${locale}.png`,fullPage:true});
});
