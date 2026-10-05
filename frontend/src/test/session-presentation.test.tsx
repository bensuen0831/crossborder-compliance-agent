import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import App from '../App';
import session from './fixtures/session.json';
import products from './fixtures/products.json';
import scenarios from './fixtures/scenarios.json';
import jurisdictions from './fixtures/jurisdictions.json';
import retrieval from './fixtures/retrieval.json';

it('preserves the selected analysis context during background trusted-session refresh', async () => {
  let resolveSession!: (value: Response) => void;
  const deferred = new Promise<Response>(resolve => { resolveSession = resolve; });
  const response = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async path => {
    const url = String(path);
    if (url.includes('/session')) return deferred;
    if (url.includes('knowledge-scope')) return response(retrieval.rag_context_pack.scope);
    if (url.includes('/products')) return response(products);
    if (url.includes('/scenarios')) return response(scenarios);
    if (url.includes('/jurisdictions')) return response(jurisdictions);
    return response({ status: 'ok' });
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });
  client.setQueryData(['session'], session);
  render(<BrowserRouter><QueryClientProvider client={client}><App/></QueryClientProvider></BrowserRouter>);
  await userEvent.click(await screen.findByRole('combobox', { name: 'Project / pinned analysis snapshot' }));
  await userEvent.click(screen.getByText(session.contexts[0].display_name, { exact: true }));
  const query = await screen.findByRole('textbox', { name: 'Question or keywords' });
  await waitFor(() => expect(query).toBeEnabled());
  await act(async () => { resolveSession(response(session)); await new Promise(resolve => setTimeout(resolve, 0)); });
  expect(screen.getByRole('textbox', { name: 'Question or keywords' })).toBeEnabled();
}, 15000);
