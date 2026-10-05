import { useQuery } from '@tanstack/react-query';
import { Alert, Card, Descriptions, Space, Tag } from 'antd';
import { useTranslation } from 'react-i18next';
import { api } from '../api/client';
import type { Session } from '../api/contracts';
import { EmptyState, ErrorState, LoadingState } from './States';

export function StatusHealthIndicator() {
  const { t } = useTranslation();
  const health = useQuery({ queryKey: ['health'], queryFn: ({ signal }) => api.health(signal), refetchInterval: 30000, retry: false });
  return <Tag color={health.data?.status === 'ok' ? 'green' : 'orange'}>{health.data?.status === 'ok' ? t('backendStatus') : t('backendUnavailable')}</Tag>;
}
function VersionStatus({ session, id }: { session: Session; id: string }) {
  const { t } = useTranslation();
  const result = useQuery({ queryKey: ['readiness', session.identity_key, id], queryFn: ({ signal }) => api.readiness(id, signal), retry: false, staleTime: 0, gcTime: 0 });
  return <Card title={t('published')} extra={result.data && <Tag>{result.data.status}</Tag>}>
    {result.isLoading ? <LoadingState /> : result.error ? <ErrorState error={result.error} /> : result.data && <>
      <Descriptions column={1} size="small" items={[
        { key: 'version', label: t('version'), children: id },
        { key: 'index', label: t('ui.indexVersion'), children: result.data.index_version_id ?? t('notAvailable') },
        { key: 'cache', label: t('ui.cacheGeneration'), children: result.data.cache_generation ?? t('notAvailable') },
        { key: 'embedding', label: t('ui.embeddingConfig'), children: result.data.embedding_config_id ?? t('notAvailable') },
        { key: 'vector', label: t('ui.vector'), children: result.data.embedding_config_id ? t('ui.vectorConfigured') : t('ui.vectorNotConfigured') },
      ]} />
      <Space wrap>{Object.entries(result.data.checks ?? {}).map(([check, ok]) => <Tag key={check} color={ok ? 'green' : 'orange'}>{check}: {ok ? t('ui.checkPass') : t('ui.checkFail')}</Tag>)}</Space>
      {result.data.reason_codes.length > 0 && <Alert type="warning" title={result.data.reason_codes.join(' · ')} />}
    </>}
  </Card>;
}
export function RuntimeStatus({ session, versions }: { session: Session; versions: string[] }) {
  const { t } = useTranslation();
  const allowed = session.permissions.includes('knowledge:admin');
  return <Space orientation="vertical" size="large" className="full-width">
    <Alert type="info" showIcon title={t('healthNote')} />
    {!allowed ? <Alert type="info" title={t('runtimeRestricted')} /> : versions.length === 0 ?
      <EmptyState title={t('noReadiness')} /> : versions.map((id) => <VersionStatus session={session} id={id} key={id} />)}
  </Space>;
}
