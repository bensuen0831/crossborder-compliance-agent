import { Alert, Card, Descriptions, Listy, Space, Tag, Typography } from 'antd';
import { useTranslation } from 'react-i18next';
import { formatNumber } from '../features/knowledge/formatting';
import type { FallbackGuidance, Sufficiency } from '../api/contracts';

const statusColors = { SUFFICIENT: 'green', PARTIALLY_SUFFICIENT: 'gold', INSUFFICIENT: 'orange', CONFLICTED: 'red' };
export function SufficiencyBadge({ status }: { status: Sufficiency['status'] }) {
  const { t } = useTranslation();
  return <Tag color={statusColors[status]}>{t(status)} · {status}</Tag>;
}
export function SufficiencyPanel({ result }: { result: Sufficiency }) {
  const { t } = useTranslation();
  return <Card title={t('sufficiency')} extra={<SufficiencyBadge status={result.status} />}>
    <Descriptions size="small" column={1} items={[
      { key: 'evidence', label: t('evidence'), children: formatNumber(result.evidence_count) },
      { key: 'missing', label: t('missing'), children: result.missing_topics.join(', ') || '—' },
      { key: 'policy', label: t('ui.policyVersion'), children: result.policy_version },
    ]} />
    <Typography.Text type="secondary">{t('reasons')}</Typography.Text>
    <div className="reason-codes"><Space wrap>{result.reason_codes.map((code) => <Tag key={code}>{code}</Tag>)}</Space></div>
    {Object.entries(result.jurisdiction_coverage).map(([id, covered]) => <p key={id}><Typography.Text code>{id}</Typography.Text> · {covered ? t('ui.covered') : t('ui.missingCoverage')}</p>)}
  </Card>;
}
export function FallbackPanel({ guidance }: { guidance: FallbackGuidance }) {
  const { t, i18n } = useTranslation();
  const groups = [
    ['acquisition', guidance.evidence_acquisition_steps], ['jurisdictionSteps', guidance.jurisdiction_verification_steps],
    ['operationalSteps', guidance.operational_next_steps], ['conservative', guidance.conservative_controls],
  ] as const;
  return <Card title={t('fallback')}>
    <Alert type="info" showIcon title={t('fallbackNote')} />
    {groups.map(([label, actions]) => actions.length > 0 && <section key={label}>
      <Typography.Title level={5}>{t(label)}</Typography.Title>
      <Listy virtual={false} items={[...actions]} rowKey="action_code" itemRender={(action) => <div className="guidance-action">
        <Space orientation="vertical"><Typography.Text>{t(i18n.exists(`action_${action.action_code}`) ? `action_${action.action_code}` : 'ui.unknownAction')}</Typography.Text><Typography.Text type="secondary" code>{action.action_code}</Typography.Text>
          {action.topic_refs && action.topic_refs.length > 0 && <span>{action.topic_refs.join(', ')}</span>}
          {action.jurisdiction_ids && action.jurisdiction_ids.length > 0 && <Typography.Text type="secondary">{action.jurisdiction_ids.join(', ')}</Typography.Text>}
        </Space>
      </div>} />
    </section>)}
    <Typography.Title level={5}>{t('questions')}</Typography.Title>
    <Listy virtual={false} items={guidance.unresolved_legal_questions} rowKey={(question) => question} itemRender={(question) => <Typography.Paragraph>{question}</Typography.Paragraph>} />
    <Typography.Title level={5}>{t('prohibited')}</Typography.Title>
    <Listy virtual={false} items={guidance.prohibited_assertions} rowKey={(assertion) => assertion} itemRender={(assertion) => <Typography.Paragraph>{assertion}</Typography.Paragraph>} />
  </Card>;
}
