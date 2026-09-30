from fastapi.testclient import TestClient
from crossborder_compliance.interfaces.api.main import app
client=TestClient(app)
def test_live(): assert client.get("/health/live").json()=={"status":"ok"}
def test_metadata_is_empty_registry_skeleton():
    body=client.get("/api/v1/metadata/bootstrap").json(); assert body["products"]==[] and body["jurisdictions"]==[]
