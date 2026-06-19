import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

SQLITE_FALLBACK_URL = "sqlite:///./workflow.db"


def _build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pg_user = os.getenv("POSTGRES_USER", "workflow")
    pg_password = os.getenv("POSTGRES_PASSWORD", "workflow")
    pg_db = os.getenv("POSTGRES_DB", "workflow")
    DATABASE_URL = f"postgresql+psycopg2://{pg_user}:{pg_password}@db:5432/{pg_db}"
engine = _build_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def init_database() -> None:
    from app.models import Execution, NodeRun, Workflow  # noqa: F401

    global engine, SessionLocal
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        if DATABASE_URL.startswith("postgres"):
            engine = _build_engine(SQLITE_FALLBACK_URL)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
            Base.metadata.create_all(bind=engine)
        else:
            raise


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
