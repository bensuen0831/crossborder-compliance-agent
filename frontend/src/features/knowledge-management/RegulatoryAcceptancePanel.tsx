import { useState } from 'react';
import { Alert, Button, Card, Descriptions, Input, Space } from 'antd';
import { useTranslation } from 'react-i18next';
import type { AdminClient } from '../admin/client';
import type { AdminSession } from '../admin/contracts';
import { ErrorState } from '../../components/States';

type RecordView = { version_id: string; kind: string; lifecycle: string; record_version: number;
  created_by: string; approved_by: string | null; approved_at: string | null; payload_sha256: string; payload: Record<string, unknown> };
type Readiness = { decision: string; dataset_kind: string; reason_codes: string[]; checks: Record<string, boolean>;
  real_regulatory_legal_acceptance: string };

/** Existing F0 records only; imported files never supply approval authority. */
export function RegulatoryAcceptancePanel({ client, session }: { client: AdminClient; session: AdminSession }) {
  const { t } = useTranslation();
  const [input, setInput] = useState<string>();
  const [identity, setIdentity] = useState('');
  const [caseId, setCaseId] = useState('');
  const [goldId, setGoldId] = useState('');
  const [record, setRecord] = useState<RecordView>();
  const [readiness, setReadiness] = useState<Readiness>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error>();
  const scopes = session.backendScopes;
  const base = '/admin/knowledge-management/acceptance';
  const act = async (work: () => Promise<void>) => {
    setError(undefined); setBusy(true);
    try { await work(); } catch (cause) { setError(cause instanceof Error ? cause : new Error('ACCEPTANCE_UNAVAILABLE')); }
    finally { setBusy(false); }
  };
  const transition = (action: string) => act(async () => {
    setRecord(await client.request<RecordView>(`${base}/records/${encodeURIComponent(record!.version_id)}/${action}`, 'POST', { expected_record_version: record!.record_version }));
  });
  return <Card title={t('ui.acceptance.expertRecords')}><Space orientation="vertical" style={{ width: '100%' }}>
    <Alert type="warning" title={t('ui.acceptance.notLegalAcceptance')} description={t('ui.acceptance.expertBoundary')} />
    {error && <ErrorState error={error} />}
    <label>{t('ui.acceptance.recordFile')}<input type="file" accept="application/json,.json" onChange={event => {
      const file = event.target.files?.[0]; setInput(undefined);
      if (file && file.size <= 128 * 1024) void file.text().then(setInput);
    }}/></label>
    <Button disabled={busy || !input || !scopes.includes('knowledge:acceptance:write')} onClick={() => void act(async () => {
      const value: unknown = JSON.parse(input!);
      if (!value || typeof value !== 'object' || !('payload' in value)
        || (value.payload as Record<string, unknown>)?.dataset_kind !== 'L2_REAL_REGULATORY') throw new Error('REAL_REGULATORY_DRAFT_REQUIRED');
      const saved = await client.request<RecordView>(`${base}/records`, 'POST', value);
      setRecord(saved); setIdentity(saved.version_id); setInput(undefined);
    })}>{t('ui.acceptance.importDraft')}</Button>
    <Input aria-label={t('ui.acceptance.recordVersion')} value={identity} onChange={e => setIdentity(e.target.value)} />
    <Button disabled={busy || !identity || !scopes.includes('knowledge:acceptance:read')} onClick={() => void act(async () => setRecord(await client.request<RecordView>(`${base}/records/${encodeURIComponent(identity)}`)))}>{t('ui.acceptance.readRecord')}</Button>
    {record && <>
      <Descriptions column={1} items={[
        { key: 'id', label: t('ui.acceptance.recordVersion'), children: record.version_id },
        { key: 'kind', label: t('ui.acceptance.recordType'), children: record.kind },
        { key: 'state', label: t('ui.acceptance.recordState'), children: record.lifecycle },
        { key: 'author', label: t('ui.acceptance.recordAuthor'), children: record.created_by },
        { key: 'reviewer', label: t('ui.acceptance.recordReviewer'), children: record.approved_by ?? t('ui.acceptance.pendingApproval') },
        { key: 'time', label: t('ui.acceptance.recordApprovalDate'), children: record.approved_at ?? t('ui.acceptance.pendingApproval') },
        { key: 'digest', label: t('ui.acceptance.recordDigest'), children: record.payload_sha256 },
      ]} />
      <pre>{JSON.stringify(record.payload, null, 2)}</pre>
      <Space>
        {record.lifecycle === 'DRAFT' && scopes.includes('knowledge:acceptance:write') && <Button disabled={busy} onClick={() => void transition('submit-review')}>{t('ui.acceptance.submitReview')}</Button>}
        {record.lifecycle === 'PENDING_REVIEW' && scopes.includes('knowledge:acceptance:review') && <Button disabled={busy} onClick={() => void transition('approve')}>{t('ui.acceptance.approveRecord')}</Button>}
        {record.lifecycle === 'APPROVED' && scopes.includes('knowledge:acceptance:publish') && <Button disabled={busy} onClick={() => void transition('publish')}>{t('ui.acceptance.publishRecord')}</Button>}
      </Space>
    </>}
    <Input aria-label={t('ui.acceptance.caseVersion')} value={caseId} onChange={e => setCaseId(e.target.value)} />
    <Input aria-label={t('ui.acceptance.goldVersion')} value={goldId} onChange={e => setGoldId(e.target.value)} />
    <Button disabled={busy || !caseId || !scopes.includes('knowledge:acceptance:read')} onClick={() => void act(async () => {
      const query = goldId ? `?gold_review_version_id=${encodeURIComponent(goldId)}` : '';
      setReadiness(await client.request<Readiness>(`${base}/cases/${encodeURIComponent(caseId)}/readiness${query}`));
    })}>{t('ui.acceptance.checkGold')}</Button>
    {readiness && <Alert type="info" title={readiness.decision} description={<>
      <p>{readiness.dataset_kind} · {readiness.real_regulatory_legal_acceptance}</p>
      <ul>{Object.entries(readiness.checks).map(([key, passed]) => <li key={key}>{key}: {String(passed)}</li>)}</ul>
      <p>{readiness.reason_codes.join(' · ')}</p>
    </>} />}
  </Space></Card>;
}
