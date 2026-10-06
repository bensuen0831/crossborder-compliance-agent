"""Loopback-only M1 UAT composition using existing E/F/G/H/I services and fixtures."""
import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_phase1f_postgres import fixture
from test_phase1i_postgres import foundation_i, execute

def seed(label, partial=False):
    f = foundation_i.__wrapped__(fixture.__wrapped__(), SimpleNamespace(param={'partial': True} if partial else {}))
    result = execute(f)
    classification = f['classification'].result
    assert classification is not None
    return {
        'tenant_id': f['tenant'], 'actor_id': 'author', 'display_name': f'UAT User {label}',
        'tenant_label': f'Synthetic Tenant {label}', 'permissions': sorted(f['ctx'].permission.scopes),
        'contexts': [{'project_id': f['project'], 'display_name': f'Generic Project · UAT {label}',
                      'analysis_snapshot_id': f['snapshot'], 'policy_id': f['policy']['policy_id']}],
        'm1': {'classification': str(classification.classification_result_id), 'applicability': str(result.applicability_result_id),
               'retrieval': f['retrieval']['retrieval_run_id'], 'status': result.applicability_status,
               'scenario': f['scenario'], 'product': f['a'], 'jurisdiction': f['juri'], 'item': f['item'],
               'official_text': f['retrieval']['rag_context_pack']['evidence_pack']['items'][0]['original_text']},
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--seed', action='store_true')
    parser.add_argument('--port', type=int, default=8010)
    args = parser.parse_args()
    if os.environ.get('M0_LOCAL_UAT') != '1':
        raise SystemExit('Explicit M0_LOCAL_UAT=1 required')
    if args.seed:
        if args.manifest.exists(): raise SystemExit('Use a fresh manifest; no reset')
        args.manifest.write_text(json.dumps({'A': seed('A'), 'B': seed('B', partial=True)}, indent=2)+'\n')
        print('Seeded actual canonical classification/applicability/evidence for two isolated tenants')
        return
    from scripts.m0_preview.server import create_demo_app
    from crossborder_compliance.interfaces.api.main import country_compliance_router
    import uvicorn
    app = create_demo_app(args.manifest)
    app.include_router(country_compliance_router)
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)

if __name__ == '__main__': main()
