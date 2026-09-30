from __future__ import annotations
import importlib.util
from fastapi import APIRouter
from crossborder_compliance.config import get_settings
router=APIRouter(tags=["health"])
@router.get("/health/live")
def live(): return {"status":"ok"}
@router.get("/health/ready")
def ready():
    s=get_settings(); return {"status":"ok","app_env":s.app_env}
@router.get("/health/dependencies")
def dependencies():
    return {"status":"degraded" if importlib.util.find_spec("langgraph") is None else "ok",
            "langgraph": importlib.util.find_spec("langgraph") is not None,
            "psycopg": importlib.util.find_spec("psycopg") is not None,
            "redis": importlib.util.find_spec("redis") is not None}
