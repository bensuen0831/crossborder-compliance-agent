import { Button, Card, Descriptions, Drawer, Empty, Space, Table, Tag, Typography } from 'antd';
import { FileSearchOutlined, LinkOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { EvidenceItem, Metadata } from '../api/contracts';
import { formatDate } from '../features/knowledge/formatting';
import { evidenceTitle, metadataLabel, safeSourceUrl } from '../features/knowledge/presentation';

export function EvidenceCard({ item, open }: { item: EvidenceItem; open: () => void }) {
  const { t } = useTranslation();
  return <Card size="small" className="evidence-card" title={<Space><FileSearchOutlined /><span>{evidenceTitle(item)}</span></Space>}
    extra={<Tag>{item.external_evidence_id ? t('external') : t('internal')}</Tag>}>
    <Typography.Paragraph ellipsis={{ rows: 2 }}>{item.source_authority ?? item.source_url}</Typography.Paragraph>
    <Space wrap><Tag>{item.source_tier}</Tag><Tag color="green">{item.scope_validation_status}</Tag></Space>
    <div className="card-action"><Button onClick={open} icon={<LinkOutlined />}>{t('source')}</Button></div>
  </Card>;
}
export function EvidenceTable({ items, jurisdictions, open }: { items: EvidenceItem[]; jurisdictions?: Metadata; open: (item: EvidenceItem) => void }) {
  const { t } = useTranslation();
  return <Table<EvidenceItem> rowKey="evidence_item_id" dataSource={items} scroll={{ x: 800 }}
    locale={{ emptyText: <Empty description={t('evidenceEmpty')} /> }}
    pagination={{ pageSize: 8, showSizeChanger: false }} columns={[
      { title: t('source'), key: 'source', render: (_, item) => <Button type="link" onClick={() => open(item)}>{evidenceTitle(item)}</Button> },
      { title: t('type'), key: 'type', render: (_, item) => item.external_evidence_id ? t('external') : t('internal') },
      { title: t('jurisdiction'), key: 'jurisdiction', render: (_, item) => item.jurisdiction_id ? metadataLabel(item.jurisdiction_id, jurisdictions) : t('notAvailable') },
      { title: t('tier'), dataIndex: 'source_tier' },
      { title: t('validation'), dataIndex: 'scope_validation_status', render: (value: string) => <Tag color="green">{value}</Tag> },
    ]} />;
}

export function SourceCitationDrawer({ item, close }: { item?: EvidenceItem; close: () => void }) {
  const { t } = useTranslation();
  const url = item && safeSourceUrl(item.source_url);
  return <Drawer title={t('source')} open={!!item} onClose={close} size="large" destroyOnHidden>
    {item && <>
      <Typography.Title level={4}>{evidenceTitle(item)}</Typography.Title>
      <Descriptions bordered column={1} size="small" items={[
        { key: 'authority', label: t('authority'), children: item.source_authority ?? t('notAvailable') },
        { key: 'url', label: t('source'), children: url ? <a href={url} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">{item.source_url}</a> : <span>{item.source_url}</span> },
        { key: 'language', label: t('ui.m1.sourceLanguage'), children: item.language },
        { key: 'locator', label: t('locator'), children: item.canonical_locator },
        { key: 'tier', label: t('tier'), children: item.source_tier },
        { key: 'citation', label: t('ui.citationId'), children: <Typography.Text code>{item.citation_id}</Typography.Text> },
        { key: 'version', label: t('version'), children: item.knowledge_version_id ?? item.external_evidence_id },
        { key: 'date', label: t('effective'), children: `${formatDate(item.effective_from)} → ${formatDate(item.effective_to)}` },
        { key: 'validation', label: t('validation'), children: item.scope_validation_status },
        { key: 'snapshot', label: t('snapshot'), children: item.analysis_snapshot_id },
        { key: 'policy', label: t('policy'), children: item.retrieval_policy_version },
        { key: 'index', label: t('ui.indexVersion'), children: item.knowledge_index_version ?? t('notAvailable') },
        { key: 'hash', label: t('ui.contentHash'), children: <Typography.Text code>{item.content_hash}</Typography.Text> },
      ]} />
      <Typography.Title level={5}>{t('excerpt')}</Typography.Title>
      <Typography.Paragraph className="source-excerpt">{item.original_text}</Typography.Paragraph>
      <Typography.Title level={5}>{t('provenance')}</Typography.Title>
      <pre className="provenance">{JSON.stringify(item.provenance, null, 2)}</pre>
    </>}
  </Drawer>;
}
