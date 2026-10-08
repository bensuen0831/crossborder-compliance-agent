import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import i18n, { supportedLocales } from '../../i18n';
import { ReviewDetail, ReviewList } from './ReviewCenter';
import { reviewsApi, type Review } from './api';
import { validateContract } from '../../api/client';
import formal from '../results/pg-fixture.json';

const reviewId='10000000-0000-4000-8000-000000000001';
function task(changes:Partial<Review>={}):Review {
  return validateContract<Review>('ReviewView',{
    review_id:reviewId,project_id:formal.project.project_id,analysis_snapshot_id:formal.analysis_snapshot_id,
    workflow_run_id:formal.workflow_run_id,review_type:'WORKFLOW_STAGE_REVIEW',reason_codes:['REVIEW_REQUIRED'],
    reason_summary:'Requirement confirmation',object_type:'WORKFLOW_RUN',object_id:formal.workflow_run_id,
    owning_stage:'requirement',status:'PENDING',presentation_state:'PENDING',allowed_actions:['APPROVE','REJECT','REQUEST_CHANGES'],
    resolution_mode:'SAME_SNAPSHOT',required_role:'workflow:review',continuation_status:'NOT_AVAILABLE',
    created_at:'2026-01-01T00:00:00Z',updated_at:'2026-01-01T00:00:00Z',record_version:1,
    evidence_refs:[],legal_basis_refs:[],choices:[],history:[],lineage:null,capability_gap:null,intake_facts:null,...changes,
  });
}
function mount(value=task(), status=200) {
  const writes:{url:string;body:Record<string,unknown>}[]=[];
  vi.stubGlobal('fetch',vi.fn(async(url:string,options:RequestInit={})=>{
    if(options.method==='POST') {writes.push({url,body:options.body?JSON.parse(String(options.body)): {}});return new Response(JSON.stringify(status===200&&url.endsWith('/corrections')?{correction_id:reviewId,source_review_id:reviewId,source_workflow_run_id:value.workflow_run_id,source_snapshot_id:value.analysis_snapshot_id,successor_project_version_id:reviewId,successor_snapshot_id:reviewId,successor_workflow_run_id:reviewId,correction_type:'SELECT_BUSINESS_FACT',submitted_by:'reviewer',created_at:'2026-01-01T00:00:00Z',comment:'Source selection',rerun_from_stage:'requirement'}:status===200?{...value,status:'APPROVED',presentation_state:'APPROVED',allowed_actions:[]}:{}),{status});}
    return new Response(JSON.stringify(url.includes('stage1-result')?formal:{items:[value],total:1,offset:0,limit:10}));
  }));
  const refresh=vi.fn();
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><ReviewDetail review={value} identity="review-unit" refresh={refresh}/></QueryClientProvider></MemoryRouter>);
  return {writes,refresh};
}

describe('governed review presentation',()=>{
  for(const locale of supportedLocales) it(`renders backend-owned review state and actions in ${locale}`,async()=>{
    await i18n.changeLanguage(locale);const value=task();const before=JSON.stringify(value);const {writes}=mount(value);
    expect(screen.getByTestId('review-state')).toHaveTextContent(i18n.t('ui.m2d.codes.PENDING'));
    for(const action of value.allowed_actions) expect(screen.getByRole('button',{name:i18n.t(`ui.m2d.codes.${action}`)})).toBeEnabled();
    expect(screen.queryByRole('button',{name:i18n.t('ui.m2d.codes.SUBMIT_CORRECTION')})).toBeNull();
    expect(writes).toHaveLength(0);expect(JSON.stringify(value)).toBe(before);
  });
  it('shows read-only permission state without fabricating actions',()=>{
    mount(task({allowed_actions:[]}));expect(screen.getByText(i18n.t('ui.m2d.readOnly'))).toBeVisible();
    expect(screen.queryByRole('button',{name:i18n.t('ui.m2d.codes.APPROVE')})).toBeNull();
  });
  for(const action of ['APPROVE','REJECT','REQUEST_CHANGES'] as const) it(`confirms ${action} with CAS and no client actor/thread/policy`,async()=>{
    const {writes,refresh}=mount();fireEvent.change(screen.getByLabelText(i18n.t('ui.m2d.comment')),{target:{value:'Audit comment'}});
    fireEvent.click(screen.getByRole('button',{name:i18n.t(`ui.m2d.codes.${action}`)}));
    await waitFor(()=>expect(screen.getByText(i18n.t('ui.m2d.sameSnapshot'))).toBeVisible());expect(writes).toHaveLength(0);
    fireEvent.click(screen.getByRole('button',{name:i18n.t('ui.m2d.confirm')}));
    await waitFor(()=>expect(refresh).toHaveBeenCalled());
    expect(writes[0].body).toEqual({decision:action,expected_record_version:1,comment:'Audit comment',idempotency_key:expect.any(String)});
  });
  it('does not offer approval for a formal conflict and submits typed owning correction',async()=>{
    const id='10000000-0000-4000-8000-000000000002';
    const value=task({object_type:'CONTEXT_CONFLICT',object_id:id,reason_codes:['BUSINESS_FACT_CONFLICT'],resolution_mode:'SUCCESSOR_SNAPSHOT',allowed_actions:['SUBMIT_CORRECTION'],choices:[{object_id:id,object_type:'BUSINESS_FACT',display_value:'Governed value',source_trace_ids:[],source_document_ids:[],structured_provenance:[]}]});
    const {writes}=mount(value);expect(screen.queryByRole('button',{name:i18n.t('ui.m2d.codes.APPROVE')})).toBeNull();
    const select=screen.getByRole('combobox',{name:i18n.t('ui.m2d.selectChoice')});fireEvent.mouseDown(select);fireEvent.click(screen.getAllByText('Governed value').at(-1)!);
    fireEvent.click(screen.getByRole('button',{name:i18n.t('ui.m2d.codes.SUBMIT_CORRECTION')}));
    await waitFor(()=>expect(screen.getByText(i18n.t('ui.m2d.newSnapshot'))).toBeVisible());
    fireEvent.click(screen.getByRole('button',{name:i18n.t('ui.m2d.confirm')}));
    await waitFor(()=>expect(writes).toHaveLength(1));expect(writes[0].body.correction).toEqual({correction_type:'SELECT_BUSINESS_FACT',target_object_type:'CONTEXT_CONFLICT',target_object_id:id,selected_fact_id:id});
  });
  it('shows stale-version feedback and reload without changing formal inputs',async()=>{
    const {writes}=mount(task(),409);fireEvent.click(screen.getByRole('button',{name:i18n.t('ui.m2d.codes.APPROVE')}));fireEvent.click(screen.getByRole('button',{name:i18n.t('ui.m2d.confirm')}));
    await waitFor(()=>expect(screen.getByText(i18n.t('ui.m2d.stale'))).toBeVisible());expect(writes).toHaveLength(1);
  });
  it('links immutable original and successor results',()=>{
    mount(task({presentation_state:'SUPERSEDED',allowed_actions:[],lineage:{correction_id:reviewId,source_review_id:reviewId,source_workflow_run_id:formal.workflow_run_id,source_snapshot_id:formal.analysis_snapshot_id,successor_project_version_id:reviewId,successor_snapshot_id:reviewId,successor_workflow_run_id:reviewId,correction_type:'SELECT_BUSINESS_FACT',submitted_by:'reviewer',created_at:'2026-01-01T00:00:00Z',comment:'Source selection',rerun_from_stage:'requirement'}}));
    expect(screen.getByRole('link',{name:i18n.t('ui.m2d.oldResult')})).toHaveAttribute('href',`/results/${formal.workflow_run_id}`);
    expect(screen.getByRole('link',{name:i18n.t('ui.m2d.newResult')})).toHaveAttribute('href',`/results/${reviewId}`);
  });
  it('reuses official legal-basis and genuine evidence drawer without translation',async()=>{
    mount();fireEvent.click(screen.getByRole('button',{name:i18n.t('ui.m2d.sources')}));
    await waitFor(()=>expect(screen.getByText(formal.legal_basis[0].official_source)).toBeVisible());
    expect(screen.getByRole('dialog')).toBeVisible();
  });
  it('list uses authorized server filtering and pagination',async()=>{
    const calls:string[]=[];vi.stubGlobal('fetch',vi.fn(async(url:string)=>{calls.push(url);return new Response(JSON.stringify({items:[task()],total:1,offset:0,limit:10}));}));
    render(<MemoryRouter><QueryClientProvider client={new QueryClient()}><ReviewList identity="reader"/></QueryClientProvider></MemoryRouter>);
    await waitFor(()=>expect(screen.getByRole('link',{name:reviewId})).toBeVisible());
    fireEvent.change(screen.getByLabelText(i18n.t('ui.m2d.projectFilter')),{target:{value:formal.project.project_id}});
    await waitFor(()=>expect(calls.some(url=>url.includes(`project_id=${formal.project.project_id}`))).toBe(true));
  });
  it('rejects wrong identities and invented legal editing requests in runtime contracts',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(task()))));await expect(reviewsApi.read('10000000-0000-4000-8000-000000000002')).rejects.toThrow('REVIEW_IDENTITY_MISMATCH');
    expect(()=>validateContract('ReviewDecisionRequest',{decision:'APPROVE',expected_record_version:1,idempotency_key:'x',decided_by:'client'})).toThrow('API_CONTRACT_MISMATCH');
  });
});
