"""M1 frontend contracts exported from verified Phase1J models; no backend writes."""
import json
from pathlib import Path
from crossborder_compliance.domain.classification import ClassificationResult
from crossborder_compliance.domain.regulation_applicability import RegulationApplicabilityResult
from crossborder_compliance.domain.contracts import ProjectIntakeContext
out = Path(__file__).resolve().parents[2] / 'src/api/m1-schemas.json'
schemas = {}
for cls in [ClassificationResult, RegulationApplicabilityResult, ProjectIntakeContext]:
    spec = cls.model_json_schema(ref_template='#/components/schemas/{model}')
    schemas.update(spec.pop('$defs', {}))
    schemas[cls.__name__] = spec
from fastapi import FastAPI
from crossborder_compliance.interfaces.api.routes.workflow import router
app = FastAPI()
app.include_router(router)
workflow = app.openapi()
schemas.update(workflow['components']['schemas'])
out.write_text(json.dumps({'openapi': '3.1.0', 'info': {'title': 'M1 baseline models', 'version': 'phase1j'}, 'paths': workflow['paths'], 'components': {'schemas': schemas}}, indent=2) + '\n')
