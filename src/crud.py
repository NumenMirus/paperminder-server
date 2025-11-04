from __future__ import annotations

from sqlalchemy import or_

from src.database import (
    Base,
    User,
    Group,
    GroupMembership,
    MessageLog,
    Printer,
    PrinterGroup,
    MessageCache,
    session_scope,
    hash_password,
    verify_password,
    _utcnow,
)
from src.models.message import InboundMessage


# ============================================================================
# USER CRUD OPERATIONS
# ============================================================================


def create_user(
    username: str,
    email: str,
    password: str,
    full_name: str | None = None,
    phone: str | None = None,
    is_admin: bool = False,
) -> User:
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


def get_user_by_email(email: str) -> User | None:
    """Retrieve a user by email.

    Args:
        email: The email address of the user

    Returns:
        The User object or None if not found
    """
    with session_scope() as session:
        user = session.query(User).filter_by(email=email).first()
        return user


def get_all_users() -> list[User]:
    """Retrieve all users from the database.

    Returns:
        List of all User objects
    """
    with session_scope() as session:
        users = session.query(User).all()
        return users


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


def update_user_metadata(
    uuid: str,
    full_name: str | None = None,
    phone: str | None = None,
    is_active: bool | None = None,
) -> bool:
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


# ============================================================================
# GROUP CRUD OPERATIONS
# ============================================================================


def create_group(name: str, owner_uuid: str, colour: str | None = None) -> Group:
    """Create a new group in the database.

    Args:
        name: The name of the group
        owner_uuid: The UUID of the user who owns the group
        colour: Optional hex colour code (e.g. "#RRGGBB")

    Returns:
        The created Group object
    """
    with session_scope() as session:
        group = Group(
            name=name,
            owner_uuid=owner_uuid,
            colour=colour,
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


def update_group(uuid: str, name: str | None = None, colour: str | None = None) -> bool:
    """Update group properties.

    Args:
        uuid: The UUID of the group
        name: Optional new name for the group
        colour: Optional new colour for the group

    Returns:
        True if the group was updated, False if not found
    """
    with session_scope() as session:
        group = session.query(Group).filter_by(uuid=uuid).first()
        if group is None:
            return False
        if name is not None:
            group.name = name
        if colour is not None:
            group.colour = colour
        return True


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


# ============================================================================
# GROUP MEMBERSHIP CRUD OPERATIONS
# ============================================================================


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
            user_uuid=user_uuid, group_uuid=group_uuid
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
        groups = [
            session.query(Group).filter_by(uuid=m.group_uuid).first() for m in memberships
        ]
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
        users = [
            session.query(User).filter_by(uuid=m.user_uuid).first() for m in memberships
        ]
        return [u for u in users if u is not None]


def is_user_in_group(user_uuid: str, group_uuid: str) -> bool:
    """Check if a user is a member of a group.

    Args:
        user_uuid: The UUID of the user
        group_uuid: The UUID of the group

    Returns:
        True if the user is a member of the group, False otherwise
    """
    with session_scope() as session:
        membership = session.query(GroupMembership).filter_by(
            user_uuid=user_uuid, group_uuid=group_uuid
        ).first()
        return membership is not None


# ============================================================================
# MESSAGE LOG CRUD OPERATIONS
# ============================================================================


def persist_message_log(sender_uuid: str, message: InboundMessage) -> MessageLog:
    """Persist a delivered message to the backing store.

    Args:
        sender_uuid: The UUID of the sender (user)
        message: The InboundMessage object containing message details

    Returns:
        The created MessageLog object
    """
    with session_scope() as session:
        msg_log = MessageLog(
            sender_uuid=sender_uuid,
            recipient_uuid=str(message.recipient_id),
            message_body=message.message,
        )
        session.add(msg_log)
        session.flush()
        session.refresh(msg_log)
        return msg_log


def get_received_messages(
    recipient_uuid: str, limit: int = 100, offset: int = 0
) -> list[MessageLog]:
    """Retrieve messages received by a user.

    Args:
        recipient_uuid: The UUID of the recipient user
        limit: Maximum number of messages to retrieve (default: 100)
        offset: Number of messages to skip (for pagination, default: 0)

    Returns:
        List of MessageLog objects ordered by creation time (newest first)
    """
    with session_scope() as session:
        messages = (
            session.query(MessageLog)
            .filter_by(recipient_uuid=recipient_uuid)
            .order_by(MessageLog.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return messages


def get_sent_messages(sender_uuid: str, limit: int = 100, offset: int = 0) -> list[MessageLog]:
    """Retrieve messages sent by a user.

    Args:
        sender_uuid: The UUID of the sender user
        limit: Maximum number of messages to retrieve (default: 100)
        offset: Number of messages to skip (for pagination, default: 0)

    Returns:
        List of MessageLog objects ordered by creation time (newest first)
    """
    with session_scope() as session:
        messages = (
            session.query(MessageLog)
            .filter_by(sender_uuid=sender_uuid)
            .order_by(MessageLog.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return messages


def get_conversation(
    user1_uuid: str, user2_uuid: str, limit: int = 100, offset: int = 0
) -> list[MessageLog]:
    """Retrieve messages exchanged between two users (conversation history).

    Args:
        user1_uuid: The UUID of the first user
        user2_uuid: The UUID of the second user
        limit: Maximum number of messages to retrieve (default: 100)
        offset: Number of messages to skip (for pagination, default: 0)

    Returns:
        List of MessageLog objects ordered by creation time (oldest first)
    """
    with session_scope() as session:
        messages = (
            session.query(MessageLog)
            .filter(
                or_(
                    (MessageLog.sender_uuid == user1_uuid)
                    & (MessageLog.recipient_uuid == user2_uuid),
                    (MessageLog.sender_uuid == user2_uuid)
                    & (MessageLog.recipient_uuid == user1_uuid),
                )
            )
            .order_by(MessageLog.created_at.asc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return messages


def get_message_count_for_user(user_uuid: str, direction: str = "received") -> int:
    """Get the count of messages for a user.

    Args:
        user_uuid: The UUID of the user
        direction: Either "received" or "sent" (default: "received")

    Returns:
        The count of messages

    Raises:
        ValueError: If direction is not "received" or "sent"
    """
    with session_scope() as session:
        if direction == "received":
            count = session.query(MessageLog).filter_by(recipient_uuid=user_uuid).count()
        elif direction == "sent":
            count = session.query(MessageLog).filter_by(sender_uuid=user_uuid).count()
        else:
            raise ValueError("direction must be 'received' or 'sent'")
        return count


# ============================================================================
# PRINTER CRUD OPERATIONS
# ============================================================================


def register_printer(name: str, uuid: str, location: str, user_uuid: str) -> Printer:
    """Register a new printer in the database.

    Args:
        name: The name of the printer
        uuid: The UUID of the printer
        location: The location of the printer
        user_uuid: The UUID of the user who owns the printer

    Returns:
        The created Printer object
    """
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


def get_printer(uuid: str) -> Printer | None:
    """Retrieve a printer by UUID.

    Args:
        uuid: The UUID of the printer

    Returns:
        The Printer object or None if not found
    """
    with session_scope() as session:
        printer = session.query(Printer).filter_by(uuid=uuid).first()
        return printer


async def get_all_registered_printers() -> list[Printer]:
    """Retrieve all registered printers from the database.

    Returns:
        List of all Printer objects
    """
    with session_scope() as session:
        printers = session.query(Printer).all()
        return printers


def get_user_printers(user_uuid: str) -> list[Printer]:
    """Retrieve all printers owned by a user.

    Args:
        user_uuid: The UUID of the user

    Returns:
        List of Printer objects owned by the user
    """
    with session_scope() as session:
        printers = session.query(Printer).filter_by(user_uuid=user_uuid).all()
        return printers


def get_group_printers(group_uuid: str) -> list[Printer]:
    """Retrieve all printers in a group.

    Args:
        group_uuid: The UUID of the group

    Returns:
        List of Printer objects in the group
    """
    with session_scope() as session:
        printer_memberships = session.query(PrinterGroup).filter_by(group_uuid=group_uuid).all()
        printers = [
            session.query(Printer).filter_by(uuid=m.printer_uuid).first() for m in printer_memberships
        ]
        return [p for p in printers if p is not None]


def update_printer(
    uuid: str, name: str | None = None, location: str | None = None
) -> bool:
    """Update printer properties.

    Args:
        uuid: The UUID of the printer
        name: Optional new name
        location: Optional new location

    Returns:
        True if the printer was updated, False if not found
    """
    with session_scope() as session:
        printer = session.query(Printer).filter_by(uuid=uuid).first()
        if printer is None:
            return False
        if name is not None:
            printer.name = name
        if location is not None:
            printer.location = location
        return True


def delete_printer(uuid: str) -> bool:
    """Delete a printer from the database by UUID.

    Args:
        uuid: The UUID of the printer

    Returns:
        True if the printer was deleted, False if not found
    """
    with session_scope() as session:
        printer = session.query(Printer).filter_by(uuid=uuid).first()
        if printer is None:
            return False
        session.delete(printer)
        return True


# ============================================================================
# PRINTER GROUP ASSOCIATION CRUD OPERATIONS
# ============================================================================


def add_printer_to_group(printer_uuid: str, group_uuid: str) -> PrinterGroup:
    """Add a printer to a group.

    Args:
        printer_uuid: The UUID of the printer
        group_uuid: The UUID of the group

    Returns:
        The created PrinterGroup object
    """
    with session_scope() as session:
        membership = PrinterGroup(
            printer_uuid=printer_uuid,
            group_uuid=group_uuid,
        )
        session.add(membership)
        session.flush()
        session.refresh(membership)
        return membership


def remove_printer_from_group(printer_uuid: str, group_uuid: str) -> bool:
    """Remove a printer from a group.

    Args:
        printer_uuid: The UUID of the printer
        group_uuid: The UUID of the group

    Returns:
        True if the membership was deleted, False if not found
    """
    with session_scope() as session:
        membership = session.query(PrinterGroup).filter_by(
            printer_uuid=printer_uuid, group_uuid=group_uuid
        ).first()
        if membership is None:
            return False
        session.delete(membership)
        return True


def get_printer_groups(printer_uuid: str) -> list[Group]:
    """Retrieve all groups that a printer belongs to.

    Args:
        printer_uuid: The UUID of the printer

    Returns:
        List of Group objects that the printer belongs to
    """
    with session_scope() as session:
        memberships = session.query(PrinterGroup).filter_by(printer_uuid=printer_uuid).all()
        groups = [
            session.query(Group).filter_by(uuid=m.group_uuid).first() for m in memberships
        ]
        return [g for g in groups if g is not None]


def is_printer_in_group(printer_uuid: str, group_uuid: str) -> bool:
    """Check if a printer is a member of a group.

    Args:
        printer_uuid: The UUID of the printer
        group_uuid: The UUID of the group

    Returns:
        True if the printer is in the group, False otherwise
    """
    with session_scope() as session:
        membership = session.query(PrinterGroup).filter_by(
            printer_uuid=printer_uuid, group_uuid=group_uuid
        ).first()
        return membership is not None


def can_user_message_printer(user_uuid: str, printer_uuid: str) -> bool:
    """Check if a user can send messages to a printer.

    A user can send messages to a printer if:
    1. The user owns the printer, OR
    2. The user is in a group that the printer belongs to

    Args:
        user_uuid: The UUID of the user
        printer_uuid: The UUID of the printer

    Returns:
        True if the user can send messages to the printer, False otherwise
    """
    with session_scope() as session:
        # Check if user is the owner of the printer
        printer = session.query(Printer).filter_by(uuid=printer_uuid).first()
        if printer is None:
            return False

        if printer.user_uuid == user_uuid:
            return True

        # Check if user is in any of the groups that the printer belongs to
        printer_groups = session.query(PrinterGroup).filter_by(printer_uuid=printer_uuid).all()
        if not printer_groups:
            return False

        group_uuids = [pg.group_uuid for pg in printer_groups]

        for group_uuid in group_uuids:
            if is_user_in_group(user_uuid, group_uuid):
                return True

        return False


# ============================================================================
# MESSAGE CACHE CRUD OPERATIONS
# ============================================================================


def cache_message(recipient_id: str, sender_id: str, sender_name: str, message_body: str) -> MessageCache:
    """Store a message in the cache for a recipient who may be offline.

    Args:
        recipient_id: The ID of the recipient
        sender_id: The ID of the sender
        sender_name: The display name of the sender
        message_body: The message content

    Returns:
        The created MessageCache object
    """
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
    """Retrieve undelivered cached messages for a recipient.

    Args:
        recipient_id: The ID of the recipient

    Returns:
        List of undelivered MessageCache objects
    """
    with session_scope() as session:
        messages = (
            session.query(MessageCache)
            .filter_by(recipient_id=recipient_id, is_delivered=False)
            .order_by(MessageCache.created_at)
            .all()
        )
        return messages


def mark_cached_messages_as_delivered(recipient_id: str) -> int:
    """Mark all cached messages for a recipient as delivered.

    Args:
        recipient_id: The ID of the recipient

    Returns:
        The count of messages marked as delivered
    """
    with session_scope() as session:
        count = (
            session.query(MessageCache)
            .filter_by(recipient_id=recipient_id, is_delivered=False)
            .update({"is_delivered": True})
        )
        return count


def clear_old_cached_messages(days: int = 7) -> int:
    """Delete cached messages older than specified days.

    Args:
        days: Number of days to keep (default: 7)

    Returns:
        The count of messages deleted
    """
    from datetime import timedelta

    with session_scope() as session:
        cutoff_date = _utcnow() - timedelta(days=days)
        count = (
            session.query(MessageCache)
            .filter(MessageCache.created_at < cutoff_date, MessageCache.is_delivered)
            .delete()
        )
        return count
