import type { CSSProperties } from 'react';
import { theme } from 'antd';
import type { AuthorizedContext, Session } from '../api/contracts';
import { PermissionDenied } from '../components/States';
import { AdminFeature } from '../features/admin/AdminFeature';

/** Reuses the canonical session, theme and shared HTTP transport; no second root. */
export function AdminRoute({ session, context }: { session: Session; context?: AuthorizedContext }) {
  const { token } = theme.useToken();
  if (!session.admin_context) return <PermissionDenied />;
  const style = {
    '--color-background': token.colorBgLayout, '--color-surface': token.colorBgContainer,
    '--color-text': token.colorText, '--color-primary': token.colorPrimary,
    '--color-border': token.colorBorder, '--color-text-secondary': token.colorTextSecondary,
  } as CSSProperties;
  return <div style={style}><AdminFeature host={{
    session: { ...session.admin_context, projectId: context?.project_id }, embedded: true,
  }}/></div>;
}
