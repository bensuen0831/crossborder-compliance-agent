import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import i18n from '../../i18n';
import { AISettings, type ModelPreference } from './AISettings';

const ids = ['00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002'];
function Selector({ change }: { change: (preference: ModelPreference) => void }) {
  const [value, setValue] = useState<ModelPreference>();
  return <AISettings identity="owner" projectId={ids[0]} value={value} onChange={next => { setValue(next); change(next); }}/>;
}
const fixture = { project_id: ids[0], status: 'AVAILABLE', reason_code: null, eligible_models: ids.map((id, index) => ({ model_id: id, deployment_id: id, provider_id: id, provider_version_id: id, display_name: `Model ${index + 1}`, capabilities: ['STRUCTURED_OUTPUT'], operations: ['structured_output'], health_status: 'HEALTHY' })) };

describe('allowlisted AI preferences', () => {
  it.each(['zh-CN', 'zh-HK', 'en-US'])('supports AUTO/SINGLE/MULTI_MODEL requests in %s', async locale => {
    await i18n.changeLanguage(locale);
    const transport = vi.fn().mockResolvedValue(new Response(JSON.stringify(fixture)));
    vi.stubGlobal('fetch', transport);
    const change = vi.fn();
    const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={cache}><Selector change={change}/></QueryClientProvider>);
    const user = userEvent.setup();
    const selection = screen.getByLabelText(i18n.t('ui.phase1kb.selectionMode'));
    await waitFor(() => expect(screen.getByRole('option', { name: i18n.t('ui.phase1kb.selection.SINGLE') })).toBeEnabled());
    expect(selection).toHaveValue('AUTO');
    await user.selectOptions(selection, 'SINGLE');
    await user.selectOptions(screen.getByLabelText(i18n.t('ui.phase1kb.eligibleModels')), ids[0]);
    expect(change).toHaveBeenLastCalledWith({ usage_mode: 'STANDARD', selection_mode: 'SINGLE', selected_model_ids: [ids[0]] });
    await user.selectOptions(selection, 'MULTI_MODEL');
    await user.selectOptions(screen.getByLabelText(i18n.t('ui.phase1kb.eligibleModels')), ids);
    expect(change.mock.lastCall?.[0]).toMatchObject({ usage_mode: 'ENHANCED', selection_mode: 'MULTI_MODEL', selected_model_ids: ids });
    await user.selectOptions(selection, 'AUTO');
    expect(change.mock.lastCall?.[0].selected_model_ids).toEqual([]);
    expect(transport).toHaveBeenCalledWith(`/api/v1/projects/${ids[0]}/eligible-models`, expect.objectContaining({ credentials: 'same-origin' }));
    expect(document.body.textContent).not.toMatch(/Base URL|API key|secret_ref/);
    vi.unstubAllGlobals();
  });
});
