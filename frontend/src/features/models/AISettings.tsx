import { useQuery } from '@tanstack/react-query';
import { Alert } from 'antd';
import { useTranslation } from 'react-i18next';
import { request } from '../../api/client';
import type { components } from '../../api/phase1kb-generated';
import type { components as Intake } from '../../api/m2a-generated';
import schemas from '../../api/m2a-schemas.json';
import { ErrorState, LoadingState } from '../../components/States';

export type ModelPreference = Intake['schemas']['AIModelPreference'];
const defaultPreference: ModelPreference = { usage_mode: 'STANDARD', selection_mode: 'AUTO', selected_model_ids: [] };

export function AISettings({ projectId, identity, value = defaultPreference, onChange, disabled = false }: {
  projectId: string; identity: string; value?: ModelPreference; onChange: (value: ModelPreference) => void; disabled?: boolean;
}) {
  const { t } = useTranslation();
  const models = useQuery({ queryKey: ['phase1kb-eligible', identity, projectId], enabled: !disabled, retry: false,
    queryFn: ({ signal }) => request<components['schemas']['EligibleModelCatalog']>(`/api/v1/projects/${encodeURIComponent(projectId)}/eligible-models`, { signal }, 'EligibleModelCatalog') });
  const mode = value.usage_mode ?? 'STANDARD';
  const selection = value.selection_mode ?? 'AUTO';
  const selected = value.selected_model_ids ?? [];
  return <fieldset disabled={disabled} className="m1-form">
    <legend>{t('ui.phase1kb.aiSettings')}</legend>
    {models.isFetching && <LoadingState/>}{models.error && <ErrorState error={models.error}/>}
    {models.data?.status === 'CAPABILITY_NOT_CONFIGURED' && <Alert type="info" title={t('ui.phase1kb.aiUnavailable')}/>}
    <label>{t('ui.phase1kb.usageMode')}<select value={mode} onChange={event => {
      const usage_mode = event.target.value as ModelPreference['usage_mode'];
      onChange({ ...value, usage_mode, ...(usage_mode !== 'ENHANCED' && selection === 'MULTI_MODEL' ? { selection_mode: 'AUTO', selected_model_ids: [] } : {}) });
    }}>{schemas.components.schemas.LLMUsageMode.enum.map(code => <option key={code} value={code}>{t(`ui.phase1kb.mode.${code}`)}</option>)}</select></label>
    <label>{t('ui.phase1kb.selectionMode')}<select value={selection} onChange={event => {
      const selection_mode = event.target.value as ModelPreference['selection_mode'];
      onChange({ ...value, selection_mode, selected_model_ids: [], ...(selection_mode === 'MULTI_MODEL' ? { usage_mode: 'ENHANCED' } : {}) });
    }}>{schemas.components.schemas.ModelSelectionMode.enum.map(code => <option key={code} value={code} disabled={code !== 'AUTO' && !models.data?.eligible_models.length}>{t(`ui.phase1kb.selection.${code}`)}</option>)}</select></label>
    {selection !== 'AUTO' && <label>{t('ui.phase1kb.eligibleModels')}<select multiple={selection === 'MULTI_MODEL'} value={selection === 'MULTI_MODEL' ? selected : selected[0] ?? ''} onChange={event => onChange({ ...value, selected_model_ids: Array.from(event.target.selectedOptions, option => option.value).filter(Boolean) })}>
      {selection === 'SINGLE' && <option value="">{t('ui.m1.choose')}</option>}
      {(models.data?.eligible_models ?? []).map(model => <option key={model.model_id} value={model.model_id}>{model.display_name}</option>)}
    </select></label>}
    <p>{t('ui.phase1kb.preferenceBoundary')}</p>
  </fieldset>;
}
