from fastapi import APIRouter
router=APIRouter(prefix="/api/v1/metadata",tags=["metadata"])
@router.get("/bootstrap")
def bootstrap_metadata():
    return {"metadata_version":"phase1a-empty","jurisdictions":[],"scenarios":[],"product_domains":[],"products":[],"data_types":[],"data_flow_types":[]}
