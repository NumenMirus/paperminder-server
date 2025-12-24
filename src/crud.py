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
    FirmwareVersion,
    UpdateRollout,
    UpdateHistory,
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


def get_and_increment_daily_message_number(printer_uuid: str) -> int:
    """Get the next daily message number for a printer, resetting if necessary.

    Checks if the printer's last reset date is before today (in UTC).
    If so, resets the counter to 1 and updates the reset date.
    Otherwise, increments the counter and returns the new value.

    Args:
        printer_uuid: The UUID of the printer

    Returns:
        The next daily message number for the printer

    Raises:
        RecipientNotFoundError: If the printer with the given UUID does not exist
    """
    from datetime import date, timedelta
    from src.exceptions import RecipientNotFoundError

    with session_scope() as session:
        printer = session.query(Printer).filter_by(uuid=printer_uuid).first()
        if not printer:
            raise RecipientNotFoundError(f"Printer with UUID {printer_uuid} not found")

        today = _utcnow().date()
        last_reset = printer.last_message_number_reset_date.date() if printer.last_message_number_reset_date else None

        # Reset counter if last reset was on a different day
        if last_reset != today:
            printer.daily_message_number = 1
            printer.last_message_number_reset_date = _utcnow()
        else:
            # Increment counter for the same day
            printer.daily_message_number += 1

        session.flush()
        current_number = printer.daily_message_number
        return current_number


# ============================================================================
# PRINTER FIRMWARE TRACKING CRUD OPERATIONS
# ============================================================================


def update_printer_firmware_info(
    uuid: str,
    firmware_version: str | None = None,
    auto_update: bool | None = None,
    update_channel: str | None = None,
) -> bool:
    """Update printer firmware information.

    Args:
        uuid: The UUID of the printer
        firmware_version: Optional new firmware version
        auto_update: Optional new auto_update setting
        update_channel: Optional new update channel

    Returns:
        True if the printer was updated, False if not found
    """
    with session_scope() as session:
        printer = session.query(Printer).filter_by(uuid=uuid).first()
        if printer is None:
            return False
        if firmware_version is not None:
            printer.firmware_version = firmware_version
        if auto_update is not None:
            printer.auto_update = auto_update
        if update_channel is not None:
            printer.update_channel = update_channel
        return True


def update_printer_connection_status(
    uuid: str,
    online: bool,
    last_connected: datetime | None = None,
    last_ip: str | None = None,
) -> bool:
    """Update printer connection status.

    Args:
        uuid: The UUID of the printer
        online: Whether the printer is currently online
        last_connected: Optional last connection timestamp
        last_ip: Optional last IP address

    Returns:
        True if the printer was updated, False if not found
    """
    with datetime_import():
        with session_scope() as session:
            printer = session.query(Printer).filter_by(uuid=uuid).first()
            if printer is None:
                return False
            printer.online = online
            if last_connected is not None:
                printer.last_connected = last_connected
            elif online:
                printer.last_connected = _utcnow()
            if last_ip is not None:
                printer.last_ip = last_ip
            return True


def get_printers_by_filters(
    user_uuid: str | None = None,
    online: bool | None = None,
    firmware_version: str | None = None,
    channel: str | None = None,
) -> list[Printer]:
    """Retrieve printers matching the specified filters.

    Args:
        user_uuid: Optional user UUID to filter by
        online: Optional online status to filter by
        firmware_version: Optional firmware version to filter by
        channel: Optional update channel to filter by

    Returns:
        List of Printer objects matching the filters
    """
    with session_scope() as session:
        query = session.query(Printer)

        if user_uuid is not None:
            query = query.filter_by(user_uuid=user_uuid)
        if online is not None:
            query = query.filter_by(online=online)
        if firmware_version is not None:
            query = query.filter_by(firmware_version=firmware_version)
        if channel is not None:
            query = query.filter_by(update_channel=channel)

        return query.all()


def get_online_printers() -> list[Printer]:
    """Retrieve all currently online printers.

    Returns:
        List of Printer objects with online=True
    """
    with session_scope() as session:
        printers = session.query(Printer).filter_by(online=True).all()
        return printers


# ============================================================================
# FIRMWARE VERSION CRUD OPERATIONS
# ============================================================================


def create_firmware_version(
    version: str,
    channel: str,
    file_data: bytes,
    file_size: int,
    md5_checksum: str,
    sha256_checksum: str | None = None,
    release_notes: str | None = None,
    changelog: str | None = None,
    mandatory: bool = False,
    min_upgrade_version: str | None = None,
) -> FirmwareVersion:
    """Create a new firmware version.

    Args:
        version: Semantic version string
        channel: Update channel (stable, beta, canary)
        file_data: Firmware binary data
        file_size: Size of the firmware file
        md5_checksum: MD5 checksum of the firmware
        sha256_checksum: Optional SHA256 checksum
        release_notes: Optional release notes
        changelog: Optional detailed changelog
        mandatory: Whether this is a mandatory update
        min_upgrade_version: Minimum version that can upgrade

    Returns:
        The created FirmwareVersion object
    """
    with session_scope() as session:
        firmware = FirmwareVersion(
            version=version,
            channel=channel,
            file_data=file_data,
            file_size=file_size,
            md5_checksum=md5_checksum,
            sha256_checksum=sha256_checksum,
            release_notes=release_notes,
            changelog=changelog,
            mandatory=mandatory,
            min_upgrade_version=min_upgrade_version,
        )
        session.add(firmware)
        session.flush()
        session.refresh(firmware)
        return firmware


def get_firmware_version(version: str) -> FirmwareVersion | None:
    """Retrieve a firmware version by version string.

    Args:
        version: The version string

    Returns:
        The FirmwareVersion object or None if not found
    """
    with session_scope() as session:
        firmware = session.query(FirmwareVersion).filter_by(version=version).first()
        return firmware


def get_firmware_version_by_id(firmware_id: int) -> FirmwareVersion | None:
    """Retrieve a firmware version by database ID.

    Args:
        firmware_id: The database ID

    Returns:
        The FirmwareVersion object or None if not found
    """
    with session_scope() as session:
        firmware = session.query(FirmwareVersion).filter_by(id=firmware_id).first()
        return firmware


def get_latest_firmware(channel: str = "stable") -> FirmwareVersion | None:
    """Retrieve the latest firmware version for a channel.

    Args:
        channel: The update channel (default: stable)

    Returns:
        The latest FirmwareVersion object or None if not found
    """
    with session_scope() as session:
        firmware = (
            session.query(FirmwareVersion)
            .filter_by(channel=channel)
            .filter(FirmwareVersion.deprecated_at.is_(None))
            .order_by(FirmwareVersion.released_at.desc())
            .first()
        )
        return firmware


def get_all_firmware_versions(channel: str | None = None) -> list[FirmwareVersion]:
    """Retrieve all firmware versions, optionally filtered by channel.

    Args:
        channel: Optional channel to filter by

    Returns:
        List of FirmwareVersion objects
    """
    with session_scope() as session:
        query = session.query(FirmwareVersion)
        if channel is not None:
            query = query.filter_by(channel=channel)
        firmware = query.order_by(FirmwareVersion.released_at.desc()).all()
        return firmware


def update_firmware_statistics(
    firmware_id: int,
    download_increment: bool = False,
    success_increment: bool = False,
    failure_increment: bool = False,
) -> bool:
    """Update firmware download/success/failure statistics.

    Args:
        firmware_id: The firmware database ID
        download_increment: Increment download count
        success_increment: Increment success count
        failure_increment: Increment failure count

    Returns:
        True if updated, False if firmware not found
    """
    with session_scope() as session:
        firmware = session.query(FirmwareVersion).filter_by(id=firmware_id).first()
        if firmware is None:
            return False
        if download_increment:
            firmware.download_count += 1
        if success_increment:
            firmware.success_count += 1
        if failure_increment:
            firmware.failure_count += 1
        return True


def deprecate_firmware_version(version: str) -> bool:
    """Mark a firmware version as deprecated.

    Args:
        version: The version string to deprecate

    Returns:
        True if deprecated, False if not found
    """
    with session_scope() as session:
        firmware = session.query(FirmwareVersion).filter_by(version=version).first()
        if firmware is None:
            return False
        firmware.deprecated_at = _utcnow()
        return True


# ============================================================================
# UPDATE ROLLOUT CRUD OPERATIONS
# ============================================================================


def create_rollout(
    firmware_version_id: int,
    target_all: bool = False,
    target_user_ids: list[str] | None = None,
    target_printer_ids: list[str] | None = None,
    target_channels: list[str] | None = None,
    min_version: str | None = None,
    max_version: str | None = None,
    rollout_type: str = "immediate",
    rollout_percentage: int = 100,
    scheduled_for: datetime | None = None,
) -> UpdateRollout:
    """Create a new update rollout.

    Args:
        firmware_version_id: The firmware version database ID
        target_all: Whether to target all printers
        target_user_ids: Optional list of user IDs to target
        target_printer_ids: Optional list of printer IDs to target
        target_channels: Optional list of channels to target
        min_version: Optional minimum firmware version to target
        max_version: Optional maximum firmware version to target
        rollout_type: Type of rollout (immediate, gradual, scheduled)
        rollout_percentage: Percentage for gradual rollout (0-100)
        scheduled_for: Optional scheduled start time

    Returns:
        The created UpdateRollout object
    """
    import json
    with datetime_import():
        with session_scope() as session:
            rollout = UpdateRollout(
                firmware_version_id=firmware_version_id,
                target_all=target_all,
                target_user_ids=json.dumps(target_user_ids) if target_user_ids else None,
                target_printer_ids=json.dumps(target_printer_ids) if target_printer_ids else None,
                target_channels=json.dumps(target_channels) if target_channels else None,
                min_version=min_version,
                max_version=max_version,
                rollout_type=rollout_type,
                rollout_percentage=rollout_percentage,
                scheduled_for=scheduled_for,
                status="pending",
            )
            session.add(rollout)
            session.flush()
            session.refresh(rollout)
            return rollout


def get_rollout(rollout_id: int) -> UpdateRollout | None:
    """Retrieve a rollout by database ID.

    Args:
        rollout_id: The rollout database ID

    Returns:
        The UpdateRollout object or None if not found
    """
    with session_scope() as session:
        rollout = session.query(UpdateRollout).filter_by(id=rollout_id).first()
        return rollout


def get_rollouts_by_status(status: str) -> list[UpdateRollout]:
    """Retrieve rollouts by status.

    Args:
        status: The status to filter by

    Returns:
        List of UpdateRollout objects
    """
    with session_scope() as session:
        rollouts = (
            session.query(UpdateRollout)
            .filter_by(status=status)
            .order_by(UpdateRollout.created_at.desc())
            .all()
        )
        return rollouts


def get_all_rollouts() -> list[UpdateRollout]:
    """Retrieve all rollouts.

    Returns:
        List of all UpdateRollout objects
    """
    with session_scope() as session:
        rollouts = (
            session.query(UpdateRollout)
            .order_by(UpdateRollout.created_at.desc())
            .all()
        )
        return rollouts


def update_rollout_status(
    rollout_id: int,
    status: str,
) -> bool:
    """Update rollout status.

    Args:
        rollout_id: The rollout database ID
        status: New status (pending, active, paused, completed, cancelled)

    Returns:
        True if updated, False if not found
    """
    with session_scope() as session:
        rollout = session.query(UpdateRollout).filter_by(id=rollout_id).first()
        if rollout is None:
            return False
        rollout.status = status
        return True


def update_rollout_percentage(
    rollout_id: int,
    rollout_percentage: int,
) -> bool:
    """Update rollout percentage for gradual rollouts.

    Args:
        rollout_id: The rollout database ID
        rollout_percentage: New percentage (0-100)

    Returns:
        True if updated, False if not found
    """
    with session_scope() as session:
        rollout = session.query(UpdateRollout).filter_by(id=rollout_id).first()
        if rollout is None:
            return False
        rollout.rollout_percentage = rollout_percentage
        return True


def update_rollout_progress(
    rollout_id: int,
    total_increment: int = 0,
    completed_increment: int = 0,
    failed_increment: int = 0,
    declined_increment: int = 0,
    pending_decrement: int = 0,
) -> bool:
    """Update rollout progress counters.

    Args:
        rollout_id: The rollout database ID
        total_increment: Increment total targets by this amount
        completed_increment: Increment completed count
        failed_increment: Increment failed count
        declined_increment: Increment declined count
        pending_decrement: Decrement pending count

    Returns:
        True if updated, False if not found
    """
    with session_scope() as session:
        rollout = session.query(UpdateRollout).filter_by(id=rollout_id).first()
        if rollout is None:
            return False
        rollout.total_targets += total_increment
        rollout.completed_count += completed_increment
        rollout.failed_count += failed_increment
        rollout.declined_count += declined_increment
        rollout.pending_count = max(0, rollout.pending_count - pending_decrement)
        return True


def get_active_rollout_for_printer(
    printer_uuid: str,
    firmware_version: str,
) -> UpdateRollout | None:
    """Retrieve an active rollout for a specific printer and firmware version.

    Args:
        printer_uuid: The printer UUID
        firmware_version: The target firmware version

    Returns:
        The UpdateRollout object or None if not found
    """
    import json
    with datetime_import():
        with session_scope() as session:
            printer = session.query(Printer).filter_by(uuid=printer_uuid).first()
            if not printer:
                return None

            firmware = session.query(FirmwareVersion).filter_by(version=firmware_version).first()
            if not firmware:
                return None

            # Find active rollout for this firmware version
            rollout = (
                session.query(UpdateRollout)
                .filter_by(firmware_version_id=firmware.id, status="active")
                .first()
            )

            if not rollout:
                return None

            # Parse JSON fields
            target_user_ids = json.loads(rollout.target_user_ids) if rollout.target_user_ids else None
            target_printer_ids = json.loads(rollout.target_printer_ids) if rollout.target_printer_ids else None
            target_channels = json.loads(rollout.target_channels) if rollout.target_channels else None

            # Check if printer matches rollout criteria
            if rollout.target_all:
                return rollout

            if target_user_ids and printer.user_uuid in target_user_ids:
                return rollout

            if target_printer_ids and printer_uuid in target_printer_ids:
                return rollout

            if target_channels and printer.update_channel in target_channels:
                # Check version constraints
                if rollout.min_version and compare_versions(printer.firmware_version, rollout.min_version) < 0:
                    return None
                if rollout.max_version and compare_versions(printer.firmware_version, rollout.max_version) > 0:
                    return None
                return rollout

            return None


def delete_rollout(rollout_id: int) -> bool:
    """Delete a rollout.

    Args:
        rollout_id: The rollout database ID

    Returns:
        True if deleted, False if not found
    """
    with session_scope() as session:
        rollout = session.query(UpdateRollout).filter_by(id=rollout_id).first()
        if rollout is None:
            return False
        session.delete(rollout)
        return True


# ============================================================================
# UPDATE HISTORY CRUD OPERATIONS
# ============================================================================


def create_update_record(
    printer_id: str,
    firmware_version: str,
    rollout_id: int | None = None,
) -> UpdateHistory:
    """Create an update history record.

    Args:
        printer_id: The printer UUID
        firmware_version: The target firmware version
        rollout_id: Optional rollout database ID

    Returns:
        The created UpdateHistory object
    """
    with session_scope() as session:
        history = UpdateHistory(
            printer_id=printer_id,
            firmware_version=firmware_version,
            rollout_id=rollout_id,
            status="pending",
        )
        session.add(history)
        session.flush()
        session.refresh(history)
        return history


def update_update_progress(
    printer_id: str,
    percent: int,
    status_message: str,
) -> bool:
    """Update progress for an active update.

    Args:
        printer_id: The printer UUID
        percent: Progress percentage (0-100, or -1 for error)
        status_message: Human-readable status message

    Returns:
        True if updated, False if no active update found
    """
    with session_scope() as session:
        history = (
            session.query(UpdateHistory)
            .filter_by(printer_id=printer_id)
            .filter(UpdateHistory.status.in_(["pending", "downloading"]))
            .order_by(UpdateHistory.started_at.desc())
            .first()
        )
        if history is None:
            return False
        history.last_percent = percent
        history.last_status_message = status_message
        if percent > 0 and percent < 100:
            history.status = "downloading"
        return True


def mark_update_complete(
    printer_id: str,
    version: str,
) -> bool:
    """Mark an update as successfully completed.

    Args:
        printer_id: The printer UUID
        version: The firmware version that was installed

    Returns:
        True if updated, False if no active update found
    """
    with session_scope() as session:
        history = (
            session.query(UpdateHistory)
            .filter_by(printer_id=printer_id, firmware_version=version)
            .filter(UpdateHistory.status.in_(["pending", "downloading"]))
            .order_by(UpdateHistory.started_at.desc())
            .first()
        )
        if history is None:
            return False
        history.status = "completed"
        history.completed_at = _utcnow()
        history.last_percent = 100
        return True


def mark_update_failed(
    printer_id: str,
    error_message: str,
) -> bool:
    """Mark an update as failed.

    Args:
        printer_id: The printer UUID
        error_message: Error message describing the failure

    Returns:
        True if updated, False if no active update found
    """
    with session_scope() as session:
        history = (
            session.query(UpdateHistory)
            .filter_by(printer_id=printer_id)
            .filter(UpdateHistory.status.in_(["pending", "downloading"]))
            .order_by(UpdateHistory.started_at.desc())
            .first()
        )
        if history is None:
            return False
        history.status = "failed"
        history.completed_at = _utcnow()
        history.error_message = error_message
        return True


def mark_update_declined(
    printer_id: str,
    version: str,
) -> bool:
    """Mark an update as declined by printer.

    Args:
        printer_id: The printer UUID
        version: The firmware version that was declined

    Returns:
        True if updated, False if no active update found
    """
    with session_scope() as session:
        history = (
            session.query(UpdateHistory)
            .filter_by(printer_id=printer_id, firmware_version=version)
            .filter_by(status="pending")
            .order_by(UpdateHistory.started_at.desc())
            .first()
        )
        if history is None:
            # Create a new declined record
            history = UpdateHistory(
                printer_id=printer_id,
                firmware_version=version,
                status="declined",
            )
            session.add(history)
            session.flush()
            return True
        history.status = "declined"
        history.completed_at = _utcnow()
        return True


def get_printer_update_history(
    printer_id: str,
    limit: int = 100,
) -> list[UpdateHistory]:
    """Retrieve update history for a printer.

    Args:
        printer_id: The printer UUID
        limit: Maximum number of records to retrieve

    Returns:
        List of UpdateHistory objects ordered by start time (newest first)
    """
    with session_scope() as session:
        history = (
            session.query(UpdateHistory)
            .filter_by(printer_id=printer_id)
            .order_by(UpdateHistory.started_at.desc())
            .limit(limit)
            .all()
        )
        return history


def get_rollout_update_history(
    rollout_id: int,
) -> list[UpdateHistory]:
    """Retrieve update history for a rollout.

    Args:
        rollout_id: The rollout database ID

    Returns:
        List of UpdateHistory objects
    """
    with session_scope() as session:
        history = (
            session.query(UpdateHistory)
            .filter_by(rollout_id=rollout_id)
            .order_by(UpdateHistory.started_at.desc())
            .all()
        )
        return history


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def compare_versions(version1: str, version2: str) -> int:
    """Compare two semantic version strings.

    Args:
        version1: First version string
        version2: Second version string

    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2
    """
    v1_parts = [int(x) for x in version1.split(".")]
    v2_parts = [int(x) for x in version2.split(".")]

    # Pad with zeros if needed
    max_len = max(len(v1_parts), len(v2_parts))
    v1_parts.extend([0] * (max_len - len(v1_parts)))
    v2_parts.extend([0] * (max_len - len(v2_parts)))

    for v1, v2 in zip(v1_parts, v2_parts):
        if v1 < v2:
            return -1
        elif v1 > v2:
            return 1

    return 0


def datetime_import():
    """Lazy import datetime for use in CRUD functions."""
    from datetime import datetime
    return datetime

