"""Database configuration and persistence helpers for the PaperMinder service."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Generator

from sqlalchemy import DateTime, Integer, String, Text, Boolean, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from src.models.message import InboundMessage

_DEFAULT_DATABASE_URL = "sqlite:///./paperminder.db"
_DATABASE_URL_ENV = "DATABASE_URL"


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy models."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MessageLog(Base):
    """ORM model representing a delivered message."""

    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sender_name: Mapped[str] = mapped_column(String(128), nullable=False)
    recipient_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message_body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Printer(Base):
    """ORM model representing a registered printer."""

    __tablename__ = "printers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    location: Mapped[str] = mapped_column(String(256), nullable=False)
    user_uuid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class MessageCache(Base):
    """ORM model for caching messages sent to offline printers."""

    __tablename__ = "message_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sender_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sender_name: Mapped[str] = mapped_column(String(128), nullable=False)
    message_body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    is_delivered: Mapped[bool] = mapped_column(default=False, index=True)


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None
_configured_url: str | None = None


def _resolve_database_url(database_url: str | None = None) -> str:
    if database_url:
        return database_url
    return os.getenv(_DATABASE_URL_ENV, _DEFAULT_DATABASE_URL)


def configure_database(database_url: str | None = None) -> None:
    """Initialise the SQLAlchemy engine and session factory."""

    global _engine, _SessionLocal, _configured_url

    resolved_url = _resolve_database_url(database_url)
    if resolved_url == _configured_url and _engine is not None and _SessionLocal is not None:
        return

    if _engine is not None:
        _engine.dispose()

    connect_args = {"check_same_thread": False} if resolved_url.startswith("sqlite") else {}
    _engine = create_engine(resolved_url, connect_args=connect_args, future=True)
    _SessionLocal = sessionmaker(
        bind=_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )
    _configured_url = resolved_url


def get_engine() -> Engine:
    if _engine is None:
        configure_database()
    assert _engine is not None
    return _engine


def get_session() -> Session:
    if _SessionLocal is None:
        configure_database()
    assert _SessionLocal is not None  # for mypy
    return _SessionLocal()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover - defensive rollback
        session.rollback()
        raise
    finally:
        session.close()


def init_db(database_url: str | None = None) -> None:
    configure_database(database_url)
    Base.metadata.create_all(bind=get_engine())
    print("Database initialized.")


def persist_message_log(sender_id: str, message: InboundMessage) -> None:
    """Persist a delivered message to the backing store."""

    with session_scope() as session:
        session.add(
            MessageLog(
                sender_id=sender_id,
                sender_name=message.sender_name,
                recipient_id=str(message.recipient_id),
                message_body=message.message,
            )
        )


def register_printer(name: str, uuid: str, location: str, user_uuid: str) -> Printer:
    """Register a new printer in the database."""

    with session_scope() as session:
        printer = Printer(
            name=name,
            uuid=uuid,
            location=location,
            user_uuid=user_uuid,
        )
        session.add(printer)
        session.flush()
        session.refresh(printer)
        return printer
    

async def get_all_registered_printers() -> list[Printer]:
    """Retrieve all registered printers from the database."""
    with session_scope() as session:
        printers = session.query(Printer).all()
        return printers


def delete_printer(uuid: str) -> bool:
    """Delete a printer from the database by UUID.
    
    Returns True if the printer was deleted, False if not found.
    """
    with session_scope() as session:
        printer = session.query(Printer).filter_by(uuid=uuid).first()
        if printer is None:
            return False
        session.delete(printer)
        return True


def cache_message(recipient_id: str, sender_id: str, sender_name: str, message_body: str) -> MessageCache:
    """Store a message in the cache for a recipient who may be offline."""
    with session_scope() as session:
        cache_entry = MessageCache(
            recipient_id=recipient_id,
            sender_id=sender_id,
            sender_name=sender_name,
            message_body=message_body,
        )
        session.add(cache_entry)
        session.flush()
        session.refresh(cache_entry)
        return cache_entry


def get_cached_messages(recipient_id: str) -> list[MessageCache]:
    """Retrieve undelivered cached messages for a recipient."""
    with session_scope() as session:
        messages = session.query(MessageCache).filter_by(
            recipient_id=recipient_id,
            is_delivered=False
        ).order_by(MessageCache.created_at).all()
        return messages


def mark_cached_messages_as_delivered(recipient_id: str) -> int:
    """Mark all cached messages for a recipient as delivered.
    
    Returns the count of messages marked as delivered.
    """
    with session_scope() as session:
        count = session.query(MessageCache).filter_by(
            recipient_id=recipient_id,
            is_delivered=False
        ).update({"is_delivered": True})
        return count


def clear_old_cached_messages(days: int = 7) -> int:
    """Delete cached messages older than specified days.
    
    Returns the count of messages deleted.
    """
    from datetime import timedelta
    with session_scope() as session:
        cutoff_date = datetime.now(UTC) - timedelta(days=days)
        count = session.query(MessageCache).filter(
            MessageCache.created_at < cutoff_date,
            MessageCache.is_delivered == True
        ).delete()
        return count
    

def reset_database(database_url: str | None = None) -> None:
    """Drop and recreate the schema. Intended for tests."""

    configure_database(database_url)
    Base.metadata.drop_all(bind=get_engine())
    Base.metadata.create_all(bind=get_engine())
