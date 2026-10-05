import { Alert, Card, Form, Select, Space, Tag, Typography } from 'antd';
import { LockOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { api } from '../api/client';
import type { AuthorizedContext, Metadata, Scope, Session } from '../api/contracts';
import { metadataLabel } from '../features/knowledge/presentation';
import { ErrorState, LoadingState } from './States';

export function ContextSelector({ session, context, choose, scope, scopeError, scopeLoading }: {
  session: Session; context?: AuthorizedContext; choose: (id: string) => void;
  scope?: Scope; scopeError: Error | null; scopeLoading: boolean;
}) {
  const { t } = useTranslation();
  const products = useQuery({ queryKey: ['metadata', session.identity_key, 'products'], queryFn: ({ signal }) => api.metadata('products', signal), retry: false, gcTime: 0 });
  const scenarios = useQuery({ queryKey: ['metadata', session.identity_key, 'scenarios'], queryFn: ({ signal }) => api.metadata('scenarios', signal), retry: false, gcTime: 0 });
  const jurisdictions = useQuery({ queryKey: ['metadata', session.identity_key, 'jurisdictions'], queryFn: ({ signal }) => api.metadata('jurisdictions', signal), retry: false, gcTime: 0 });
  const field = (label: string, ids: string[] | undefined, metadata?: Metadata) => <Form.Item label={t(label)}>
    <Select mode="multiple" aria-label={t(label)} disabled value={ids ?? []} placeholder={t('notAvailable')}
      options={(ids ?? []).map((id) => ({ value: id, label: metadataLabel(id, metadata) }))} />
  </Form.Item>;
  return <Card title={<Space><LockOutlined />{t('context')}</Space>} className="context-card">
    <Form layout="vertical">
      <Form.Item label={t('project')}>
        <Select aria-label={t('project')} value={context?.project_id} onChange={choose} placeholder={t('chooseContext')}
          options={session.contexts.map((item) => ({ value: item.project_id, label: item.display_name }))} />
      </Form.Item>
      {scopeLoading ? <LoadingState /> : scopeError ? <ErrorState error={scopeError} /> : <div className="scope-fields">
        {field('product', scope?.allowed_product_ids, products.data)}
        {field('scenario', scope?.allowed_scenario_ids, scenarios.data)}
        {field('jurisdiction', scope?.allowed_jurisdiction_ids, jurisdictions.data)}
        {field('domain', scope?.allowed_product_domain_ids)}
      </div>}
    </Form>
    {[products, scenarios, jurisdictions].map((q, index) => q.error && <ErrorState key={index} error={q.error} />)}
    <Typography.Paragraph type="secondary" className="scope-note">{t('pinned')}</Typography.Paragraph>
    {scope && <Space wrap>{scope.allowed_scope_types.map((value) => <Tag key={value}>{value}</Tag>)}<Tag>{scope.permission_filters.join(' · ') || t('ui.noKnowledgePermissions')}</Tag></Space>}
    {scope?.review_required && <Alert type="warning" showIcon title={scope.reason_codes.join(' · ')} />}
  </Card>;
}
