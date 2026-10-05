export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type Payload = { [key: string]: Json };
export type Lifecycle = 'DRAFT' | 'INGESTED' | 'VALIDATED' | 'PENDING_REVIEW' | 'APPROVED' | 'ACTIVE' | 'SUPERSEDED' | 'EXPIRED' | 'ARCHIVED';
export type Operation = 'VIEW' | 'EDIT' | 'REVIEW' | 'APPROVE' | 'PUBLISH' | 'ARCHIVE' | 'DOWNLOAD' | 'EXPORT' | 'OPERATIONS';
export type Action = 'validate' | 'submit-review' | 'approve' | 'reject' | 'publish' | 'supersede' | 'expire' | 'archive';
export type AdminSession = import('../../api/contracts').AdminContext;

export interface Version {
  id: string; definitionId: string; number: number | null; lifecycle: Lifecycle;
  recordVersion: number; payload?: Payload;
}
export type RegistryItem = Payload;
export interface RegistryResponse {
  registry_version: string;
  health: Payload;
  items: RegistryItem[];
}
export interface Resource {
  key: string; label: string; group: string;
  family: 'metadata' | 'knowledge' | 'boundary';
  registry?: string;
  fields: readonly Field[];
  gap?: string;
}
export interface Field {
  name: string; label: string; type: 'text' | 'json' | 'metadata';
  registry?: string; required?: boolean;
}
export interface Draft { code: string; display_name: string; payload: Payload; parent_definition_id?: string; }
export interface RuntimeReadiness {
  knowledge_version_id: string; tenant_id: string;
  status: 'PENDING' | 'BUILDING' | 'READY' | 'FAILED';
  checks: Record<string, boolean>; reason_codes: string[];
  assets: Payload; registry_projection_version: string | null;
  cache_generation: string | null; embedding_config_id: string | null;
}
export interface Source {
  source_id: string; collection_id: string; code: string; record_version: number;
}
export interface KnowledgeVersion {
  knowledge_version_id: string; document_id: string; collection_version_id: string;
  record_version: number; version: number; lifecycle: Lifecycle; language: string;
  provenance_json: Payload;
}
export interface IngestionRun { ingestion_run_id: string; status: string; error_code: string | null; }
export type FetchPort = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
export interface AdminHost {
  session: AdminSession | null;
  embedded?: boolean;
  /** Same-origin authenticated transport, including the host's CSRF protection. */
  transport?: FetchPort;
  onLogin?: () => void;
  /** Optional server supplied descriptors augment known contracts; no invented endpoints. */
  resources?: readonly Resource[];
}
