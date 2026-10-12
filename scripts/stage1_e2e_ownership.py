"""Finite R2/approved0020 successor, authenticated exclusively from committed Git blobs.

Historical manifests remain immutable. Legal calculation bodies remain the
original owner; only strategy/version metadata and the approved helper differ.
"""
import ast
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

BASE = "4c79243bbfa22108f1005c8e92265e2137012d4d"
FORMAL_BASE = "df3a10923734495d728981f4f319b66afadf8c71"
RECORD = "evidence/stage1-full-e2e/r2/approved_owner_overlay.json"
PATHS = frozenset((
    'tests/test_m2e_r1_architecture.py',
    'tests/test_phase1kb_architecture.py',
    'tests/test_m2c_architecture.py',
    'tests/test_m2d_architecture.py',
    'scripts/m1_phase1lb_ownership.py',
    'scripts/phase1kb_ownership.py',
    'ARCHITECTURE_RULES.md',
    'alembic/versions/0020_stage1_formal_decision_engine_compatibility.py',
    'frontend/e2e/stage1-business.spec.ts',
    'frontend/scripts/stage1/uat.py',
    'frontend/src/api/m1-generated.ts',
    'frontend/src/api/m1-schemas.json',
    'frontend/src/api/m2a-generated.ts',
    'frontend/src/api/m2a-schemas.json',
    'frontend/src/api/m2c-generated.ts',
    'frontend/src/api/m2c-schemas.json',
    'frontend/src/api/m2d-generated.ts',
    'frontend/src/api/m2d-schemas.json',
    'frontend/src/features/intake/IntakeFeature.tsx',
    'frontend/src/features/intake/contracts.ts',
    'frontend/src/features/intake/persistence.ts',
    'frontend/src/locales/en-US.json',
    'frontend/src/locales/zh-CN.json',
    'frontend/src/locales/zh-HK.json',
    'scripts/architecture_rule_check.py',
    'scripts/m2e_r1_ownership.py',
    'scripts/stage1_candidate_closure.py',
    'scripts/stage1_candidate_ownership.py',
    'scripts/stage1_decision_compatibility_architecture.py',
    'scripts/stage1_e2e_ownership.py',
    'sdk/openapi/external-v1.json',
    'sdk/python/src/crossborder_agent/external-v1.json',
    'sdk/typescript/src/generated.ts',
    'src/crossborder_compliance/application/context_ports.py',
    'src/crossborder_compliance/application/context_services.py',
    'src/crossborder_compliance/application/decision_services.py',
    'src/crossborder_compliance/application/structured_dataflow.py',
    'src/crossborder_compliance/application/workflow_formal.py',
    'src/crossborder_compliance/domain/contracts.py',
    'src/crossborder_compliance/domain/decision_calculation_versions.py',
    'src/crossborder_compliance/domain/decision_contracts.py',
    'src/crossborder_compliance/domain/decision_engine.py',
    'src/crossborder_compliance/infrastructure/intake_composition.py',
    'src/crossborder_compliance/infrastructure/persistence/context_repositories.py',
    'src/crossborder_compliance/infrastructure/persistence/decision_models.py',
    'src/crossborder_compliance/infrastructure/persistence/decision_repository.py',
    'src/crossborder_compliance/infrastructure/persistence/structured_intake.py',
    'tests/stage1_business_fixtures.py',
    'tests/stage1_external_business.py',
    'tests/stage1_formal_acceptance.py',
    'tests/stage1_legacy_history.py',
    'tests/test_stage1_business_http.py',
    'tests/test_stage1_candidate_governance_migrations.py',
    'tests/test_stage1_channel_parity.py',
    'tests/test_stage1_dataflow_http.py',
    'tests/test_stage1_decision_compatibility_architecture.py',
    'tests/test_stage1_decision_compatibility_migrations.py',
    'tests/test_stage1_decision_versions.py',
    'tests/test_stage1_support_historical.py',
    'tests/test_stage1_support_merge.py',
    'tests/test_stage1_support_pipeline.py',
))

class OriginalCalculationBody(ast.NodeTransformer):
    def visit_Name(self,node):
        if node.id == "envelope":node.id="_envelope"
        return node
    def visit_Attribute(self,node):
        if isinstance(node.value,ast.Name) and node.value.id=="_calculation" and node.attr=="merge_support":
            return ast.Name(id="merge_support",ctx=node.ctx)
        return self.generic_visit(node)

def legal_bodies_preserved(original,current):
    old={n.name:n for n in ast.parse(original).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    now={n.name:n for n in ast.parse(current).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    for name in ("obligations","candidates","risks","recommendation","final_path"):
        node=now[name];node.args.kwonlyargs=[];node.args.kw_defaults=[]
        if isinstance(node.body[0],ast.Assign) and isinstance(node.body[0].targets[0],ast.Name) and node.body[0].targets[0].id=="envelope":node.body.pop(0)
        node=OriginalCalculationBody().visit(node)
        if ast.dump(node)!=ast.dump(old[name]):return False
    return all(ast.dump(node)==ast.dump(now[name]) for name,node in old.items() if isinstance(node,ast.ClassDef))

def overlay(root,previous_paths):
    root=Path(root).resolve()
    from scripts.stage1_candidate_ownership import OWNER_PATHS
    def git(*args):return subprocess.check_output(["git","-c","core.quotepath=false",*args],cwd=root,stderr=subprocess.DEVNULL)
    def ancestor(a,b):return subprocess.run(["git","merge-base","--is-ancestor",a,b],cwd=root,stderr=subprocess.DEVNULL).returncode==0
    def blobs(source,paths):
        with tarfile.open(fileobj=io.BytesIO(git("archive",source,"--",*sorted(paths)))) as archive:
            return {f.name:archive.extractfile(f).read() for f in archive if f.isfile()}
    try:
        historical=set()
        for path in ("evidence/m2e/r1_approved_owner_overlay.json","evidence/m2e/resume_approved_owner_overlay.json","evidence/stage1-full-e2e/r11_approved_owner_overlay.json"):
            frozen=git("show",BASE+":"+path)
            if (root/path).read_bytes()!=frozen:return False,{},None
            data=json.loads(frozen);source=data["source_sha"]
            if not ancestor(data["base_sha"],source) or not ancestor(source,BASE):return False,{},None
            originals=blobs(source,data["paths"])
            if any(hashlib.sha256(originals[p]).hexdigest()!=h for p,h in data["paths"].items()):return False,{},None
            historical.update(data["paths"])
        if historical!=set(previous_paths)|OWNER_PATHS:return False,{},None
        record=json.loads((root/RECORD).read_text());source=record["source_sha"]
        expected=historical|PATHS
        if record["base_sha"]!=BASE or set(record["paths"])!=expected or not ancestor(BASE,source) or not ancestor(source,"HEAD"):return False,{},None
        committed=blobs(source,expected)
        if any(hashlib.sha256(committed[p]).hexdigest()!=h or (root/p).read_bytes()!=committed[p] for p,h in record["paths"].items()):return False,{},None
        files=git("ls-tree","-r","--name-only",BASE).decode().splitlines()
        originals=blobs(BASE,files)
        if any((root/p).read_bytes()!=originals[p] for p in files if p not in PATHS):return False,{},None
        changes=set(git("diff","--name-only",BASE,source).decode().splitlines())|set(git("diff","--name-only",BASE).decode().splitlines())|set(git("ls-files","--others","--exclude-standard").decode().splitlines())
        if any(p not in PATHS and not p.startswith(("docs/stage1-e2e/","evidence/stage1-full-e2e/")) and p!="Phase1H_integration_closure.md" for p in changes):return False,{},None
        engine="src/crossborder_compliance/domain/decision_engine.py"
        if not legal_bodies_preserved(originals[engine],(root/engine).read_bytes()):return False,{},None
        user=root/"Phase1H_integration_closure.md"
        if user.exists() and hashlib.sha256(user.read_bytes()).hexdigest()!="c9530e2a9c36746deadc143e3e94ab982c370650b653758ebe2f1d1aeb19ec37":return False,{},None
        return True,record["paths"],source
    except (OSError,KeyError,ValueError,subprocess.CalledProcessError):return False,{},None
