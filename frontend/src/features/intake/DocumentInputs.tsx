import { useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Alert, Button, Progress } from 'antd';
import { useTranslation } from 'react-i18next';
import { ErrorState, LoadingState } from '../../components/States';
import type { IntakePersistence } from './persistence';
import { documentApi } from './documentApi';

export function DocumentInputs({ persistence, identity, dirty }: { persistence: IntakePersistence; identity: string; dirty: boolean }) {
  const { t } = useTranslation();
  const record = persistence.record;
  const key = ['m2b-documents', identity, record.project_id, record.version];
  const docs = useQuery({ queryKey: key, queryFn: ({ signal }) => documentApi.list(record.project_id, signal), retry: false, gcTime: 0 });
  const policy = useQuery({ queryKey: ['m2b-upload-policy', identity, record.project_id], queryFn: ({ signal }) => documentApi.policy(record.project_id, signal), retry: false, gcTime: 0 });
  const [file, setFile] = useState<File>();
  const [progress, setProgress] = useState(0);
  const uploadKey = useRef(crypto.randomUUID());
  const operation = useMutation({ mutationFn: async (input: { action: 'upload' | 'parse' | 'unlink' | 'supersede'; versionId?: string }) => {
    if (input.action === 'upload') await documentApi.upload(record.project_id, record.version, file!, uploadKey.current, setProgress);
    else await documentApi.action(record.project_id, record.version, crypto.randomUUID(), input.action, input.versionId);
    await docs.refetch(); await persistence.refresh?.();
    if (input.action === 'upload') { setFile(undefined); uploadKey.current = crypto.randomUUID(); }
  }, retry: false });
  const editable = record.status === 'DRAFT' && !dirty && !operation.isPending;
  const statuses: Record<string, string> = { STORED: 'ui.m2b.stored', ACCEPTED: 'ui.m2b.pending', RUNNING: 'ui.m2b.parsing', COMPLETED: 'ui.m2b.parsed', FAILED: 'ui.m2b.failed', PASS: 'ui.m2b.qualityPass', WARNING: 'ui.m2b.qualityWarning', REVIEW_REQUIRED: 'ui.m2b.review' };
  return <section aria-label={t('ui.m2b.documents')}>
    {dirty && <Alert type="warning" title={t('ui.m2b.saveFirst')}/>}
    {policy.data?.status === 'CAPABILITY_NOT_CONFIGURED' && <Alert type="warning" title={t('ui.m2b.unavailable')}/>}
    {record.status === 'CONFIRMED' && <><Alert type="info" title={t('ui.m2b.pinned')}/><Button loading={operation.isPending} onClick={() => operation.mutate({ action: 'supersede' })}>{t('ui.m2b.newVersion')}</Button></>}
    <label>{t('ui.m2b.select')}<input type="file" disabled={!editable || policy.data?.status !== 'AVAILABLE'} accept={policy.data?.allowed_types.map(x => x.extension).join(',')} onChange={event => { setFile(event.target.files?.[0]); uploadKey.current = crypto.randomUUID(); setProgress(0); }}/></label>
    {policy.data?.max_size_bytes && <p>{t('ui.m2b.limit', { bytes: policy.data.max_size_bytes })}</p>}
    <Button disabled={!editable || !file || policy.data?.status !== 'AVAILABLE'} loading={operation.isPending} onClick={() => operation.mutate({ action: 'upload' })}>{t('ui.m2b.upload')}</Button>
    {operation.isPending && <Progress percent={progress}/>}
    {[docs, policy].map((query, i) => query.isPending ? <LoadingState key={i}/> : query.error && <ErrorState key={i} error={query.error}/>)}
    {operation.error && <ErrorState error={operation.error}/>}
    <ul>{docs.data?.items.map(row => <li key={row.document_version_id} data-testid="document-input">
      <strong>{row.filename}</strong><p>{t(statuses[row.parse_status])} · {row.quality_status && t(statuses[row.quality_status])}</p>
      <details><summary>{t('ui.m2b.source')}</summary><dl><dt>{t('ui.m2b.version')}</dt><dd>{row.document_version_id}</dd><dt>{t('ui.m2b.hash')}</dt><dd>{row.content_hash}</dd><dt>{t('ui.m2b.parseRef')}</dt><dd>{row.parse_run_id}</dd></dl></details>
      {row.error_code && <p>{row.error_code}</p>}
      <Button disabled={!editable || row.parse_status === 'COMPLETED' || row.parse_status === 'RUNNING'} loading={operation.isPending} onClick={() => operation.mutate({ action: 'parse', versionId: row.document_version_id })}>{t(row.parse_status === 'FAILED' ? 'ui.m2b.retry' : 'ui.m2b.parse')}</Button>
      <Button disabled={!editable} onClick={() => operation.mutate({ action: 'unlink', versionId: row.document_version_id })}>{t('ui.m2b.remove')}</Button>
    </li>)}</ul>
    {!docs.isPending && docs.data?.items.length === 0 && <p>{t('ui.m2b.empty')}</p>}
    <Button disabled={operation.isPending} onClick={() => docs.refetch()}>{t('ui.m2b.refresh')}</Button>
    <p>{t('ui.m2b.readiness')}</p>
  </section>;
}
