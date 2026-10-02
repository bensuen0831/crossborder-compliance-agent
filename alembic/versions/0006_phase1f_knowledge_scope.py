"""Phase 1F canonical knowledge extensions and derived indexes (frozen DDL)."""

from alembic import op

revision = "0006_phase1f"
down_revision = "0005_phase1e"
branch_labels = None
depends_on = None

UPGRADE_STATEMENTS = [
    "\nCREATE TABLE knowledge_documents (\n\tdocument_id VARCHAR(36) NOT NULL, \n\tsource_id VARCHAR(36) NOT NULL, \n\tdisplay_name VARCHAR(250) NOT NULL, \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (document_id), \n\tFOREIGN KEY(source_id) REFERENCES knowledge_source_definitions (knowledge_source_definition_id)\n)\n\n",
    "\nCREATE TABLE knowledge_scope_resolutions (\n\tresolution_id VARCHAR(36) NOT NULL, \n\tproject_id VARCHAR(36) NOT NULL, \n\tanalysis_snapshot_id VARCHAR(36), \n\tsubject_type VARCHAR(40) NOT NULL, \n\tsubject_id VARCHAR(36) NOT NULL, \n\tscope_json JSON NOT NULL, \n\tcontext_json JSON NOT NULL, \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (resolution_id), \n\tCONSTRAINT uq_snapshot_knowledge_scope UNIQUE (tenant_id, analysis_snapshot_id, subject_type, subject_id), \n\tFOREIGN KEY(project_id) REFERENCES projects (project_id), \n\tFOREIGN KEY(analysis_snapshot_id) REFERENCES analysis_snapshots (analysis_snapshot_id)\n)\n\n",
    "\nCREATE TABLE knowledge_document_versions (\n\tknowledge_version_id VARCHAR(36) NOT NULL, \n\tdocument_id VARCHAR(36) NOT NULL, \n\tcollection_version_id VARCHAR(36) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tlifecycle VARCHAR(40) NOT NULL, \n\tlanguage VARCHAR(80) NOT NULL, \n\tcontent_hash VARCHAR(64), \n\toriginal_artifact_ref VARCHAR(500), \n\teffective_from DATE, \n\teffective_to DATE, \n\tprovenance_json JSON NOT NULL, \n\treview_task_id VARCHAR(36), \n\tapproved_by VARCHAR(160), \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (knowledge_version_id), \n\tCONSTRAINT uq_knowledge_document_version UNIQUE (tenant_id, document_id, version), \n\tCONSTRAINT ck_knowledge_document_version CHECK (version > 0), \n\tCONSTRAINT ck_knowledge_effective_dates CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from), \n\tCONSTRAINT ck_knowledge_lifecycle CHECK (lifecycle IN ('DRAFT','INGESTED','VALIDATED','PENDING_REVIEW','APPROVED','ACTIVE','SUPERSEDED','EXPIRED','ARCHIVED')), \n\tFOREIGN KEY(document_id) REFERENCES knowledge_documents (document_id), \n\tFOREIGN KEY(collection_version_id) REFERENCES knowledge_collection_versions (knowledge_collection_version_id), \n\tFOREIGN KEY(review_task_id) REFERENCES admin_review_tasks (review_task_id)\n)\n\n",
    "\nCREATE TABLE embedding_jobs (\n\tembedding_job_id VARCHAR(36) NOT NULL, \n\tknowledge_version_id VARCHAR(36) NOT NULL, \n\tmodel_config_id VARCHAR(36) NOT NULL, \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (embedding_job_id), \n\tFOREIGN KEY(knowledge_version_id) REFERENCES knowledge_document_versions (knowledge_version_id), \n\tFOREIGN KEY(model_config_id) REFERENCES model_deployments (model_deployment_id)\n)\n\n",
    "\nCREATE TABLE knowledge_change_events (\n\tevent_id VARCHAR(36) NOT NULL, \n\tknowledge_version_id VARCHAR(36) NOT NULL, \n\tevent_type VARCHAR(80) NOT NULL, \n\tprovenance_json JSON NOT NULL, \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (event_id), \n\tFOREIGN KEY(knowledge_version_id) REFERENCES knowledge_document_versions (knowledge_version_id)\n)\n\n",
    "\nCREATE TABLE knowledge_chunks (\n\tchunk_id VARCHAR(36) NOT NULL, \n\tknowledge_version_id VARCHAR(36) NOT NULL, \n\tchunk_type VARCHAR(40) NOT NULL, \n\toriginal_text TEXT NOT NULL, \n\tnormalized_text TEXT NOT NULL, \n\ttoken_count INTEGER NOT NULL, \n\tlanguage VARCHAR(80) NOT NULL, \n\tsequence INTEGER NOT NULL, \n\tcanonical_locator VARCHAR(500) NOT NULL, \n\tcontent_hash VARCHAR(64) NOT NULL, \n\tchunking_strategy_version VARCHAR(80) NOT NULL, \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (chunk_id), \n\tCONSTRAINT uq_knowledge_chunk_sequence UNIQUE (tenant_id, knowledge_version_id, sequence), \n\tCONSTRAINT ck_knowledge_chunk_tokens CHECK (token_count > 0), \n\tFOREIGN KEY(knowledge_version_id) REFERENCES knowledge_document_versions (knowledge_version_id)\n)\n\n",
    "\nCREATE TABLE knowledge_index_versions (\n\tindex_version_id VARCHAR(36) NOT NULL, \n\tknowledge_version_id VARCHAR(36) NOT NULL, \n\tchunking_strategy_version VARCHAR(80) NOT NULL, \n\tembedding_config_id VARCHAR(36), \n\tfts_config_version VARCHAR(80) NOT NULL, \n\tbuild_status VARCHAR(40) NOT NULL, \n\tbuilt_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tcontent_hash VARCHAR(64) NOT NULL, \n\tderived BOOLEAN NOT NULL, \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (index_version_id), \n\tFOREIGN KEY(knowledge_version_id) REFERENCES knowledge_document_versions (knowledge_version_id), \n\tFOREIGN KEY(embedding_config_id) REFERENCES model_deployments (model_deployment_id)\n)\n\n",
    "\nCREATE TABLE knowledge_ingestion_runs (\n\tingestion_run_id VARCHAR(36) NOT NULL, \n\tknowledge_version_id VARCHAR(36) NOT NULL, \n\tidempotency_key VARCHAR(160) NOT NULL, \n\trequest_hash VARCHAR(64) NOT NULL, \n\tinput_json JSON NOT NULL, \n\taudit_json JSON NOT NULL, \n\terror_code VARCHAR(80), \n\toutbox_event_id VARCHAR(36) NOT NULL, \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (ingestion_run_id), \n\tCONSTRAINT uq_knowledge_ingestion_idempotency UNIQUE (tenant_id, knowledge_version_id, idempotency_key), \n\tFOREIGN KEY(knowledge_version_id) REFERENCES knowledge_document_versions (knowledge_version_id), \n\tFOREIGN KEY(outbox_event_id) REFERENCES registry_sync_events (registry_sync_event_id)\n)\n\n",
    "\nCREATE TABLE knowledge_quality_results (\n\tquality_id VARCHAR(36) NOT NULL, \n\tknowledge_version_id VARCHAR(36) NOT NULL, \n\tchecks_json JSON NOT NULL, \n\treason_codes_json JSON NOT NULL, \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (quality_id), \n\tCONSTRAINT uq_knowledge_quality_version UNIQUE (knowledge_version_id), \n\tFOREIGN KEY(knowledge_version_id) REFERENCES knowledge_document_versions (knowledge_version_id)\n)\n\n",
    "\nCREATE TABLE knowledge_translations (\n\ttranslation_id VARCHAR(36) NOT NULL, \n\tknowledge_version_id VARCHAR(36) NOT NULL, \n\tsource_language VARCHAR(80) NOT NULL, \n\ttarget_language VARCHAR(80) NOT NULL, \n\ttranslated_text_ref VARCHAR(500) NOT NULL, \n\ttranslation_method VARCHAR(40) NOT NULL, \n\tmodel_config_id VARCHAR(36), \n\treviewer VARCHAR(160), \n\treview_status VARCHAR(40) NOT NULL, \n\tprovenance_json JSON NOT NULL, \n\tversion INTEGER NOT NULL, \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (translation_id), \n\tCONSTRAINT ck_translation_reviewer CHECK (review_status <> 'APPROVED' OR reviewer IS NOT NULL), \n\tFOREIGN KEY(knowledge_version_id) REFERENCES knowledge_document_versions (knowledge_version_id), \n\tFOREIGN KEY(model_config_id) REFERENCES model_deployments (model_deployment_id)\n)\n\n",
    "\nCREATE TABLE knowledge_version_diffs (\n\tdiff_id VARCHAR(36) NOT NULL, \n\told_version_id VARCHAR(36) NOT NULL, \n\tnew_version_id VARCHAR(36) NOT NULL, \n\tchanges_json JSON NOT NULL, \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (diff_id), \n\tFOREIGN KEY(old_version_id) REFERENCES knowledge_document_versions (knowledge_version_id), \n\tFOREIGN KEY(new_version_id) REFERENCES knowledge_document_versions (knowledge_version_id)\n)\n\n",
    "\nCREATE TABLE embedding_records (\n\tembedding_record_id VARCHAR(36) NOT NULL, \n\tembedding_job_id VARCHAR(36) NOT NULL, \n\tchunk_id VARCHAR(36) NOT NULL, \n\tmodel_config_id VARCHAR(36) NOT NULL, \n\tembedding_dimension INTEGER NOT NULL, \n\tembedding_version VARCHAR(80) NOT NULL, \n\tvector_hash VARCHAR(64) NOT NULL, \n\tgenerated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (embedding_record_id), \n\tCONSTRAINT uq_embedding_record_version UNIQUE (tenant_id, chunk_id, model_config_id, embedding_version), \n\tCONSTRAINT ck_embedding_dimension CHECK (embedding_dimension > 0), \n\tFOREIGN KEY(embedding_job_id) REFERENCES embedding_jobs (embedding_job_id), \n\tFOREIGN KEY(chunk_id) REFERENCES knowledge_chunks (chunk_id), \n\tFOREIGN KEY(model_config_id) REFERENCES model_deployments (model_deployment_id)\n)\n\n",
    "\nCREATE TABLE knowledge_structure_nodes (\n\tstructure_node_id VARCHAR(36) NOT NULL, \n\tregulatory_structure_node_id VARCHAR(36), \n\tknowledge_version_id VARCHAR(36) NOT NULL, \n\tparent_node_id VARCHAR(36), \n\tnode_type VARCHAR(40) NOT NULL, \n\tsequence INTEGER NOT NULL, \n\tcanonical_locator VARCHAR(500) NOT NULL, \n\tofficial_number VARCHAR(100), \n\theading TEXT NOT NULL, \n\toriginal_text TEXT NOT NULL, \n\tnormalized_text TEXT NOT NULL, \n\tlanguage VARCHAR(80) NOT NULL, \n\teffective_date DATE, \n\tsource_trace_json JSON NOT NULL, \n\tprovenance_json JSON NOT NULL, \n\tcitation_id VARCHAR(36) NOT NULL, \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (structure_node_id), \n\tCONSTRAINT uq_knowledge_structure_locator UNIQUE (tenant_id, knowledge_version_id, canonical_locator), \n\tCONSTRAINT uq_knowledge_legal_node_extension UNIQUE (regulatory_structure_node_id), \n\tFOREIGN KEY(regulatory_structure_node_id) REFERENCES regulatory_structure_nodes (regulatory_structure_node_id), \n\tFOREIGN KEY(knowledge_version_id) REFERENCES knowledge_document_versions (knowledge_version_id), \n\tFOREIGN KEY(parent_node_id) REFERENCES knowledge_structure_nodes (structure_node_id), \n\tFOREIGN KEY(citation_id) REFERENCES citations (citation_id)\n)\n\n",
    "\nCREATE TABLE knowledge_chunk_nodes (\n\tchunk_id VARCHAR(36) NOT NULL, \n\tstructure_node_id VARCHAR(36) NOT NULL, \n\ttenant_id VARCHAR(36) NOT NULL, \n\trecord_version INTEGER DEFAULT '1' NOT NULL, \n\tstatus VARCHAR(40) DEFAULT 'ACTIVE' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (chunk_id, structure_node_id), \n\tFOREIGN KEY(chunk_id) REFERENCES knowledge_chunks (chunk_id), \n\tFOREIGN KEY(structure_node_id) REFERENCES knowledge_structure_nodes (structure_node_id)\n)\n\n",
    "CREATE INDEX ix_knowledge_documents_tenant_id ON knowledge_documents (tenant_id)",
    "CREATE INDEX ix_knowledge_scope_resolutions_tenant_id ON knowledge_scope_resolutions (tenant_id)",
    "CREATE INDEX ix_knowledge_document_versions_tenant_id ON knowledge_document_versions (tenant_id)",
    "CREATE INDEX ix_embedding_jobs_tenant_id ON embedding_jobs (tenant_id)",
    "CREATE INDEX ix_knowledge_change_events_tenant_id ON knowledge_change_events (tenant_id)",
    "CREATE INDEX ix_knowledge_chunks_tenant_id ON knowledge_chunks (tenant_id)",
    "CREATE INDEX ix_knowledge_index_versions_tenant_id ON knowledge_index_versions (tenant_id)",
    "CREATE INDEX ix_knowledge_ingestion_runs_tenant_id ON knowledge_ingestion_runs (tenant_id)",
    "CREATE INDEX ix_knowledge_quality_results_tenant_id ON knowledge_quality_results (tenant_id)",
    "CREATE INDEX ix_knowledge_translations_tenant_id ON knowledge_translations (tenant_id)",
    "CREATE INDEX ix_knowledge_version_diffs_tenant_id ON knowledge_version_diffs (tenant_id)",
    "CREATE INDEX ix_embedding_records_tenant_id ON embedding_records (tenant_id)",
    "CREATE INDEX ix_knowledge_structure_nodes_tenant_id ON knowledge_structure_nodes (tenant_id)",
    "CREATE INDEX ix_knowledge_chunk_nodes_tenant_id ON knowledge_chunk_nodes (tenant_id)",
    "ALTER TABLE knowledge_bindings ADD COLUMN knowledge_version_id VARCHAR(36) REFERENCES knowledge_document_versions(knowledge_version_id)",
    "ALTER TABLE knowledge_bindings ADD COLUMN binding_version INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE knowledge_bindings ADD COLUMN dimensions_json JSON NOT NULL DEFAULT '{}'",
    "ALTER TABLE knowledge_bindings ADD COLUMN permission_scopes_json JSON NOT NULL DEFAULT '[]'",
    "ALTER TABLE knowledge_bindings ADD COLUMN provenance_json JSON NOT NULL DEFAULT '{}'",
    "ALTER TABLE knowledge_bindings ADD COLUMN review_status VARCHAR(40) NOT NULL DEFAULT 'PENDING'",
    "CREATE UNIQUE INDEX uq_active_knowledge_document ON knowledge_document_versions(tenant_id, document_id) WHERE lifecycle='ACTIVE'",
    "CREATE EXTENSION IF NOT EXISTS vector",
    "ALTER TABLE embedding_records ADD COLUMN embedding_vector vector",
    "ALTER TABLE embedding_records ADD CONSTRAINT ck_embedding_vector_dimension CHECK (embedding_vector IS NULL OR vector_dims(embedding_vector)=embedding_dimension)",
    "ALTER TABLE knowledge_chunks ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, normalized_text)) STORED",
    "CREATE INDEX ix_knowledge_chunks_fts ON knowledge_chunks USING gin(search_vector)",
]
DOWNGRADE_STATEMENTS = [
    "ALTER TABLE knowledge_bindings DROP COLUMN knowledge_version_id",
    "ALTER TABLE knowledge_bindings DROP COLUMN binding_version",
    "ALTER TABLE knowledge_bindings DROP COLUMN dimensions_json",
    "ALTER TABLE knowledge_bindings DROP COLUMN permission_scopes_json",
    "ALTER TABLE knowledge_bindings DROP COLUMN provenance_json",
    "ALTER TABLE knowledge_bindings DROP COLUMN review_status",
    "DROP TABLE knowledge_chunk_nodes",
    "DROP TABLE knowledge_structure_nodes",
    "DROP TABLE embedding_records",
    "DROP TABLE knowledge_version_diffs",
    "DROP TABLE knowledge_translations",
    "DROP TABLE knowledge_quality_results",
    "DROP TABLE knowledge_ingestion_runs",
    "DROP TABLE knowledge_index_versions",
    "DROP TABLE knowledge_chunks",
    "DROP TABLE knowledge_change_events",
    "DROP TABLE embedding_jobs",
    "DROP TABLE knowledge_document_versions",
    "DROP TABLE knowledge_scope_resolutions",
    "DROP TABLE knowledge_documents",
]


def upgrade():
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade():
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
