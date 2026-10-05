import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Avatar, Button, Card, ConfigProvider, Layout, Menu, Select, Space, Tabs, Tag, Typography } from 'antd';
import { ApiOutlined, BookOutlined, SafetyCertificateOutlined, SearchOutlined } from '@ant-design/icons';
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api, ApiError, demoEnabled } from './api/client';
import type { EvidenceItem, RetrievalRequest, Session } from './api/contracts';
import enUS from 'antd/locale/en_US';
import zhCN from 'antd/locale/zh_CN';
import zhHK from 'antd/locale/zh_HK';
import { currentLocale, supportedLocales, type Locale } from './i18n';
import { formatNumber } from './features/knowledge/formatting';
import { enterpriseTheme } from './theme';
import { AdminRoute } from './routes/AdminRoute';
import { ContextSelector } from './components/ContextSelector';
import { EvidenceCard, EvidenceTable, SourceCitationDrawer } from './components/Evidence';
import { FallbackPanel, SufficiencyPanel } from './components/Sufficiency';
import { QueryPanel } from './components/QueryPanel';
import { RuntimeStatus, StatusHealthIndicator } from './components/RuntimeStatus';
import { EmptyState, ErrorState, FeatureGate, LoadingState, PermissionDenied } from './components/States';
import { useRetrieval, useScope } from './features/knowledge/queries';

function PageHeader({ runtime, admin = false }: { runtime: boolean; admin?: boolean }) {
  const { t } = useTranslation();
  return <header className="page-heading"><Typography.Text className="eyebrow">{t('ui.foundation')}</Typography.Text>
    <Typography.Title level={1}>{t(admin ? 'admin' : runtime ? 'operational' : 'knowledge')}</Typography.Title>
    <Typography.Paragraph type="secondary">{t(admin ? 'adminSubtitle' : 'subtitle')}</Typography.Paragraph>
  </header>;
}

function SideNavigation({ adminAvailable }: { adminAvailable: boolean }) {
  const { t } = useTranslation();
  const location = useLocation();
  return <nav aria-label={t('ui.navigation')}>
    <Menu theme="dark" mode="inline" selectedKeys={[location.pathname]} items={[
      { key: '/knowledge', icon: <SearchOutlined />, label: <Link to="/knowledge">{t('knowledge')}</Link> },
      { key: '/runtime', icon: <ApiOutlined />, label: <Link to="/runtime">{t('operational')}</Link> },
      { key: '/admin', disabled: !adminAvailable, icon: <SafetyCertificateOutlined />, label: <Link to="/admin">{t('admin')}</Link> },
      { type: 'group', label: t('future'), children: [
        { key: 'stage1', disabled: true, icon: <SafetyCertificateOutlined />, label: <FeatureGate label={t('ui.stage1')} /> },
      ] },
    ]} />
  </nav>;
}

function Workspace({ session }: { session: Session }) {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const [project, setProject] = useState<string>();
  const [submitted, setSubmitted] = useState<RetrievalRequest | null>(null);
  const [selectedId, setSelectedId] = useState<string>();
  const context = session.contexts.find((item) => item.project_id === project);
  const scope = useScope(session, context);
  const retrieval = useRetrieval(session, context, submitted);
  const rag = retrieval.isSuccess && !retrieval.isFetching ? retrieval.data.rag_context_pack : undefined;
  const items = rag?.evidence_pack.items ?? [];
  const selected = items.find((item) => item.evidence_item_id === selectedId);
  const jurisdictions = useQuery({ queryKey: ['metadata', session.identity_key, 'jurisdictions'], queryFn: ({ signal }) => api.metadata('jurisdictions', signal), retry: false, gcTime: 0 });
  const open = (item: EvidenceItem) => setSelectedId(item.evidence_item_id);
  const submit = (query: string) => {
    if (!context) return;
    setSelectedId(undefined);
    setSubmitted({ query_text: query, analysis_snapshot_id: context.analysis_snapshot_id, policy_id: context.policy_id,
      idempotency_key: crypto.randomUUID(), subject_type: 'PROJECT', languages: [] });
  };
  const choose = (id: string) => { setProject(id); setSubmitted(null); setSelectedId(undefined); };
  const runtime = location.pathname === '/runtime';
  const admin = location.pathname.startsWith('/admin');
  return <Layout className="workspace-layout">
    <Layout.Sider width={230} breakpoint="lg" collapsedWidth={0} className="sidebar">
      <div className="wordmark"><span className="brand-mark"><BookOutlined /></span><span>{t('ui.brand')}<small>{t('ui.brandSubtitle')}</small></span></div>
      <SideNavigation adminAvailable={!!session.admin_context}/>
      <div className="sidebar-foot"><Tag>{t('ui.release')}</Tag><Typography.Paragraph type="secondary">{t('noLegalResult')}</Typography.Paragraph></div>
    </Layout.Sider>
    <Layout>
      <div className="workspace-topbar"><Space><Avatar size="small">{session.display_name.slice(0, 1)}</Avatar><Typography.Text>{session.display_name}</Typography.Text><Tag>{session.tenant_label}</Tag>
        {session.organization_label && <Tag>{session.organization_label}</Tag>}{session.department_label && <Tag>{session.department_label}</Tag>}</Space><StatusHealthIndicator /></div>
      <Layout.Content className="workspace-content"><PageHeader runtime={runtime} admin={admin}/>
        {session.demo && <Alert className="demo-banner" type="info" showIcon title={t('demo')} description={t('demoNote')} />}
        <div className={`workspace-grid ${admin ? 'admin-workspace-grid' : ''}`}><section className="main-column">
          <ContextSelector session={session} context={context} choose={choose} scope={scope.data} scopeError={scope.error} scopeLoading={scope.isFetching} />
          {session.contexts.length === 0 && <EmptyState title={t('noContext')} />}
          <Routes>
            <Route path="/knowledge" element={<>
              <QueryPanel disabled={!context || !scope.isSuccess || scope.isFetching} busy={retrieval.isFetching} submit={submit} />
              {retrieval.isFetching ? <Card><LoadingState /></Card> : retrieval.error ? <ErrorState error={retrieval.error} retry={() => void retrieval.refetch()} /> : !submitted ?
                <Card className="welcome-card"><EmptyState title={t('readyToSearch')} description={t('startHint')} /></Card> : rag ?
                  <Card title={<Space>{t('evidence')}<Tag>{formatNumber(rag.knowledge_sufficiency.evidence_count)}</Tag></Space>}
                    extra={<Button onClick={() => navigate('/runtime')}>{t('operational')}</Button>}>
                    {items.length === 0 ? <EmptyState title={t('evidenceEmpty')} description={t('evidenceEmptyDetail')} /> :
                      <Tabs items={[
                        { key: 'cards', label: t('ui.cards'), children: <div className="evidence-grid">{items.map((item) => <EvidenceCard key={item.evidence_item_id} item={item} open={() => open(item)} />)}</div> },
                        { key: 'table', label: t('ui.table'), children: <EvidenceTable items={items} jurisdictions={jurisdictions.data} open={open} /> },
                      ]} />}
                  </Card> : <Alert type="info" title={t('ui.retrievalStatus', { status: retrieval.data?.status ?? t('notAvailable') })} />}
            </>} />
            <Route path="/runtime" element={<RuntimeStatus session={session} versions={[...new Set(items.flatMap((item) => item.knowledge_version_id ? [item.knowledge_version_id] : []))]} />} />
            <Route path="/admin/*" element={<AdminRoute session={session} context={context}/>} />
            <Route path="*" element={<Navigate replace to="/knowledge" />} />
          </Routes>
        </section>{!admin && <aside className="insight-column" aria-label={t('sufficiency')}>
          {rag ? <><SufficiencyPanel result={rag.knowledge_sufficiency} />{rag.fallback_guidance_context && <FallbackPanel guidance={rag.fallback_guidance_context} />}</> :
            <Card title={t('sufficiency')}><Typography.Paragraph type="secondary">{t('startHint')}</Typography.Paragraph></Card>}
        </aside>}</div>
      </Layout.Content>
    </Layout>
    <SourceCitationDrawer item={selected} close={() => setSelectedId(undefined)} />
  </Layout>;
}

export default function App() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [switching, setSwitching] = useState(false);
  const [loginError, setLoginError] = useState<Error | null>(null);
  const session = useQuery({ queryKey: ['session'], queryFn: ({ signal }) => api.session(signal), enabled: !switching, retry: false, staleTime: 0, gcTime: 0 });
  const changeIdentity = async (persona?: 'A' | 'B' | 'PROJECT') => {
    setSwitching(true); setLoginError(null);
    await queryClient.cancelQueries();
    queryClient.clear();
    try {
      if (persona) queryClient.setQueryData(['session'], await api.demoLogin(persona));
      else await api.logout();
    } catch (error) { setLoginError(error instanceof Error ? error : new ApiError(0, 'SIGN_IN_FAILED')); }
    finally { setSwitching(false); }
  };
  return <ConfigProvider theme={enterpriseTheme} locale={{ 'en-US': enUS, 'zh-CN': zhCN, 'zh-HK': zhHK }[currentLocale()]}>
    <div className="global-bar"><Space><SafetyCertificateOutlined /><span>{t('workspace')}</span></Space>
      <Space wrap><Select aria-label={t('ui.language')} value={currentLocale()} options={supportedLocales.map(locale => ({ value: locale, label: t({ 'zh-CN': 'ui.localeCN', 'zh-HK': 'ui.localeHK', 'en-US': 'ui.localeEN' }[locale]) }))} onChange={(lang: Locale) => void i18n.changeLanguage(lang)} />
        {demoEnabled && <><Button disabled={switching} onClick={() => void changeIdentity('A')}>{t('loginA')}</Button><Button disabled={switching} onClick={() => void changeIdentity('B')}>{t('loginB')}</Button><Button disabled={switching} onClick={() => void changeIdentity('PROJECT')}>{t('loginProject')}</Button></>}
        {session.isSuccess && <Button onClick={() => void changeIdentity()}>{t('signOut')}</Button>}
      </Space>
    </div>
    {loginError && <ErrorState error={loginError} />}
    {switching || session.isPending ? <div className="sign-in-state"><LoadingState /></div> : session.isSuccess ?
      <Workspace key={session.data.identity_key} session={session.data} /> : <div className="sign-in-state">
        {session.error instanceof ApiError && session.error.status === 404 ? <Alert type="info" title={t('sessionUnavailable')} description={t('sessionHint')} /> : session.error ?
          <ErrorState error={session.error} retry={() => void session.refetch()} /> : <PermissionDenied />}
      </div>}
  </ConfigProvider>;
}
