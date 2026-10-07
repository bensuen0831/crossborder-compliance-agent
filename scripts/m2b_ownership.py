"""Finite committed M2-B owner transfer; frozen prior evidence remains intact."""
import hashlib
import json
import subprocess
from pathlib import Path

BASE = 'da2d420602d9c71991bcae4ffd3d33c9b3497d25'
MIGRATIONS = frozenset({'alembic/versions/0012_m2b_document_inputs.py','alembic/versions/0013_m2b_context_temporal_contract.py'})
# Exact implementation ownership, never an arbitrary prefix authorization.
SHARED = frozenset({
    '.github/workflows/m1-alpha.yml',
    '.github/workflows/m2a-intake.yml',
    '.github/workflows/m2b-documents.yml',
    '.github/workflows/phase1a-runtime-smoke.yml',
    'alembic/versions/0012_m2b_document_inputs.py',
    'alembic/versions/0013_m2b_context_temporal_contract.py',
    'frontend/e2e/m2b.spec.ts',
    'frontend/scripts/m2a/export_contracts.py',
    'frontend/scripts/m2a/uat.py',
    'frontend/src/api/client.ts',
    'frontend/src/api/m2a-generated.ts',
    'frontend/src/api/m2a-schemas.json',
    'frontend/src/features/intake/DocumentInputs.tsx',
    'frontend/src/features/intake/IntakeFeature.tsx',
    'frontend/src/features/intake/ProductionIntake.tsx',
    'frontend/src/features/intake/documentApi.ts',
    'frontend/src/features/intake/m2b.test.tsx',
    'frontend/src/features/intake/persistence.ts',
    'frontend/src/locales/en-US.json',
    'frontend/src/locales/zh-CN.json',
    'frontend/src/locales/zh-HK.json',
    'scripts/m2a_architecture_check.py',
    'scripts/m2a_ownership.py',
    'scripts/m2b_architecture_check.py',
    'scripts/m2b_ownership.py',
    'scripts/phase1e_schema_check.py',
    'scripts/phase1j_ownership.py',
    'scripts/phase1l_b_ownership.py',
    'scripts/stage1_alpha_integrity.py',
    'smoke/run_gate.sh',
    'src/crossborder_compliance/application/context_ports.py',
    'src/crossborder_compliance/application/context_services.py',
    'src/crossborder_compliance/application/document_services.py',
    'src/crossborder_compliance/application/document_upload.py',
    'src/crossborder_compliance/application/workflow_formal.py',
    'src/crossborder_compliance/infrastructure/document_input_composition.py',
    'src/crossborder_compliance/infrastructure/document_storage.py',
    'src/crossborder_compliance/infrastructure/intake_composition.py',
    'src/crossborder_compliance/infrastructure/persistence/classification_repository.py',
    'src/crossborder_compliance/infrastructure/persistence/context_models.py',
    'src/crossborder_compliance/infrastructure/persistence/context_repositories.py',
    'src/crossborder_compliance/infrastructure/persistence/context_temporal.py',
    'src/crossborder_compliance/infrastructure/persistence/country_compliance_repository.py',
    'src/crossborder_compliance/infrastructure/persistence/document_models.py',
    'src/crossborder_compliance/infrastructure/persistence/document_repositories.py',
    'src/crossborder_compliance/infrastructure/persistence/document_snapshot_inputs.py',
    'src/crossborder_compliance/infrastructure/persistence/knowledge_repositories.py',
    'src/crossborder_compliance/infrastructure/persistence/project_document_inputs.py',
    'src/crossborder_compliance/infrastructure/persistence/project_intake.py',
    'src/crossborder_compliance/infrastructure/persistence/structured_intake.py',
    'src/crossborder_compliance/infrastructure/workflow_formal_composition.py',
    'src/crossborder_compliance/interfaces/api/routes/intake_documents.py',
    'src/crossborder_compliance/interfaces/api/workflow_app.py',
    'tests/m2b_legacy_seed.py',
    'tests/m2b_parse_worker.py',
    'tests/test_m2a_migrations.py',
    'tests/test_m2b_architecture.py',
    'tests/test_m2b_document_inputs.py',
    'tests/test_m2b_file_policy.py',
    'tests/test_m2b_integration.py',
    'tests/test_m2b_migrations.py',
    'tests/test_m2b_ownership.py',
    'tests/test_m2b_snapshot_contract_probe.py',
    'tests/test_m2b_temporal_postgres.py',
    'tests/test_phase1d_postgres.py',
    'tests/test_phase1f_postgres.py',
    'tests/test_phase1f_snapshot_scope.py',
    'tests/test_phase1g_publication_postgres.py',
    'tests/test_phase1h_postgres.py',
    'tests/test_phase1i_postgres.py',
    'tests/test_phase1j_postgres.py',
})


def overlay(root):
    root=Path(root); record=root/'evidence/m2b/approved_owner_overlay.json'
    if not record.exists(): return False,{},None
    try:
        data=json.loads(record.read_text()); source=data['source_sha']
        def git(*args): return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL)
        def ancestor(a,b): return subprocess.run(['git','merge-base','--is-ancestor',a,b],cwd=root,stderr=subprocess.DEVNULL).returncode==0
        valid=data['base_sha']==BASE and source!=BASE and ancestor(BASE,source) and ancestor(source,'HEAD') and set(data['paths'])==SHARED
        valid=valid and all(hashlib.sha256(git('show',source+':'+p)).hexdigest()==h and (root/p).read_bytes()==git('show',source+':'+p) for p,h in data['paths'].items())
        old=set(git('ls-tree','-r','--name-only',BASE,'--','alembic/versions').decode().splitlines())
        now={str(p.relative_to(root)) for p in (root/'alembic/versions').glob('*.py')}
        valid=valid and now==old|MIGRATIONS and all((root/p).read_bytes()==git('show',BASE+':'+p) for p in old)
        protected=['ARCHITECTURE_RULES.md','frontend/package.json','frontend/package-lock.json','pyproject.toml']
        protected+=git('ls-tree','-r','--name-only',BASE,'--','src/crossborder_compliance/domain','src/crossborder_compliance/workflows','evidence/m2a','evidence/phase1j','evidence/phase1l_b','evidence/integration/m1-phase1lb').decode().splitlines()
        valid=valid and all((root/p).read_bytes()==git('show',BASE+':'+p) for p in protected)
        delta=set(git('diff','--name-only',BASE,source).decode().splitlines())
        valid=valid and all(p in SHARED or p.startswith(('docs/m2b/','evidence/m2b/')) for p in delta)
        return valid,data['paths'],source
    except (OSError,KeyError,ValueError,subprocess.CalledProcessError): return False,{},None
