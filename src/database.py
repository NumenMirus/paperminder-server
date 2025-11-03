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
    user_uuid: Mapped[str] = mapped_column(String(36), nullable=False, index=True) ## owner of the printer
    group: Mapped[str] = mapped_column(String(36), nullable=False, index=True) ## group the printer belongs to
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


# User and Group management functions


def create_user(username: str, email: str, password: str, full_name: str | None = None, phone: str | None = None, is_admin: bool = False) -> User:
    """Create a new user in the database.
    
    Args:
        username: The username for the user
        email: The email address for the user
        password: The plaintext password (will be hashed)
        full_name: Optional full name of the user
        phone: Optional phone number
        is_admin: Whether the user is an admin (default: False)
        
    Returns:
        The created User object
    """
    with session_scope() as session:
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            phone=phone,
            is_admin=is_admin,
        )
        session.add(user)
        session.flush()
        session.refresh(user)
        return user


def get_user(uuid: str) -> User | None:
    """Retrieve a user by UUID.
    
    Args:
        uuid: The UUID of the user
        
    Returns:
        The User object or None if not found
    """
    with session_scope() as session:
        user = session.query(User).filter_by(uuid=uuid).first()
        return user


def get_user_by_username(username: str) -> User | None:
    """Retrieve a user by username.
    
    Args:
        username: The username of the user
        
    Returns:
        The User object or None if not found
    """
    with session_scope() as session:
        user = session.query(User).filter_by(username=username).first()
        return user


def verify_user_password(username: str, password: str) -> bool:
    """Verify a user's password.
    
    Args:
        username: The username of the user
        password: The plaintext password to verify
        
    Returns:
        True if the password is correct, False otherwise
    """
    user = get_user_by_username(username)
    if user is None:
        return False
    return verify_password(password, user.password_hash)


def update_user_password(uuid: str, new_password: str) -> bool:
    """Update a user's password.
    
    Args:
        uuid: The UUID of the user
        new_password: The new plaintext password
        
    Returns:
        True if the password was updated, False if user not found
    """
    with session_scope() as session:
        user = session.query(User).filter_by(uuid=uuid).first()
        if user is None:
            return False
        user.password_hash = hash_password(new_password)
        return True


def update_user_metadata(uuid: str, full_name: str | None = None, phone: str | None = None, is_active: bool | None = None) -> bool:
    """Update user metadata.
    
    Args:
        uuid: The UUID of the user
        full_name: Optional new full name
        phone: Optional new phone number
        is_active: Optional new active status
        
    Returns:
        True if the user was updated, False if user not found
    """
    with session_scope() as session:
        user = session.query(User).filter_by(uuid=uuid).first()
        if user is None:
            return False
        if full_name is not None:
            user.full_name = full_name
        if phone is not None:
            user.phone = phone
        if is_active is not None:
            user.is_active = is_active
        return True


def update_user_last_login(uuid: str) -> bool:
    """Update the last login timestamp for a user.
    
    Args:
        uuid: The UUID of the user
        
    Returns:
        True if the user was updated, False if user not found
    """
    with session_scope() as session:
        user = session.query(User).filter_by(uuid=uuid).first()
        if user is None:
            return False
        user.last_login_at = _utcnow()
        return True


def get_all_users() -> list[User]:
    """Retrieve all users from the database.
    
    Returns:
        List of all User objects
    """
    with session_scope() as session:
        users = session.query(User).all()
        return users


def delete_user(uuid: str) -> bool:
    """Delete a user from the database by UUID.
    
    Args:
        uuid: The UUID of the user to delete
        
    Returns:
        True if the user was deleted, False if not found
    """
    with session_scope() as session:
        user = session.query(User).filter_by(uuid=uuid).first()
        if user is None:
            return False
        session.delete(user)
        return True


def create_group(name: str, owner_uuid: str) -> Group:
    """Create a new group in the database.
    
    Args:
        name: The name of the group
        owner_uuid: The UUID of the user who owns the group
        
    Returns:
        The created Group object
    """
    with session_scope() as session:
        group = Group(
            name=name,
            owner_uuid=owner_uuid,
        )
        session.add(group)
        session.flush()
        session.refresh(group)
        return group


def get_group(uuid: str) -> Group | None:
    """Retrieve a group by UUID.
    
    Args:
        uuid: The UUID of the group
        
    Returns:
        The Group object or None if not found
    """
    with session_scope() as session:
        group = session.query(Group).filter_by(uuid=uuid).first()
        return group


def get_groups_by_owner(owner_uuid: str) -> list[Group]:
    """Retrieve all groups owned by a user.
    
    Args:
        owner_uuid: The UUID of the user who owns the groups
        
    Returns:
        List of Group objects owned by the user
    """
    with session_scope() as session:
        groups = session.query(Group).filter_by(owner_uuid=owner_uuid).all()
        return groups


def get_all_groups() -> list[Group]:
    """Retrieve all groups from the database.
    
    Returns:
        List of all Group objects
    """
    with session_scope() as session:
        groups = session.query(Group).all()
        return groups


def delete_group(uuid: str) -> bool:
    """Delete a group from the database by UUID.
    
    Args:
        uuid: The UUID of the group to delete
        
    Returns:
        True if the group was deleted, False if not found
    """
    with session_scope() as session:
        group = session.query(Group).filter_by(uuid=uuid).first()
        if group is None:
            return False
        session.delete(group)
        return True


def add_user_to_group(user_uuid: str, group_uuid: str) -> GroupMembership:
    """Add a user to a group.
    
    Args:
        user_uuid: The UUID of the user
        group_uuid: The UUID of the group
        
    Returns:
        The created GroupMembership object
    """
    with session_scope() as session:
        membership = GroupMembership(
            user_uuid=user_uuid,
            group_uuid=group_uuid,
        )
        session.add(membership)
        session.flush()
        session.refresh(membership)
        return membership


def remove_user_from_group(user_uuid: str, group_uuid: str) -> bool:
    """Remove a user from a group.
    
    Args:
        user_uuid: The UUID of the user
        group_uuid: The UUID of the group
        
    Returns:
        True if the membership was deleted, False if not found
    """
    with session_scope() as session:
        membership = session.query(GroupMembership).filter_by(
            user_uuid=user_uuid,
            group_uuid=group_uuid
        ).first()
        if membership is None:
            return False
        session.delete(membership)
        return True


def get_user_groups(user_uuid: str) -> list[Group]:
    """Retrieve all groups that a user is a member of.
    
    Args:
        user_uuid: The UUID of the user
        
    Returns:
        List of Group objects that the user is a member of
    """
    with session_scope() as session:
        memberships = session.query(GroupMembership).filter_by(user_uuid=user_uuid).all()
        groups = [session.query(Group).filter_by(uuid=m.group_uuid).first() for m in memberships]
        return [g for g in groups if g is not None]


def get_group_members(group_uuid: str) -> list[User]:
    """Retrieve all members of a group.
    
    Args:
        group_uuid: The UUID of the group
        
    Returns:
        List of User objects that are members of the group
    """
    with session_scope() as session:
        memberships = session.query(GroupMembership).filter_by(group_uuid=group_uuid).all()
        users = [session.query(User).filter_by(uuid=m.user_uuid).first() for m in memberships]
        return [u for u in users if u is not None]
    

def reset_database(database_url: str | None = None) -> None:
    """Drop and recreate the schema. Intended for tests."""

    configure_database(database_url)
    Base.metadata.drop_all(bind=get_engine())
    Base.metadata.create_all(bind=get_engine())
