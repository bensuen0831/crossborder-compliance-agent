"""Additive engine compatibility checks; no legal rules or historical checks removed."""
import ast
import subprocess
from pathlib import Path

def check(root):
    root=Path(root)
    read=lambda p:(root/p).read_text()
    engine=read('src/crossborder_compliance/domain/decision_engine.py')
    versions=read('src/crossborder_compliance/domain/decision_calculation_versions.py')
    contract=read('src/crossborder_compliance/domain/decision_contracts.py')
    service=read('src/crossborder_compliance/application/decision_services.py')
    repository=read('src/crossborder_compliance/infrastructure/persistence/decision_repository.py')
    migration=read('alembic/versions/0020_stage1_formal_decision_engine_compatibility.py')
    old=ast.parse(subprocess.check_output(['git','show','4c79243bbfa22108f1005c8e92265e2137012d4d:src/crossborder_compliance/domain/decision_engine.py'],cwd=root))
    expected=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name=='merge_support')
    actual=next(n for n in ast.parse(versions).body if isinstance(n,ast.FunctionDef) and n.name=='legacy_merge_support');actual.name='merge_support'
    functions={n.name:n for n in ast.parse(service).body if isinstance(n,ast.FunctionDef)}
    return {
        'decision_legacy_merger_matches_frozen_source':ast.dump(expected)==ast.dump(actual),
        'decision_strategy_is_immutable_and_not_global_mutation':'@dataclass(frozen=True)' in versions and not any(x in versions+engine for x in ('monkeypatch','ContextVar','setattr(', 'os.environ')),
        'decision_new_execution_has_no_version_selector':len(functions['calculate'].args.args)==3 and 'CORRECTED_CALCULATION' in ast.unparse(functions['calculate']),
        'decision_verifier_dispatches_explicit_saved_version':'verify_calculation(stage, inputs, parents, saved.engine_version)' in repository and 'DecisionEngineVersion(engine_version)' in service,
        'decision_full_digest_revalidation_is_preserved':'result_digest(saved) != result_digest(current)' in repository and 'saved decision no longer revalidates' in repository,
        'decision_versions_agree_row_json_provenance':all(x in repository for x in ('row.engine_version','row.provenance_json["engine_version"]','result.engine_version','result.provenance.engine_version','ENGINE_VERSION_MISMATCH')),
        'decision_legacy_snapshot_cannot_new_execute':all(x in repository+service for x in ('LEGACY_DECISION_SNAPSHOT_READ_ONLY','LEGACY_DECISION_EXECUTION_FORBIDDEN','FORMAL_DECISION_MIXED_ENGINE_VERSIONS')),
        'decision_compatibility_migration_is_bounded_and_refuses_loss':all(x in migration for x in ('0019_stage1_candidate_governance','FORMAL_DECISION_V2_1','DOWNGRADE_REFUSED')) and not any(x in migration for x in ('create_table','drop_table','UPDATE ','DELETE ','alter_column')),
    }
