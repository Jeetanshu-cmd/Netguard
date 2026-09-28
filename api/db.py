"""
NetGuard AI — Database persistence layer (api/db.py)
SQLAlchemy 2.0 models and session management for SQLite.
"""

import time
import uuid
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import JSON, Float, Integer, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from api.config import settings


def default_flow_id() -> str:
    return f"flow-{uuid.uuid4().hex[:12]}"


class Base(DeclarativeBase):
    pass


class Flow(Base):
    __tablename__ = "flows"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=default_flow_id, index=True)
    ts: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    src_ip: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    dst_ip: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    dst_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    label: Mapped[str] = mapped_column(String, index=True)
    confidence: Mapped[float] = mapped_column(Float)
    features: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    top_features: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    first_seen: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    last_seen: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    src_ip: Mapped[str] = mapped_column(String, index=True)
    label: Mapped[str] = mapped_column(String, index=True)
    max_confidence: Mapped[float] = mapped_column(Float)
    flow_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String, default="open", index=True)


def create_app_engine(database_url: str = settings.database_url):
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    eng = create_engine(database_url, connect_args=connect_args)

    if database_url.startswith("sqlite") and not database_url.endswith(":memory:"):
        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
            except Exception:
                pass
            finally:
                cursor.close()

    return eng


engine = create_app_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None) -> None:
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)
