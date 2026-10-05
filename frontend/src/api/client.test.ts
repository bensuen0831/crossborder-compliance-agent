import { describe, expect, it, vi } from 'vitest';
import { api, ApiError, validateContract } from './client';
import type { RetrievalResponse, Session } from './contracts';
import fixture from '../test/fixtures/retrieval.json';
import ready from '../test/fixtures/readiness.json';
import session from '../test/fixtures/session.json';
import products from '../test/fixtures/products.json';

describe('frozen API contracts', () => {
  it('validates a real PostgreSQL-backed retrieval, scope, readiness, evidence and sufficiency', () => {
    const actual = validateContract<RetrievalResponse>('RetrievalResponseDTO', fixture);
    expect(actual.rag_context_pack?.evidence_pack.items).toHaveLength(2);
    validateContract('KnowledgeScope', fixture.rag_context_pack.scope);
    validateContract('EvidencePack', fixture.rag_context_pack.evidence_pack);
    validateContract('KnowledgeSufficiencyResult', fixture.rag_context_pack.knowledge_sufficiency);
    validateContract('KnowledgeRuntimeReadinessResult', ready);
    validateContract('Session', session);
    validateContract('Metadata', products);
  });
  it('fails closed on a malformed session integration response', () => {
    expect(() => validateContract('Session', { ...session, contexts: 'FORGED' })).toThrow('API_CONTRACT_MISMATCH');
    expect(() => validateContract('Session', { ...session, admin_context: { roles: ['admin'] } })).toThrow('API_CONTRACT_MISMATCH');
  });
  it('rejects malformed status and fabricated legal evidence at the API boundary', () => {
    expect(() => validateContract('RetrievalResponseDTO', { ...fixture, status: 'FAKE_SUCCESS' })).toThrow('API_CONTRACT_MISMATCH');
    const corrupt = structuredClone(fixture);
    corrupt.rag_context_pack.evidence_pack.items[0].legal_decision = true;
    expect(() => validateContract('RetrievalResponseDTO', corrupt)).toThrow('API_CONTRACT_MISMATCH');
  });
  it('posts only typed retrieval fields and uses same-origin cookie authentication', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(fixture), { status: 200 }));
    vi.stubGlobal('fetch', fetch);
    const ctx = (session as Session).contexts[0];
    await api.retrieve(ctx, { analysis_snapshot_id: ctx.analysis_snapshot_id, policy_id: ctx.policy_id, query_text: 'Generic', idempotency_key: 'test', subject_type: 'PROJECT', languages: [] });
    expect(fetch.mock.calls[0][1].credentials).toBe('same-origin');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).not.toHaveProperty('tenant_id');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).not.toHaveProperty('allowed_product_ids');
  });
  it('preserves safe trace IDs and does not serialize sensitive validation bodies', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ input: 'SENSITIVE_BODY' }], trace_id: 'trace-safe' }), { status: 422 })));
    await expect(api.health()).rejects.toMatchObject({ status: 422, message: 'HTTP_422', traceId: 'trace-safe' });
  });
  it('hides raw error strings and unsafe trace IDs on the shared Admin/M0 transport', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'API_KEY_SECRET', trace_id: '<script>secret</script>' }), { status: 403 })));
    await expect(api.health()).rejects.toMatchObject({ message: 'HTTP_403', traceId: undefined });
  });
  it.each([401, 403, 404])('preserves authorization/scoped absence HTTP %s', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status })));
    await expect(api.session()).rejects.toBeInstanceOf(ApiError);
    await expect(api.session()).rejects.toMatchObject({ status });
  });
});
