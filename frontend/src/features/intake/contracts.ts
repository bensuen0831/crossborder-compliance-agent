import type { components } from '../../api/m1-generated';
export type Classification = components['schemas']['ClassificationResult'];
export type Applicability = components['schemas']['RegulationApplicabilityResult'];
export type IntakeContract = components['schemas']['ProjectIntakeContext'];
export type WorkflowView = components['schemas']['WorkflowView'];
export interface GovernedOption { definition_id?: string; jurisdiction_id?: string; code?: string; display_name?: string; payload?: Record<string, unknown>; presentation?: { display_name: string; fallback_used: boolean; requested_locale: string }; }
export interface ContextItem { data_item_id: string; display_name?: string; canonical_name?: string; }
export interface Party { project_party_id: string; display_name: string; }
export interface FlowInput { id: string; data_item_id: string; source_location: string; destination_location: string; }
/** Local, uncommitted intake facts; never a source of formal engine outputs. */
export interface Draft { scenario: string; product: string; source: string[]; destination: string[]; processing: string[]; storage: string[]; categories: string[]; dataTypes: string[]; items: string[]; organizations: string[]; thirdParties: string[]; flows: FlowInput[]; purpose: string; dataVolume: string; flowDescription: string; description: string; documents: string; }
export const emptyDraft = (): Draft => ({ scenario: '', product: '', source: [], destination: [], processing: [], storage: [], categories: [], dataTypes: [], items: [], organizations: [], thirdParties: [], flows: [], purpose: '', dataVolume: '', flowDescription: '', description: '', documents: '' });
export const optionId = (item: GovernedOption) => item.definition_id ?? item.jurisdiction_id ?? item.code ?? '';
export const optionLabel = (item: GovernedOption) => item.presentation?.display_name ?? item.display_name ?? item.code ?? optionId(item);
