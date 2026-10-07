"""Export only the additive canonical Stage 1 projection endpoint."""
import json
from pathlib import Path
from fastapi import FastAPI
from crossborder_compliance.interfaces.api.routes.workflow import router
app=FastAPI();app.include_router(router)
spec=app.openapi()
spec['paths']={path:value for path,value in spec['paths'].items() if path.endswith('/stage1-result')}
output=Path(__file__).resolve().parents[2]/'src/api/m2c-schemas.json'
output.write_text(json.dumps(spec,indent=2)+'\n')
