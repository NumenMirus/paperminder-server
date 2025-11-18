"""Database configuration and persistence helpers for the PaperMinder service."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Generator
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, Boolean, create_engine, ForeignKey
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker, relationship
from passlib.context import CryptContext

from src.models.message import InboundMessage

# Password hashing context using argon2 and bcrypt as fallback
_password_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
)

_DEFAULT_DATABASE_URL = "sqlite:///./paperminder.db"
_DATABASE_URL_ENV = "DATABASE_URL"


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy models."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _generate_uuid() -> str:
    return str(uuid4())


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.
    
    Args:
        password: The plaintext password to hash
        
    Returns:
        The hashed password string
    """
    return _password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hashed password.
    
    Args:
        plain_password: The plaintext password to verify
        hashed_password: The hashed password to verify against
        
    Returns:
        True if the password matches, False otherwise
    """
    return _password_context.verify(plain_password, hashed_password)


class User(Base):
    """ORM model representing a user."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True, default=_generate_uuid)
    username: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # User metadata
    full_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    owned_groups: Mapped[list[Group]] = relationship("Group", back_populates="owner", foreign_keys="Group.owner_uuid")
    group_memberships: Mapped[list[GroupMembership]] = relationship("GroupMembership", back_populates="user")


class Group(Base):
    """ORM model representing a group."""

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True, default=_generate_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_uuid: Mapped[str] = mapped_column(String(36), ForeignKey("users.uuid"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    colour: Mapped[str | None] = mapped_column(String(7), nullable=True)  # e.g. "#RRGGBB"

    # Relationships
    owner: Mapped[User] = relationship("User", back_populates="owned_groups", foreign_keys=[owner_uuid])
    members: Mapped[list[GroupMembership]] = relationship("GroupMembership", back_populates="group")
    printer_memberships: Mapped[list[PrinterGroup]] = relationship("PrinterGroup", back_populates="group")


class GroupMembership(Base):
    """ORM model representing membership of a user in a group (many-to-many relationship)."""

    __tablename__ = "group_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_uuid: Mapped[str] = mapped_column(String(36), ForeignKey("users.uuid"), nullable=False, index=True)
    group_uuid: Mapped[str] = mapped_column(String(36), ForeignKey("groups.uuid"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="group_memberships")
    group: Mapped[Group] = relationship("Group", back_populates="members")


class PrinterGroup(Base):
    """ORM model representing assignment of a printer to a group (many-to-many relationship)."""

    __tablename__ = "printer_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    printer_uuid: Mapped[str] = mapped_column(String(36), ForeignKey("printers.uuid"), nullable=False, index=True)
    group_uuid: Mapped[str] = mapped_column(String(36), ForeignKey("groups.uuid"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    printer: Mapped[Printer] = relationship("Printer", back_populates="group_memberships")
    group: Mapped[Group] = relationship("Group", back_populates="printer_memberships")


class MessageLog(Base):
    """ORM model representing a delivered message."""

    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_uuid: Mapped[str] = mapped_column(String(36), ForeignKey("users.uuid"), nullable=False, index=True)
    recipient_uuid: Mapped[str] = mapped_column(String(36), ForeignKey("users.uuid"), nullable=False, index=True)
    message_body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    sender: Mapped[User] = relationship("User", foreign_keys=[sender_uuid], backref="sent_messages")
    recipient: Mapped[User] = relationship("User", foreign_keys=[recipient_uuid], backref="received_messages")


class Printer(Base):
    """ORM model representing a registered printer."""

    __tablename__ = "printers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    location: Mapped[str] = mapped_column(String(256), nullable=False)
    user_uuid: Mapped[str] = mapped_column(String(36), ForeignKey("users.uuid"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    
    # Daily message number tracking
    daily_message_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_message_number_reset_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    owner: Mapped[User] = relationship("User", foreign_keys=[user_uuid], backref="owned_printers")
    group_memberships: Mapped[list[PrinterGroup]] = relationship("PrinterGroup", back_populates="printer")


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


def persist_message_log(sender_uuid: str, message: InboundMessage) -> None:
    """Persist a delivered message to the backing store.
    
    Args:
        sender_uuid: The UUID of the sender (user)
        message: The InboundMessage object containing message details
    """

    with session_scope() as session:
        session.add(
            MessageLog(
                sender_uuid=sender_uuid,
                recipient_uuid=str(message.recipient_id),
                message_body=message.message,
            )
        )


def reset_database(database_url: str | None = None) -> None:
    """Drop and recreate the schema. Intended for tests."""

    configure_database(database_url)
    Base.metadata.drop_all(bind=get_engine())
    Base.metadata.create_all(bind=get_engine())
