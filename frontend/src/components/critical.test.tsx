import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import type { EvidenceItem, FallbackGuidance, Sufficiency } from '../api/contracts';
import retrieval from '../test/fixtures/retrieval.json';
import { enterpriseTheme } from '../theme';
import { SourceCitationDrawer } from './Evidence';
import { SufficiencyBadge, SufficiencyPanel, FallbackPanel } from './Sufficiency';
import { ErrorState, EmptyState, FeatureGate, LoadingState } from './States';
import { RuntimeStatus } from './RuntimeStatus';
import { safeSourceUrl } from '../features/knowledge/presentation';
import session from '../test/fixtures/session.json';

function wrapper({ children }: { children: React.ReactNode }) {
  return <ConfigProvider theme={enterpriseTheme}><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider></ConfigProvider>;
}

describe('critical presentation behavior', () => {
  it.each(['SUFFICIENT', 'PARTIALLY_SUFFICIENT', 'INSUFFICIENT', 'CONFLICTED'] as const)('renders textual sufficiency status %s', (status) => {
    render(<SufficiencyBadge status={status} />, { wrapper });
    expect(screen.getByText(new RegExp(status))).toBeVisible();
  });
  it('renders backend reason codes, missing topics and typed fallback without legal decisions', () => {
    const suff = retrieval.rag_context_pack.knowledge_sufficiency as Sufficiency;
    render(<><SufficiencyPanel result={suff} /><FallbackPanel guidance={retrieval.rag_context_pack.fallback_guidance_context as FallbackGuidance} /></>, { wrapper });
    suff.reason_codes.forEach((code) => expect(screen.getAllByText(code)[0]).toBeVisible());
    expect(screen.getByText(/not a final compliance path/)).toBeVisible();
    expect(screen.queryByText('ALLOWED')).not.toBeInTheDocument();
  });
  it('opens an accessible source drawer with canonical citation, original text and version pins', async () => {
    const item = retrieval.rag_context_pack.evidence_pack.items[0] as EvidenceItem;
    const close = vi.fn();
    render(<SourceCitationDrawer item={item} close={close} />, { wrapper });
    expect(await screen.findByRole('dialog')).toBeVisible();
    expect(screen.getByText(item.citation_id)).toBeVisible();
    expect(screen.getByText(item.content_hash)).toBeVisible();
    expect(screen.getByText(item.original_text)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(close).toHaveBeenCalledOnce();
  });
  it.each([401, 403])('renders permission-denied status %s without retry or raw body', (status) => {
    render(<ErrorState error={new ApiError(status, 'PRIVATE_DETAIL')} />, { wrapper });
    expect(screen.getByText('Authorization required')).toBeVisible();
    expect(screen.queryByText('PRIVATE_DETAIL')).not.toBeInTheDocument();
  });
  it('renders loading, empty, error and trace ID states', () => {
    render(<><LoadingState /><EmptyState title="No evidence" /><ErrorState error={new ApiError(500, 'SERVER_FAILED', 'trace-123')} /></>, { wrapper });
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('No evidence')).toBeVisible();
    expect(screen.getByText('Request failed (HTTP 500).')).toBeVisible();
    expect(screen.queryByText('SERVER_FAILED')).not.toBeInTheDocument();
    expect(screen.getByText(/trace-123/)).toBeVisible();
  });
  it('marks unfinished features as unavailable without fake workflow progress', () => {
    render(<FeatureGate label="Stage 1" />, { wrapper });
    expect(screen.getByText('Coming in next milestone')).toBeVisible();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });
  it('does not request Admin readiness for an ordinary reader', () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    render(<RuntimeStatus session={{ ...session, permissions: ['read:internal'] }} versions={['restricted-version']} />, { wrapper });
    expect(screen.getByText(/requires knowledge:admin/)).toBeVisible();
    expect(fetch).not.toHaveBeenCalled();
  });
  it('renders only credential-free HTTPS source links', () => {
    expect(safeSourceUrl('javascript:alert(1)')).toBeUndefined();
    expect(safeSourceUrl('https://user:secret@site.example/a')).toBeUndefined();
    expect(safeSourceUrl('https://site.example/a')).toBe('https://site.example/a');
  });
});
