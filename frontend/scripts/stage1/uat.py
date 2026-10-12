"""Loopback-only full business UAT; all projects are created by the Browser.

Fixture operators publish synthetic governed configuration. The browser actor
has no metadata administrator grants and receives zero preset project contexts.
"""
import argparse
import json
import os
import sys
from contextlib import ExitStack
from pathlib import Path
from uuid import UUID

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]

from stage1_business_fixtures import business_environment
from scripts.m0_preview.server import create_demo_app
from test_phase1c_model_registry import _ctx
from crossborder_compliance.infrastructure.document_storage import FileObjectStorageAdapter
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.intake import router as intake_router
from crossborder_compliance.interfaces.api.routes.intake_documents import router as document_router
from crossborder_compliance.interfaces.api.routes.workflow import router as workflow_router
from crossborder_compliance.interfaces.api.routes.reviews import router as review_router
from crossborder_compliance.interfaces.api.routes.external import router as external_router
from crossborder_compliance.interfaces.api.routes.integrations import admin_router


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--private-root',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8010)
    args=parser.parse_args()
    if os.environ.get('M0_LOCAL_UAT')!='1' or os.environ.get('STAGE1_LOCAL_UAT')!='1':
        raise SystemExit('Explicit loopback-only STAGE1_LOCAL_UAT=1 required')
    if args.manifest.exists():raise SystemExit('Use a new isolated manifest; no reset')
    args.private_root.mkdir(parents=True,exist_ok=True)
    with ExitStack() as stack:
        universes={outcome:stack.enter_context(business_environment(args.private_root/outcome,outcome))
                   for outcome in ('DIRECT','CONDITIONAL','LOCALIZATION','REVIEW')}
        people={}
        for outcome,f in universes.items():
            common=dict(tenant_id=f['tenant'],tenant_label='Synthetic Stage1 tenant',contexts=[],intake=f['facts'],models=f['model_ids'],expected=f['expected'])
            people[outcome]=dict(common,actor_id=f['user'].permission.actor_id,display_name='Business user',permissions=sorted(f['user'].permission.scopes))
            scopes=sorted(_ctx(UUID(f['tenant'])).permission.scopes)
            for role in ('ADMIN','REVIEWER'):
                people[outcome+'_'+role]=dict(common,actor_id='fixture-'+role.lower(),display_name='Independent configuration '+role,permissions=scopes)
            people[outcome]['project_policy_payload']=dict(scope_type='PROJECT',default_mode='INTERNAL_MODEL_ONLY',allowed_operations=['structured_output'],allowed_model_ids=f['model_ids'],allowed_trust_levels=['APPROVED'],allowed_data_boundaries=['TENANT'])
        people['A']=people['DIRECT']
        args.manifest.parent.mkdir(parents=True,exist_ok=True)
        args.manifest.write_text(json.dumps(people,indent=2)+'\n')
        app=create_demo_app(args.manifest)
        # Only canonical application routes; no fixture business-result endpoint.
        for router in (admin_router,intake_router,document_router,workflow_router,review_router,external_router):
            previous=len(app.router.routes);app.include_router(router)
            if router is admin_router:app.router.routes=app.router.routes[previous:]+app.router.routes[:previous]
        first=universes['DIRECT']
        app.state.knowledge_session_factory=first['sf']
        app.state.integration_policy=first['app'].state.integration_policy
        app.state.document_file_policy=first['app'].state.document_file_policy
        app.state.document_object_storage=FileObjectStorageAdapter(str(args.private_root/'objects'))
        by_tenant={f['tenant']:f for f in universes.values()}
        app.state.llm_secret_store_factory=lambda ctx:by_tenant[str(ctx.tenant_id)]['app'].state.llm_secret_store_factory(ctx)
        # create_demo_app obtains RepositoryContext from its HttpOnly loopback
        # session; no dependency override or client-selected scopes are installed.
        assert get_repository_context not in app.dependency_overrides
        import uvicorn
        uvicorn.run(app,host='127.0.0.1',port=args.port,access_log=False)


if __name__=='__main__':main()
