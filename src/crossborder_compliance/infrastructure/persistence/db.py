from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def build_engine(database_url: str):
    kwargs = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, **kwargs)

def build_session_factory(database_url: str):
    engine = build_engine(database_url)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
