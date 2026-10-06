import { useState, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Card } from 'antd';
import { useTranslation } from 'react-i18next';
import type { Session, AuthorizedContext } from '../../api/contracts';
import { ErrorState, LoadingState } from '../../components/States';
import { IntakeFeature } from './IntakeFeature';
import { draftFacts, intakeApi } from './persistence';

export function ProductionIntake({ session, context }: { session: Session; context?: AuthorizedContext }) {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const project = params.get('project_id');
  const [name, setName] = useState('');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [createKey, setCreateKey] = useState(crypto.randomUUID());
  const cache = useQueryClient();
  const saveAttempt = useRef<{ payload: string; key: string } | null>(null);
  const queryKey = ['m2a-intake', session.identity_key, project];
  const saved = useQuery({ queryKey, queryFn: ({ signal }) => intakeApi.read(project!, signal), enabled: !!project, retry: false, gcTime: 0 });
  const create = useMutation({ mutationFn: () => intakeApi.create(name, date, createKey), retry: false, onSuccess: record => { cache.setQueryData(['m2a-intake', session.identity_key, record.project_id], record); setParams({ project_id: record.project_id }); setCreateKey(crypto.randomUUID()); } });
  return <>
    <Card title={t('ui.m2a.create')}><form className="m1-form" onSubmit={event => { event.preventDefault(); create.mutate(); }}>
      <label>{t('ui.m2a.projectName')}<input value={name} maxLength={200} required onChange={event => { setName(event.target.value); setCreateKey(crypto.randomUUID()); }}/></label>
      <label>{t('ui.m2a.asOf')}<input type="date" required value={date} onChange={event => { setDate(event.target.value); setCreateKey(crypto.randomUUID()); }}/></label>
      <Button htmlType="submit" loading={create.isPending} disabled={!name.trim()}>{t('ui.m2a.create')}</Button>
    </form>{create.error && <ErrorState error={create.error}/>}</Card>
    {project ? saved.isPending ? <LoadingState/> : saved.error ? <ErrorState error={saved.error}/> : saved.data && <>
      <Alert type="info" title={t('ui.m2a.saved', { version: saved.data.version, status: saved.data.status })}/>
      <p data-testid="intake-project-id">{saved.data.project_id}</p>
      <IntakeFeature key={`${session.identity_key}:${project}:${saved.data.version}`} session={session} persistence={{ record: saved.data,
        save: async draft => { const facts = draftFacts(saved.data, draft); const payload = JSON.stringify([saved.data.project_id, saved.data.version, facts]); if (saveAttempt.current?.payload !== payload) saveAttempt.current = { payload, key: crypto.randomUUID() }; const value = await intakeApi.save(saved.data, facts, saveAttempt.current.key); cache.setQueryData(queryKey, value); },
        confirm: async () => { const value = await intakeApi.confirm(saved.data); cache.setQueryData(queryKey, value); return value; } }}/>
    </> : context && <IntakeFeature key={`${session.identity_key}:${context.project_id}:${context.analysis_snapshot_id}`} session={session} context={context}/>}
  </>;
}
