import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, AutoComplete, Button, Card, Form, Input, InputNumber, Select, Space, Table, Tag, Typography } from 'antd';
import { useTranslation } from 'react-i18next';
import schemas from '../../api/phase1kb-schemas.json';
import type { AdminSession, FetchPort } from '../admin/contracts';
import { ErrorState, LoadingState, PermissionDenied } from '../../components/States';
import { ModelControlClient } from './api';
import type { Model, ModelDraft, Provider, ProviderDraft, ProviderVersion, TestResult, Transition } from './api';

export function ModelProviders({ session, transport }: { session: AdminSession; transport?: FetchPort }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const client = useMemo(() => new ModelControlClient(transport), [transport]);
  const [form] = Form.useForm<ProviderDraft>();
  const [modelForm] = Form.useForm<ModelDraft>();
  const [editing, setEditing] = useState<Provider>();
  const [selected, setSelected] = useState<Provider>();
  const [editModel, setEditModel] = useState<Model>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error>();
  const [probe, setProbe] = useState<TestResult>();
  const [candidateNames, setCandidateNames] = useState<string[]>([]);
  const access = session.backendScopes.includes('metadata:admin');
  const key = ['phase1kb-providers', session.tenantId, session.actorId];
  const providers = useQuery({ queryKey: key, queryFn: ({ signal }) => client.providers(signal), enabled: access, retry: false });
  const presets = useQuery({ queryKey: ['phase1kb-presets', session.tenantId, session.actorId], queryFn: ({ signal }) => client.presets(signal), enabled: access, retry: false });
  const models = useQuery({ queryKey: ['phase1kb-models', session.tenantId, session.actorId, selected?.provider_id], queryFn: ({ signal }) => client.models(selected!.provider_id, signal), enabled: access && !!selected, retry: false });
  const act = async (action: () => Promise<unknown>) => {
    setError(undefined); setBusy(true);
    try { await action(); await queryClient.invalidateQueries({ queryKey: ['phase1kb-providers'] }); await queryClient.invalidateQueries({ queryKey: ['phase1kb-models'] }); }
    catch (cause) { setError(cause instanceof Error ? cause : new Error('MODEL_CONTROL_UNAVAILABLE')); } finally { setBusy(false); }
  };
  const edit = (provider: Provider) => {
    const version = provider.versions[0]; setEditing(provider);
    form.resetFields(); form.setFieldsValue({ code: provider.code, display_name: provider.display_name, vendor_preset: version.vendor_preset,
      protocol: version.protocol as ProviderDraft['protocol'], base_url: version.base_url ?? '', deployment_class: version.deployment_class as ProviderDraft['deployment_class'],
      trust_level: version.trust_level, data_boundary: version.data_boundary, effective_from: new Date().toISOString().slice(0, 10) });
  };
  const transition = (version: ProviderVersion | Model, kind: 'PROVIDER' | 'MODEL', target_status: Transition['target_status']) => act(() => kind === 'PROVIDER'
    ? client.transitionProvider((version as ProviderVersion).provider_version_id, { target_status, expected_record_version: version.record_version })
    : client.transitionModel((version as Model).deployment_id, { target_status, expected_record_version: version.record_version }));
  const actions = (version: ProviderVersion | Model, kind: 'PROVIDER' | 'MODEL') => <Space wrap>
    {version.lifecycle_status === 'DRAFT' && <Button disabled={busy} onClick={() => void transition(version, kind, 'PENDING_REVIEW')}>{t('ui.phase1kb.submit')}</Button>}
    {version.lifecycle_status === 'PENDING_REVIEW' && session.backendScopes.includes('metadata:review') && <Button disabled={busy} onClick={() => void transition(version, kind, 'APPROVED')}>{t('ui.phase1kb.approve')}</Button>}
    {version.lifecycle_status === 'APPROVED' && session.backendScopes.includes('metadata:publish') && <Button disabled={busy} onClick={() => void transition(version, kind, 'ACTIVE')}>{t('ui.phase1kb.publish')}</Button>}
  </Space>;
  const selectedProvider = providers.data?.providers.find(provider => provider.provider_id === selected?.provider_id) ?? selected;
  if (!access) return <PermissionDenied />;
  return <Space orientation="vertical" style={{ width: '100%' }}>
    <Typography.Title level={2}>{t('ui.phase1kb.providers')}</Typography.Title>
    {error && <ErrorState error={error} />}
    {providers.isPending ? <LoadingState /> : providers.error ? <ErrorState error={providers.error} /> : <Card>
      <Table<Provider> rowKey="provider_id" dataSource={providers.data?.providers} pagination={false} scroll={{ x: true }} columns={[
        { title: t('ui.phase1kb.displayName'), dataIndex: 'display_name' },
        { title: t('ui.phase1kb.status'), render: (_, provider) => <Space><Tag>{provider.enabled ? t('ui.phase1kb.enabled') : t('ui.phase1kb.disabled')}</Tag><Tag>{provider.versions[0]?.lifecycle_status}</Tag><Tag>{provider.versions[0]?.secret_configured ? t('ui.phase1kb.configured') : t('ui.phase1kb.notConfigured')}</Tag></Space> },
        { title: t('ui.phase1kb.actions'), render: (_, provider) => <Space wrap>
          <Button onClick={() => edit(provider)}>{t('ui.phase1kb.editSecret')}</Button>
          <Button onClick={() => { setSelected(provider); setCandidateNames([]); setProbe(undefined); }}>{t('ui.phase1kb.models')}</Button>
          <Button disabled={busy} onClick={() => void act(() => client.providerEnabled(provider, !provider.enabled))}>{t(provider.enabled ? 'ui.phase1kb.disable' : 'ui.phase1kb.enable')}</Button>
          {provider.versions.map(version => <Space key={version.provider_version_id}><Tag>{t('ui.phase1kb.version', { version: version.provider_version })}</Tag>{actions(version, 'PROVIDER')}
            <Button disabled={busy} onClick={() => void act(async () => setProbe(await client.testConnection(version.provider_version_id)))}>{t('ui.phase1kb.testConnection')}</Button>
            <Button disabled={busy} onClick={() => void act(async () => { const result = await client.discover(version.provider_version_id); setProbe(result); setCandidateNames(result.candidate_models); setSelected(provider); })}>{t('ui.phase1kb.discover')}</Button>
          </Space>)}
        </Space> },
      ]} />
    </Card>}
    {probe && <Alert type={probe.status === 'HEALTHY' ? 'success' : 'warning'} title={`${t('ui.phase1kb.health')}: ${probe.status}`} />}
    <Card title={t(editing ? 'ui.phase1kb.editProvider' : 'ui.phase1kb.createProvider')}>
      <Form form={form} layout="vertical" initialValues={{ protocol: 'OPENAI_COMPATIBLE', deployment_class: 'EXTERNAL', vendor_preset: 'OTHER_OPENAI_COMPATIBLE', timeout_seconds: 30, effective_from: new Date().toISOString().slice(0, 10) }} onFinish={(values) => void act(async () => {
        await client.saveProvider({ ...values, ...(editing ? { provider_id: editing.provider_id, expected_record_version: editing.record_version } : {}) });
        form.resetFields(); setEditing(undefined);
      })}>
        <Form.Item name="code" label={t('ui.phase1kb.code')} rules={[{ required: true }]}><Input disabled={!!editing} /></Form.Item>
        <Form.Item name="display_name" label={t('ui.phase1kb.displayName')} rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item name="vendor_preset" label={t('ui.phase1kb.vendor')}><AutoComplete options={(presets.data?.items ?? []).map(item => ({ value: item.payload?.vendor_preset ?? item.code, label: item.display_name }))} /></Form.Item>
        <Form.Item name="protocol" label={t('ui.phase1kb.protocol')}><Select options={schemas.components.schemas.ProviderDraft.properties.protocol.enum.map(value => ({ value, label: value }))} /></Form.Item>
        <Form.Item name="base_url" label={t('ui.phase1kb.endpoint')} rules={[{ required: true }]}><Input type="url" /></Form.Item>
        <Form.Item name="credential" label={t('ui.phase1kb.credential')}><Input.Password autoComplete="new-password" /></Form.Item>
        <Form.Item name="deployment_class" label={t('ui.phase1kb.deployment')}><Select options={schemas.components.schemas.ProviderDraft.properties.deployment_class.enum.map(value => ({ value, label: value }))} /></Form.Item>
        <Form.Item name="trust_level" label={t('ui.phase1kb.trust')} rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item name="data_boundary" label={t('ui.phase1kb.boundary')} rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item name="timeout_seconds" label={t('ui.phase1kb.timeout')}><InputNumber min={1} max={300} /></Form.Item>
        <Form.Item name="effective_from" label={t('ui.phase1kb.effectiveDate')} rules={[{ required: true }]}><Input type="date" /></Form.Item>
        <Space><Button htmlType="submit" type="primary" loading={busy}>{t('ui.phase1kb.saveProvider')}</Button><Button onClick={() => { form.resetFields(); setEditing(undefined); }}>{t('ui.phase1kb.clear')}</Button></Space>
      </Form>
    </Card>
    {selected && <Card title={`${t('ui.phase1kb.models')} — ${selected.display_name}`}>
      {models.error && <ErrorState error={models.error} />}
      <Table<Model> rowKey="deployment_id" dataSource={models.data?.models} pagination={false} scroll={{ x: true }} columns={[
        { title: t('ui.phase1kb.displayName'), dataIndex: 'display_name' }, { title: t('ui.phase1kb.remoteModel'), dataIndex: 'remote_model_name' },
        { title: t('ui.phase1kb.health'), dataIndex: 'health_status' }, { title: t('ui.phase1kb.status'), dataIndex: 'lifecycle_status' },
        { title: t('ui.phase1kb.actions'), render: (_, model) => <Space wrap>{actions(model, 'MODEL')}
          <Button disabled={busy} onClick={() => void act(() => client.modelEnabled(model, !model.enabled))}>{t(model.enabled ? 'ui.phase1kb.disable' : 'ui.phase1kb.enable')}</Button>
          <Button onClick={() => { setEditModel(model); modelForm.setFieldsValue({ ...model, effective_from: new Date().toISOString().slice(0, 10) }); }}>{t('ui.phase1kb.configureModel')}</Button>
          {model.operations.filter(operation => ['chat', 'structured_output', 'embedding'].includes(operation)).map(operation => <Button key={operation} disabled={busy} onClick={() => void act(async () => setProbe(await client.testModel(model.deployment_id, operation as 'chat' | 'structured_output' | 'embedding')))}>{t('ui.phase1kb.testModel')} {operation}</Button>)}
        </Space> },
      ]} />
      <Typography.Paragraph>{t('ui.phase1kb.discoveryNote')}</Typography.Paragraph>
      <Form form={modelForm} layout="vertical" initialValues={{ max_output_tokens: 512, priority: 100, capabilities: ['TEXT'], operations: ['chat'], structured_output_format: 'json_schema', effective_from: new Date().toISOString().slice(0, 10) }} onFinish={(values) => void act(async () => {
        await client.saveModel(selected.provider_id, { ...values, ...(editModel ? { model_id: editModel.model_id, expected_record_version: editModel.model_record_version } : {}) });
        modelForm.resetFields(); setEditModel(undefined);
      })}>
        <Form.Item name="provider_version_id" label={t('ui.phase1kb.providerVersion')} rules={[{ required: true }]}><Select options={selectedProvider!.versions.filter(version => version.lifecycle_status === 'ACTIVE').map(version => ({ value: version.provider_version_id, label: t('ui.phase1kb.version', { version: version.provider_version }) }))} /></Form.Item>
        <Form.Item name="display_name" label={t('ui.phase1kb.displayName')} rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item name="remote_model_name" label={t('ui.phase1kb.remoteModel')} rules={[{ required: true }]}><AutoComplete options={candidateNames.map(value => ({ value, label: value }))} /></Form.Item>
        <Form.Item name="capabilities" label={t('ui.phase1kb.capabilities')}><Select mode="multiple" options={schemas.components.schemas.ModelCapabilityCode.enum.map(value => ({ value, label: value }))} /></Form.Item>
        <Form.Item name="operations" label={t('ui.phase1kb.operations')}><Select mode="multiple" options={schemas.components.schemas.ModelOperation.enum.map(value => ({ value, label: value }))} /></Form.Item>
        <Form.Item name="max_output_tokens" label={t('ui.phase1kb.maxTokens')}><InputNumber min={1} max={65536} /></Form.Item>
        <Form.Item name="embedding_dimension" label={t('ui.phase1kb.embeddingDimension')}><InputNumber min={1} max={16000} /></Form.Item>
        <Form.Item name="priority" label={t('ui.phase1kb.priority')}><InputNumber min={0} max={10000} /></Form.Item>
        <Form.Item name="structured_output_format" label={t('ui.phase1kb.structuredFormat')}><Select options={schemas.components.schemas.ModelDraft.properties.structured_output_format.enum.map(value => ({ value, label: value }))} /></Form.Item>
        <Form.Item name="effective_from" label={t('ui.phase1kb.effectiveDate')} rules={[{ required: true }]}><Input type="date" /></Form.Item>
        <Button type="primary" htmlType="submit" loading={busy}>{t('ui.phase1kb.saveModel')}</Button>
      </Form>
    </Card>}
  </Space>;
}
