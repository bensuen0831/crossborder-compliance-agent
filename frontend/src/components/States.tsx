import { Alert, Button, Empty, Result, Skeleton, Space, Tag, Typography } from 'antd';
import { useTranslation } from 'react-i18next';
import { ApiError } from '../api/client';

export function LoadingState() {
  const { t } = useTranslation();
  return <div role="status" aria-label={t('loading')}><Skeleton active paragraph={{ rows: 4 }} /></div>;
}
export function EmptyState({ title, description }: { title: string; description?: string }) {
  return <Empty description={<><Typography.Title level={4}>{title}</Typography.Title>{description}</>} />;
}
export function PermissionDenied() {
  const { t } = useTranslation();
  return <Result status="403" title={t('permission')} subTitle={t('permissionHint')} />;
}
export function ErrorState({ error, retry }: { error: Error; retry?: () => void }) {
  const { t } = useTranslation();
  if (error instanceof ApiError && [401, 403].includes(error.status)) return <PermissionDenied />;
  return <Alert type="error" showIcon title={t('error')} description={<Space orientation="vertical">
    <span>{error.message}</span>
    {error instanceof ApiError && error.traceId && <Typography.Text code>{t('trace')}: {error.traceId}</Typography.Text>}
    {retry && <Button onClick={retry}>{t('retry')}</Button>}
  </Space>} />;
}
export function FeatureGate({ label }: { label: string }) {
  const { t } = useTranslation();
  return <Space orientation="vertical" size={2} className="feature-gate"><span>{label}</span><Tag>{t('comingSoon')}</Tag></Space>;
}
