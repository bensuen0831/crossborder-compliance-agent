import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Card, Drawer, Progress, Space, Statistic, Steps, Table, Tag, Typography } from 'antd';
import { useTranslation } from 'react-i18next';
import { m1Api } from '../intake/api';
import { currentLocale } from '../../i18n';
import { ErrorState, LoadingState } from '../../components/States';
import { EvidenceTable, SourceCitationDrawer } from '../../components/Evidence';
import { optionLabel } from '../intake/contracts';
import { stage1Read, type Stage1Result } from './api';

const colors: Record<string, string> = { LOW: 'success', MEDIUM: 'warning', HIGH: 'error', CRITICAL: 'error', UNKNOWN: 'default', DIRECT_TRANSFER_ALLOWED: 'success', CONDITIONAL_TRANSFER_ALLOWED: 'warning', TRANSFER_NOT_ALLOWED_OR_LOCALIZATION_REQUIRED: 'error', REVIEW_REQUIRED: 'warning', CONFLICTED: 'warning', REQUIRED: 'blue', CONDITIONAL: 'gold', RECOMMENDED: 'cyan', NOT_APPLICABLE: 'default' };
export function Stage1Workspace({ runId, identity }: { runId: string; identity: string }) {
  const query = useQuery({ queryKey: ['stage1-results', identity, runId], queryFn: ({ signal }) => stage1Read(runId, signal), retry: false, gcTime: 0 });
  const { t } = useTranslation();
  return <section aria-label={t('ui.m2c.workspace')} data-testid="stage1-workspace">
    {query.isPending ? <LoadingState/> : query.error ? <ErrorState error={query.error} retry={() => void query.refetch()}/> : <Stage1View result={query.data} identity={identity}/>}
  </section>;
}

export function Stage1View({ result: r, identity }: { result: Stage1Result; identity: string }) {
  const { t, i18n } = useTranslation();
  const [basisOpen, setBasisOpen] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState<string>();
  const [documentSelection, setDocumentSelection] = useState(false);
  const [finished, setFinished] = useState(false);
  const metadata = useQuery({ queryKey: ['result-jurisdictions', identity, i18n.language], queryFn: ({ signal }) => m1Api.metadata('jurisdictions', currentLocale(), signal), retry: false });
  const label = (id: string) => { const item = metadata.data?.items.find(v => v.jurisdiction_id === id || v.definition_id === id); return item ? optionLabel(item) : id; };
  const code = (value?: string | null) => value ? <Tag color={colors[value]}>{t(`ui.m2c.codes.${value}`, { defaultValue: value })}</Tag> : <span>{t('ui.m2c.unassessed')}</span>;
  const cross = r.cross_border?.items[0];
  const risks = r.risk?.items ?? [];
  const final = r.final_path?.items[0];
  const documents = r.document_requirements?.items ?? [];
  const evidence = r.retrieval?.evidence_pack.items ?? [];
  const links = r.flows.map(flow => ({ id: flow.flow_edge_id, source: r.flow_nodes.find(n => n.flow_node_id === flow.source_node_id)?.name ?? flow.source_node_id, target: r.flow_nodes.find(n => n.flow_node_id === flow.target_node_id)?.name ?? flow.target_node_id }));
  const classFor = (id: string) => r.classification.find(c => c.data_item_id === id);
  const crossFor = (id: string) => r.cross_border?.data_item_ids.includes(id) ? cross : undefined;
  const scopedDocs = (id: string) => r.document_requirements?.data_item_ids.includes(id) ? documents : [];
  const scopedFinal = (id: string) => r.final_path?.data_item_ids.includes(id) ? final : undefined;
  const scopedRisks = (id: string) => r.risk?.data_item_ids.includes(id) ? risks : [];
  return <div className="stage1-workspace">
    <Card title={t('ui.m2c.workspace')} extra={<Button onClick={() => setBasisOpen(true)}>{t('ui.m2c.legalEvidence')}</Button>}>
      <Typography.Title level={3}>{r.project.name}</Typography.Title>
      <Space wrap>{code(r.status)}<span>{r.project.analysis_as_of_date}</span><span>{t('ui.m2c.mode')}: {r.mode}</span></Space>
      <p data-testid="stage1-snapshot-id">{r.analysis_snapshot_id}</p><p data-testid="stage1-run-id">{r.workflow_run_id}</p>
      {r.status !== 'COMPLETED' && <Alert type="warning" title={t('ui.m2c.partial')} description={[...r.reason_codes, ...r.capability_gaps].join(' · ')}/>}
      {r.capability_gaps.map(gap => <Alert key={gap} type="warning" title={gap}/>)}
      {r.review_id && <Alert type="warning" title={t('ui.m2c.review')} description={r.review_id}/>}
    </Card>
    <div className="stage1-kpis"><Card><Statistic title={t('ui.m2c.dataItems')} value={r.data_items.length}/></Card><Card><Statistic title={t('ui.m2c.documents')} value={r.documents.length}/></Card><Card><Statistic title={t('ui.m2c.evidence')} value={evidence.length}/></Card><Card><Statistic title={t('ui.m2c.requirements')} value={documents.filter(d => d.requirement_level === 'REQUIRED').length}/></Card></div>
    <div className="stage1-columns"><Card title={t('ui.m2c.workflow')}><Steps direction="vertical" size="small" items={r.steps.map(step => ({ key: step, title: t(`ui.m2c.steps.${step}`, { defaultValue: step }), status: r.completed_steps.includes(step) ? 'finish' : r.current_step === step ? 'process' : 'wait' }))}/></Card>
      <div className="stage1-main">
        <Card title={t('ui.m2c.transferMap')}>
          <p>{t('ui.m2c.mapNotice')}</p>
          <svg role="img" aria-label={t('ui.m2c.transferMap')} viewBox={`0 0 800 ${Math.max(120, links.length * 90)}`} className="stage1-transfer-map">
            <defs><marker id="transfer-arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#2563eb"/></marker></defs>
            {links.map((link, index) => <g key={link.id}><rect x="10" y={index * 90 + 20} width="280" height="48" rx="8" fill="#eff6ff"/><text x="25" y={index * 90 + 50}>{link.source}</text><line x1="295" y1={index * 90 + 44} x2="495" y2={index * 90 + 44} stroke="#2563eb" strokeWidth="2" markerEnd="url(#transfer-arrow)"/><rect x="510" y={index * 90 + 20} width="280" height="48" rx="8" fill="#eff6ff"/><text x="525" y={index * 90 + 50}>{link.target}</text></g>)}
            {!links.length && <text x="20" y="55">{t('ui.m2c.noFlow')}</text>}
          </svg>
          {cross && <><Space wrap><span>{t('ui.m2c.source')}: {cross.source_jurisdiction_ids.map(label).join(' · ')}</span><span>→</span><span>{t('ui.m2c.destination')}: {cross.destination_jurisdiction_ids.map(label).join(' · ')}</span></Space><p>{code(cross.status)}</p><Space wrap>{cross.reason_codes.map(reason => <Tag key={reason}>{t(`ui.m2c.codes.${reason}`, { defaultValue: reason })}</Tag>)}</Space></>}
        </Card>
        <Card title={t('ui.m2c.risk')}><p>{t('ui.m2c.riskNotice')}</p>{risks.length ? risks.map(risk => <div key={risk.risk_assessment_id}><Space>{code(risk.risk_level)}<span>{risk.score ?? t('notAvailable')}</span></Space>{risk.dimensions.map(d => <div key={d.code}><span>{d.code} · {d.score ?? t('notAvailable')}</span>{d.score !== null && <Progress percent={Number(d.score)} showInfo={false} status="active"/>}</div>)}</div>) : <p>{t('ui.m2c.unassessed')}</p>}</Card>
        <Card title={t('ui.m2c.path')}><p>{t('ui.m2c.pathNotice')}</p>{final ? <>{code(final.status)}<Steps direction="vertical" size="small" items={final.actions.map(action => ({ key: action.entry_id, title: action.action_code, description: <span>{t('ui.m2c.actionPending')} · {action.conditions.map(c => c.code).join(' · ')}</span>, status: 'wait' }))}/>{final.required_conditions.map(c => <Tag key={c.entry_id}>{c.code} · {c.evaluation}</Tag>)}</> : <p>{t('ui.m2c.unassessed')}</p>}</Card>
      </div>
    </div>
    <Card title={t('ui.m2c.inventory')}><Table dataSource={r.data_items} rowKey="data_item_id" scroll={{ x: 1500 }} pagination={{ pageSize: 10 }} columns={[
      { title: t('ui.m2c.dataItem'), dataIndex: 'name' },
      { title: t('ui.m2c.classification'), render: (_, row) => classFor(row.data_item_id)?.category_ids.join(' · ') ?? t('ui.m2c.unassessed') },
      { title: t('ui.m2c.level'), render: (_, row) => classFor(row.data_item_id)?.level_id ?? t('ui.m2c.unassessed') },
      { title: t('ui.m2c.source'), render: (_, row) => crossFor(row.data_item_id)?.source_jurisdiction_ids.map(label).join(' · ') ?? t('notAvailable') },
      { title: t('ui.m2c.destination'), render: (_, row) => crossFor(row.data_item_id)?.destination_jurisdiction_ids.map(label).join(' · ') ?? t('notAvailable') },
      { title: t('ui.m2c.crossBorder'), render: (_, row) => code(crossFor(row.data_item_id)?.status) },
      { title: t('ui.m2c.localization'), render: (_, row) => crossFor(row.data_item_id) ? t(crossFor(row.data_item_id)!.localization_required ? 'ui.m2c.yes' : 'ui.m2c.no') : t('ui.m2c.unassessed') },
      { title: t('ui.m2c.legalBasis'), render: (_, row) => crossFor(row.data_item_id) ? <Button type="link" onClick={() => setBasisOpen(true)}>{crossFor(row.data_item_id)!.legal_basis_ids.length}</Button> : t('notAvailable') },
      { title: t('ui.m2c.risk'), render: (_, row) => scopedRisks(row.data_item_id).map(risk => <span key={risk.risk_assessment_id}>{code(risk.risk_level)}</span>) },
      { title: t('ui.m2c.measures'), render: (_, row) => scopedFinal(row.data_item_id)?.actions.map(a => a.action_code).join(' · ') ?? t('ui.m2c.unassessed') },
      { title: t('ui.m2c.requirements'), render: (_, row) => scopedDocs(row.data_item_id).filter(d => d.requirement_level !== 'NOT_APPLICABLE').map(d => <span key={d.document_requirement_id}>{d.name} {code(d.requirement_level)}</span>) },
      { title: t('ui.m2c.review'), render: (_, row) => code(row.review_required || crossFor(row.data_item_id)?.review_required ? 'REVIEW_REQUIRED' : classFor(row.data_item_id)?.status) },
    ]}/></Card>
    <Card title={t('ui.m2c.documents')}><Table rowKey="document_version_id" dataSource={r.documents} pagination={false} columns={[{title:t('ui.m2c.name'),dataIndex:'name'},{title:t('ui.m2c.version'),dataIndex:'version'},{title:t('ui.m2c.parseStatus'),dataIndex:'parse_status'},{title:t('ui.m2c.parseRun'),dataIndex:'parse_run_id'}]}/></Card>
    <Card title={t('ui.m2c.obligations')}><Table rowKey="obligation_id" dataSource={r.obligation?.items ?? []} columns={[{title:t('ui.m2c.code'),dataIndex:'obligation_code'},{title:t('ui.m2c.effect'),dataIndex:'legal_effect'},{title:t('ui.m2c.fulfillment'),dataIndex:'fulfillment_state'}]}/></Card>
    <Card title={t('ui.m2c.regulations')}>{r.applicability.map(a => <p key={a.applicability_result_id}>{a.regulation_document_id} · {a.regulation_version_ref} {code(a.applicability_status)}</p>)}</Card>
    <Card title={t('ui.m2c.recommendation')}>{r.recommendation?.items.map(item => <p key={item.recommendation_id}>{code(item.status)} · {item.selected_candidate_id ?? t('ui.m2c.unassessed')}</p>)}</Card>
    <Card title={t('ui.m2c.requirements')}><p>{t('ui.m2c.stage2Boundary')}</p>{r.document_requirements?.review_required && <Alert type="warning" title={t('ui.m2c.review')}/>}
      <Table rowKey="document_requirement_id" dataSource={documents} pagination={false} columns={[{title:t('ui.m2c.name'),dataIndex:'name'},{title:t('ui.m2c.requirementLevel'),render:(_,d)=>code(d.requirement_level)},{title:t('ui.m2c.template'),render:(_,d)=>t(d.template_version_id ? 'ui.m2c.available':'ui.m2c.unavailable')},{title:t('ui.m2c.conditions'),render:(_,d)=>d.conditions.map(c=>c.code).join(' · ')}]}/>
      <Space><Button onClick={() => setFinished(true)}>{t('ui.m2c.finish')}</Button><Button onClick={() => setDocumentSelection(true)} disabled={r.status !== 'COMPLETED' || !documents.length || r.document_requirements?.review_required}>{t('ui.m2c.chooseDocuments')}</Button></Space>
      {finished && <Alert type="success" title={t('ui.m2c.finished')}/>}{documentSelection && <Alert type="info" title={t('ui.m2c.stage2Unavailable')}/>}
    </Card>
    <Drawer open={basisOpen} title={t('ui.m2c.legalEvidence')} onClose={() => setBasisOpen(false)} width={720}>
      <p>{t('ui.m2c.officialNotice')}</p>{r.legal_basis.map(b => <Card key={b.legal_basis_id} title={b.citation_locator}><p>{b.summary}</p><p>{b.official_source}</p><p>{b.legal_basis_id}</p></Card>)}
      <EvidenceTable items={evidence} open={item => setSelectedEvidence(item.evidence_item_id)}/>
    </Drawer>
    <SourceCitationDrawer item={evidence.find(item => item.evidence_item_id === selectedEvidence)} close={() => setSelectedEvidence(undefined)}/>
  </div>;
}
