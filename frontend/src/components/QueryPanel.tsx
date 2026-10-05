import { Button, Card, Form, Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

export function QueryPanel({ disabled, busy, submit }: { disabled: boolean; busy: boolean; submit: (text: string) => void }) {
  const { t } = useTranslation();
  return <Card className="query-card"><Form layout="vertical" onFinish={({ query }: { query: string }) => submit(query.trim())}>
    <Form.Item name="query" label={t('query')} rules={[
      { required: true, whitespace: true, message: t('query') }, { max: 4000, message: 'Maximum 4000 characters' },
    ]}>
      <Input.TextArea aria-label={t('query')} placeholder={t('queryPlaceholder')} autoSize={{ minRows: 3, maxRows: 8 }} maxLength={4000} disabled={disabled} />
    </Form.Item>
    <Button type="primary" size="large" htmlType="submit" aria-label={t('search')} icon={<SearchOutlined aria-hidden />} loading={busy} disabled={disabled}>{t('search')}</Button>
  </Form></Card>;
}
