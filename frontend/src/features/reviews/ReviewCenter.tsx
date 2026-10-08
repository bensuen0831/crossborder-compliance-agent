import { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Card, Descriptions, Drawer, Empty, Input, Modal, Select, Space, Table, Tag, Timeline, Typography } from 'antd';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ApiError } from '../../api/client';
import { ErrorState, LoadingState } from '../../components/States';
import { EvidenceTable, SourceCitationDrawer } from '../../components/Evidence';
import { stage1Read } from '../results/api';
import { reviewsApi, type Review, type Correction, type Decision } from './api';

export function ReviewCenter({ identity }: { identity: string }) {
  const { reviewId } = useParams();
  return reviewId ? <ReviewRoute key={`${identity}:${reviewId}`} id={reviewId} identity={identity}/> : <ReviewList identity={identity}/>;
}

export function ReviewList({ identity }: { identity: string }) {
  const { t, i18n } = useTranslation();
  const [status, setStatus] = useState<string>();
  const [project, setProject] = useState('');
  const [stage, setStage] = useState('');
  const [kind, setKind] = useState('');
  const [after, setAfter] = useState('');
  const [before, setBefore] = useState('');
  const [page, setPage] = useState(1);
  const [order, setOrder] = useState('CREATED_DESC');
  const filters = new URLSearchParams({ offset: String((page - 1) * 10), limit: '10', order });
  if (status) filters.set('status', status);
  if (project) filters.set('project_id', project);
  if (stage) filters.set('owning_stage', stage);
  if (kind) filters.set('review_type', kind);
  if (after) filters.set('created_after', new Date(after).toISOString());
  if (before) filters.set('created_before', new Date(before).toISOString());
  const query = useQuery({ queryKey: ['m2d-review-list', identity, filters.toString()], queryFn: ({ signal }) => reviewsApi.list(filters, signal), retry: false, gcTime: 0 });
  const code = (value: string) => i18n.exists(`ui.m2d.codes.${value}`) ? t(`ui.m2d.codes.${value}`) : value;
  return <section data-testid="review-center" aria-label={t('ui.m2d.title')}>
    <Card title={t('ui.m2d.title')}><Space wrap>
      <Select allowClear aria-label={t('ui.m2d.status')} placeholder={t('ui.m2d.status')} value={status} style={{ width: 180 }} options={['PENDING','APPROVED','REJECTED','CANCELLED'].map(value => ({ value, label: code(value) }))} onChange={value => {setStatus(value);setPage(1);}}/>
      <Input aria-label={t('ui.m2d.projectFilter')} placeholder={t('ui.m2d.projectFilter')} value={project} onChange={e => {setProject(e.target.value);setPage(1);}}/>
      <Input aria-label={t('ui.m2d.stageFilter')} placeholder={t('ui.m2d.stageFilter')} value={stage} onChange={e => {setStage(e.target.value);setPage(1);}}/>
      <Input aria-label={t('ui.m2d.typeFilter')} placeholder={t('ui.m2d.typeFilter')} value={kind} onChange={e => {setKind(e.target.value);setPage(1);}}/>
      <label>{t('ui.m2d.after')}<Input type="datetime-local" aria-label={t('ui.m2d.after')} value={after} onChange={e=>{setAfter(e.target.value);setPage(1);}}/></label>
      <label>{t('ui.m2d.before')}<Input type="datetime-local" aria-label={t('ui.m2d.before')} value={before} onChange={e=>{setBefore(e.target.value);setPage(1);}}/></label>
      <Select aria-label={t('ui.m2d.sort')} value={order} onChange={value=>{setOrder(value);setPage(1);}} options={[{value:'CREATED_DESC',label:t('ui.m2d.newest')},{value:'CREATED_ASC',label:t('ui.m2d.oldest')}]}/>
      <Button onClick={() => void query.refetch()}>{t('ui.m2d.refresh')}</Button>
    </Space></Card>
    {query.isPending ? <LoadingState/> : query.error ? <ErrorState error={query.error} retry={()=>void query.refetch()}/> :
      <Table<Review> rowKey="review_id" dataSource={query.data.items} scroll={{ x: 1100 }} locale={{ emptyText: <Empty description={t('ui.m2d.empty')}/> }} pagination={{ current: page, total: query.data.total, pageSize: 10, showSizeChanger: false, onChange: setPage }} columns={[
        {title:t('ui.m2d.review'),render:(_,r)=><Link to={`/reviews/${r.review_id}`}>{r.review_id}</Link>},
        {title:t('ui.m2d.projectFilter'),dataIndex:'project_id'},
        {title:t('ui.m2d.run'),dataIndex:'workflow_run_id'},
        {title:t('ui.m2d.typeFilter'),dataIndex:'review_type'},
        {title:t('ui.m2d.stageFilter'),dataIndex:'owning_stage'},
        {title:t('ui.m2d.reasons'),render:(_,r)=>r.reason_codes.map(code).join(' · ')},
        {title:t('ui.m2d.object'),dataIndex:'object_type'},
        {title:t('ui.m2d.status'),render:(_,r)=><Tag>{code(r.presentation_state)}</Tag>},
        {title:t('ui.m2d.importance'),render:()=>t('notAvailable')},
        {title:t('ui.m2d.created'),dataIndex:'created_at'},
      ]}/>}
  </section>;
}

function ReviewRoute({ id, identity }: { id: string; identity: string }) {
  const query = useQuery({queryKey:['m2d-review',identity,id],queryFn:({signal})=>reviewsApi.read(id,signal),retry:false,gcTime:0});
  return query.isPending ? <LoadingState/> : query.error ? <ErrorState error={query.error} retry={()=>void query.refetch()}/> : <ReviewDetail review={query.data} identity={identity} refresh={()=>void query.refetch()}/>;
}

export function ReviewDetail({ review: r, identity, refresh }: { review: Review; identity: string; refresh: () => void }) {
  const { t, i18n } = useTranslation();
  const cache = useQueryClient();
  const [comment, setComment] = useState('');
  const [choice, setChoice] = useState<string>();
  const [clarification, setClarification] = useState(r.intake_facts?.scenario_description ?? '');
  const [pending, setPending] = useState<string>();
  const [contextOpen, setContextOpen] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState<string>();
  const retryRequest = useRef<{ signature: string; key: string } | null>(null);
  const result = useQuery({queryKey:['stage1-results',identity,r.workflow_run_id],queryFn:({signal})=>stage1Read(r.workflow_run_id,signal),retry:false,gcTime:0});
  const code = (v: string) => i18n.exists(`ui.m2d.codes.${v}`) ? t(`ui.m2d.codes.${v}`) : v;
  const keyFor = (value: object) => {
    const signature=JSON.stringify(value);
    if(retryRequest.current?.signature !== signature) retryRequest.current={signature,key:crypto.randomUUID()};
    return retryRequest.current!.key;
  };
  const write = useMutation({mutationFn:async(action:string)=>{
    if(!r.allowed_actions.includes(action)) throw new ApiError(409,'ACTION_NOT_ALLOWED');
    if(action==='CONTINUE_SUCCESSOR') return reviewsApi.continueSuccessor(r.review_id);
    if(action==='RESUME') return reviewsApi.resume(r.review_id);
    if(action==='SUBMIT_CORRECTION' || action==='ADD_INFORMATION') {
      let correction:Correction['correction'];
      if(action==='ADD_INFORMATION' && r.intake_facts) correction={correction_type:'CLARIFY_INTAKE',target_object_type:'PROJECT_INTAKE',target_object_id:r.object_id,facts:{...r.intake_facts,scenario_description:clarification}};
      else if(r.object_type==='CONTEXT_CONFLICT' && choice && r.choices.some(c=>c.object_id===choice && c.object_type==='BUSINESS_FACT')) correction={correction_type:'SELECT_BUSINESS_FACT',target_object_type:'CONTEXT_CONFLICT',target_object_id:r.object_id,selected_fact_id:choice};
      else if(r.object_type==='CONTEXT_CONFLICT' && choice && r.choices.some(c=>c.object_id===choice && c.object_type==='PRODUCT_CONTEXT')) correction={correction_type:'SELECT_PRODUCT_SCOPE',target_object_type:'CONTEXT_CONFLICT',target_object_id:r.object_id,selected_product_ids:[choice]};
      else throw new ApiError(409,'CORRECTION_NOT_CONFIGURED');
      const payload={expected_record_version:r.record_version,comment:comment||null,correction};
      return reviewsApi.correct(r.review_id,{...payload,idempotency_key:keyFor(payload)});
    }
    const decision=action as Decision['decision'];
    const payload={decision,expected_record_version:r.record_version,comment:comment||null};
    return reviewsApi.decide(r.review_id,{...payload,idempotency_key:keyFor(payload)});
  },onError:()=>{setPending(undefined);refresh();},onSuccess:async()=>{
    setPending(undefined);
    await cache.invalidateQueries({queryKey:['m2d-review',identity,r.review_id]});
    await cache.invalidateQueries({queryKey:['m2d-review-list',identity]});
    await cache.invalidateQueries({queryKey:['stage1-results',identity,r.workflow_run_id]});
    refresh();
  }});
  const factsChange = pending === 'SUBMIT_CORRECTION' || pending === 'ADD_INFORMATION' || pending === 'CONTINUE_SUCCESSOR';
  const official = result.data?.analysis_snapshot_id === r.analysis_snapshot_id ? result.data : undefined;
  const evidence = official?.retrieval?.evidence_pack.items ?? [];
  return <section data-testid="review-detail" aria-label={t('ui.m2d.detail')}>
    <Card title={t('ui.m2d.detail')} extra={<Link to="/reviews">{t('ui.m2d.back')}</Link>}>
      <Tag data-testid="review-state">{code(r.presentation_state)}</Tag><Typography.Text code data-testid="review-id">{r.review_id}</Typography.Text>
      <Descriptions column={2} bordered items={[
        {key:'project',label:t('ui.m2d.projectFilter'),children:r.project_id},
        {key:'run',label:t('ui.m2d.run'),children:<Link to={`/results/${r.workflow_run_id}`}>{r.workflow_run_id}</Link>},
        {key:'snapshot',label:t('snapshot'),children:r.analysis_snapshot_id},
        {key:'stage',label:t('ui.m2d.stageFilter'),children:r.owning_stage},
        {key:'role',label:t('ui.m2d.role'),children:r.required_role},
        {key:'object',label:t('ui.m2d.object'),children:<span>{r.object_type} · {r.object_id}</span>},
        {key:'version',label:t('version'),children:r.record_version},
        {key:'date',label:t('ui.m2d.created'),children:r.created_at},
      ]}/>
      <Space wrap>{r.reason_codes.map(value=><Tag key={value}>{code(value)}</Tag>)}</Space><p>{r.reason_summary}</p>
      <Alert type="warning" title={t('ui.m2d.impact')} description={t('ui.m2d.noBypass')}/>
      {r.capability_gap && <Alert type="info" title={t('ui.m2d.gap')} description={r.capability_gap}/>}
      {r.continuation_status==='RESUME_PENDING' && <Alert type="warning" title={t('ui.m2d.resumePending')}/>}
      <Button onClick={()=>setContextOpen(true)}>{t('ui.m2d.sources')}</Button>
    </Card>
    <Card title={t('ui.m2d.choices')}>
      {r.choices.length ? r.choices.map(value=><Card size="small" key={value.object_id}>
        <Typography.Text>{value.display_value}</Typography.Text><p>{value.object_type} · {value.object_id}</p>
        <p>{t('ui.m2d.sourceDocument')}: {value.source_document_ids.join(' · ')}</p>
        <p>{t('ui.m2d.sourceTrace')}: {value.source_trace_ids.join(' · ')}</p>
        {value.structured_provenance.map(p=><p key={`${p.source_ref}:${p.source_locator}`}>{p.source_type} · {p.source_ref} · {p.source_version} · {p.source_locator} · {p.actor_ref}</p>)}
      </Card>) : <p>{t('ui.m2d.noChoices')}</p>}
      {r.allowed_actions.includes('SUBMIT_CORRECTION') && <Select aria-label={t('ui.m2d.selectChoice')} placeholder={t('ui.m2d.selectChoice')} style={{width:'100%'}} value={choice} onChange={setChoice} options={r.choices.map(value=>({value:value.object_id,label:value.display_value}))}/>}
      {r.allowed_actions.includes('ADD_INFORMATION') && <label>{t('ui.m2d.clarification')}<Input.TextArea aria-label={t('ui.m2d.clarification')} maxLength={4096} value={clarification} onChange={e=>setClarification(e.target.value)}/></label>}
    </Card>
    <Card title={t('ui.m2d.actions')}>
      <label>{t('ui.m2d.comment')}<Input.TextArea aria-label={t('ui.m2d.comment')} maxLength={4096} value={comment} onChange={e=>setComment(e.target.value)}/></label>
      <Space wrap>{r.allowed_actions.map(action=><Button key={action} aria-label={code(action)} type={action==='APPROVE'?'primary':'default'} danger={action==='REJECT'} disabled={write.isPending || action==='SUBMIT_CORRECTION'&&!choice} onClick={()=>setPending(action)}>{code(action)}</Button>)}</Space>
      {!r.allowed_actions.length && <p>{t('ui.m2d.readOnly')}</p>}
      {write.error && <><ErrorState error={write.error}/>{write.error instanceof ApiError && write.error.status===409 && <Alert type="warning" title={t('ui.m2d.stale')}/>}<Button onClick={refresh}>{t('ui.m2d.refresh')}</Button></>}
    </Card>
    <Card title={t('ui.m2d.history')}><Timeline items={r.history.map(h=>({key:h.decision_id,children:<span>{code(h.decision)} · {h.decided_by} · {h.decided_at}<p>{h.comment}</p></span>}))}/></Card>
    {r.lineage && <Card title={t('ui.m2d.successor')} data-testid="review-lineage">
      <p>{r.lineage.submitted_by} · {r.lineage.created_at}</p><p>{r.lineage.comment}</p>
      <p>{t('ui.m2d.newSnapshot')}</p><Typography.Text code>{r.lineage.successor_snapshot_id}</Typography.Text>
      <Space><Link to={`/results/${r.lineage.source_workflow_run_id}`}>{t('ui.m2d.oldResult')}</Link><Link to={`/results/${r.lineage.successor_workflow_run_id}`}>{t('ui.m2d.newResult')}</Link></Space>
    </Card>}
    <Modal open={!!pending} title={pending ? code(pending) : t('ui.m2d.actions')} okText={t('ui.m2d.confirm')} cancelText={t('ui.m2d.cancel')} confirmLoading={write.isPending} onCancel={()=>setPending(undefined)} onOk={()=>pending&&write.mutate(pending)}>
      <p>{t(factsChange?'ui.m2d.newSnapshot':'ui.m2d.sameSnapshot')}</p><p>{t('ui.m2d.noBypass')}</p>
    </Modal>
    <Drawer open={contextOpen} title={t('ui.m2d.sources')} onClose={()=>setContextOpen(false)} size="large">
      {result.isPending ? <LoadingState/> : result.error ? <ErrorState error={result.error}/> : <>
        <p>{t('ui.m2c.officialNotice')}</p>
        {official?.legal_basis.map(b=><Card key={b.legal_basis_id} title={b.citation_locator}><p>{b.summary}</p><p>{b.official_source}</p><p>{b.legal_basis_id}</p></Card>)}
        <EvidenceTable items={evidence} open={item=>setSelectedEvidence(item.evidence_item_id)}/>
        {official?.documents.map(d=><p key={d.document_version_id}>{d.name} · {d.document_version_id} · {d.parse_run_id}</p>)}
        <p>{r.evidence_refs.join(' · ')}</p><p>{r.legal_basis_refs.join(' · ')}</p>
      </>}
    </Drawer>
    <SourceCitationDrawer item={evidence.find(item=>item.evidence_item_id===selectedEvidence)} close={()=>setSelectedEvidence(undefined)}/>
  </section>;
}
