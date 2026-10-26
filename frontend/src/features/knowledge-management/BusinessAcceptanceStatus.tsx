import { Alert, Button, Card, Space, Tag } from 'antd';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { request } from '../../api/client';
import { ErrorState } from '../../components/States';

type Readiness = {
  entry: string;
  model_configuration: { providers: number; active_deployments: number };
  native_processing: { status: string; reason: string };
  legal_accuracy_execution: string;
};

/** Operational prerequisites only; never infers a formal result or legal approval. */
export function BusinessAcceptanceStatus({ identity }: { identity: string }) {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: ['business-acceptance-readiness', identity],
    queryFn: ({ signal }) => request<Readiness>('/api/v1/acceptance-readiness', { signal }), retry: false });
  return <Card title={t('ui.acceptance.prerequisites')}>
    <Space orientation="vertical">
      <Alert type="warning" title={t('ui.acceptance.notLegalAcceptance')} description={t('ui.acceptance.requiredEvidence')} />
      {query.error && <ErrorState error={query.error} />}
      {query.data && <>
        <span>{t('ui.acceptance.modelCount', query.data.model_configuration)}</span>
        <Tag>{t('ui.acceptance.processing')}: {query.data.native_processing.status}</Tag>
        <p>{t('ui.acceptance.processingHeld')}</p>
        <span>{t('ui.acceptance.legalAccuracy')}: {query.data.legal_accuracy_execution}</span>
      </>}
      <Space wrap>
        <Link to="/intake">{t('ui.acceptance.businessInput')}</Link>
        <Link to="/admin?admin_resource=knowledge-management">{t('ui.acceptance.lawUpload')}</Link>
        <Link to="/admin?admin_resource=models">{t('ui.acceptance.modelSetup')}</Link>
        <Link to="/admin?admin_resource=regulatory-acceptance">{t('ui.acceptance.expertRecords')}</Link>
        <Link to="/reviews">{t('ui.acceptance.reviewCenter')}</Link>
        <Button onClick={() => void query.refetch()}>{t('ui.acceptance.refresh')}</Button>
      </Space>
    </Space>
  </Card>;
}
