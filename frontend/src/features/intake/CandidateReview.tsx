import { useState } from 'react';
import { Alert, Button } from 'antd';
import { useTranslation } from 'react-i18next';
import { ErrorState, LoadingState } from '../../components/States';
import type { components } from '../../api/m2a-generated';
import type { useDocumentCandidates } from './candidateApi';

type Item = components['schemas']['CandidatePreviewItem'];
type Decision = components['schemas']['CandidateDecisionInput'];


function editableValue(item: Item) {
  const payload = item.proposed_payload as Record<string, unknown>;
  const field = item.candidate_type === 'BUSINESS_FACT' ? 'normalized_value_json' : item.candidate_type === 'DATA_ITEM' ? 'raw_name' : item.candidate_type === 'DATA_FLOW_NODE' ? 'name' : 'direction';
  const value = item.edited_payload?.[item.candidate_type === 'BUSINESS_FACT' ? 'normalized_value' : field] ?? payload[field];
  return typeof value === 'string' ? value : JSON.stringify(value ?? '');
}
function editedPayload(item: Item, value: string) {
  const field = item.candidate_type === 'BUSINESS_FACT' ? 'normalized_value' : item.candidate_type === 'DATA_ITEM' ? 'raw_name' : item.candidate_type === 'DATA_FLOW_NODE' ? 'name' : 'direction';
  return { [field]: value };
}

export function CandidateReview({ state, dirty }: { state: ReturnType<typeof useDocumentCandidates>; dirty: boolean }) {
  const { t } = useTranslation();
  const [choices, setChoices] = useState<Record<string, Decision['action'] | 'UNRESOLVED'>>({});
  const [edits, setEdits] = useState<Record<string, string>>({});
  const items = state.preview.data?.candidates ?? [];
  const decisions = items.flatMap(item => {
    const action = choices[item.preparation_candidate_id] ?? (item.decision_status === 'UNRESOLVED' ? undefined : item.decision_status);
    return action && action !== 'UNRESOLVED' ? [{ preparation_candidate_id: item.preparation_candidate_id, action, ...(action === 'EDIT' ? { edited_payload: editedPayload(item, edits[item.preparation_candidate_id] ?? editableValue(item)) } : {}) }] : [];
  });
  const unresolved = items.some(item => item.requires_confirmation && !decisions.some(decision => decision.preparation_candidate_id === item.preparation_candidate_id));
  return <section aria-label={t('ui.candidates.title')}>
    <h3>{t('ui.candidates.title')}</h3><p>{t('ui.candidates.boundary')}</p>
    <Button disabled={dirty || state.preparation.isPending || state.preview.data?.status === 'PREPARING'} loading={state.preparation.isPending} onClick={() => state.preparation.mutate()}>{t('ui.candidates.prepare')}</Button>
    {state.preview.isPending && <LoadingState/>}
    {[state.preview.error, state.preparation.error, state.resolution.error].map((error, index) => error && <ErrorState key={index} error={error}/>)}
    {state.preview.data?.stale && <Alert type="warning" title={t('ui.candidates.stale')}/>}
    {state.preview.data?.status === 'COMPLETED' && items.length === 0 && <p>{t('ui.candidates.empty')}</p>}
    <ul>{items.map(item => {
      const action = choices[item.preparation_candidate_id] ?? item.decision_status ?? 'UNRESOLVED';
      return <li key={item.preparation_candidate_id} data-testid="candidate-review-item">
        <p>{item.requires_confirmation ? t('ui.candidates.aiDerived') : t('ui.candidates.native')}</p>
        <pre>{JSON.stringify(item.proposed_payload, null, 2)}</pre><p>{t('ui.candidates.confidence', { value: item.confidence })}</p>
        {item.sources.map(source => <details key={source.source_trace_ref_id}><summary>{t('ui.candidates.source')}</summary><blockquote>{source.source_excerpt}</blockquote><p>{source.section}</p><p>{source.document_version_id}</p><p>{source.parse_run_id}</p></details>)}
        <label>{t('ui.candidates.decision')}<select aria-label={t('ui.candidates.decision')} value={action} disabled={dirty || state.resolution.isPending} onChange={event => setChoices(previous => ({ ...previous, [item.preparation_candidate_id]: event.target.value as Decision['action'] | 'UNRESOLVED' }))}>
          <option value="UNRESOLVED">{t('ui.candidates.unresolved')}</option><option value="ACCEPT">{t('ui.candidates.accept')}</option><option value="REJECT">{t('ui.candidates.reject')}</option><option value="EDIT">{t('ui.candidates.edit')}</option>
        </select></label>
        {action === 'EDIT' && <label>{t('ui.candidates.editedValue')}<input maxLength={4000} value={edits[item.preparation_candidate_id] ?? editableValue(item)} onChange={event => setEdits(previous => ({ ...previous, [item.preparation_candidate_id]: event.target.value }))}/></label>}
      </li>;
    })}</ul>
    {items.length > 0 && <Button disabled={dirty || unresolved || state.preview.data?.stale || state.resolution.isPending} loading={state.resolution.isPending} onClick={() => state.resolution.mutate(decisions)}>{t('ui.candidates.submit')}</Button>}
    {state.blocked && <Alert type="warning" title={t('ui.candidates.required')}/>}
  </section>;
}
