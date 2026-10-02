import type { components } from './generated';

export type RetrievalResponse = components['schemas']['RetrievalResponseDTO'];
export type RetrievalRequest = components['schemas']['RetrievalRequestDTO'];
export type EvidenceItem = components['schemas']['EvidencePackItem'];
export type Sufficiency = components['schemas']['KnowledgeSufficiencyResult'];
export type FallbackGuidance = components['schemas']['ActionableFallbackGuidanceContext'];
export type Scope = components['schemas']['KnowledgeScope'];
export type Readiness = components['schemas']['KnowledgeRuntimeReadinessResult'];

// Presentation/auth integration contract, separate from frozen domain DTOs.
// A deployment BFF supplies this; the loopback-only UAT adapter implements it.
export interface AuthorizedContext {
  project_id: string;
  display_name: string;
  analysis_snapshot_id: string;
  policy_id: string;
}
export interface Session {
  identity_key: string;
  display_name: string;
  tenant_label: string;
  organization_label: string | null;
  department_label: string | null;
  permissions: string[];
  contexts: AuthorizedContext[];
  demo: boolean;
}
export interface MetadataItem {
  definition_id?: string;
  jurisdiction_id?: string;
  display_name?: string;
  name?: string;
  code?: string;
}
export interface Metadata {
  items: MetadataItem[];
  registry_version: string;
  health: { status: string };
}
export interface Health { status: string; app_env?: string }
