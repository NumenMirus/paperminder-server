"""Initial schema with PostgreSQL optimizations

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-12-27

This migration creates the initial database schema with:
- PostgreSQL JSONB types for UpdateRollout targeting fields
- Server defaults for Boolean and Integer fields
- Composite indexes for query optimization
- Connection pooling support

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=256), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_uuid", "users", ["uuid"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_is_active", "users", ["is_active"])

    # Create groups table
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("owner_uuid", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("colour", sa.String(length=7), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_uuid"], ["users.uuid"]),
    )
    op.create_index("ix_groups_id", "groups", ["id"])
    op.create_index("ix_groups_uuid", "groups", ["uuid"], unique=True)
    op.create_index("ix_groups_owner_uuid", "groups", ["owner_uuid"])

    # Create group_memberships table
    op.create_table(
        "group_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_uuid", sa.String(length=36), nullable=False),
        sa.Column("group_uuid", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["group_uuid"], ["groups.uuid"]),
        sa.ForeignKeyConstraint(["user_uuid"], ["users.uuid"]),
    )
    op.create_index("ix_group_memberships_id", "group_memberships", ["id"])
    op.create_index("ix_group_memberships_user_uuid", "group_memberships", ["user_uuid"])
    op.create_index("ix_group_memberships_group_uuid", "group_memberships", ["group_uuid"])

    # Create printers table
    op.create_table(
        "printers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("location", sa.String(length=256), nullable=False),
        sa.Column("user_uuid", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("daily_message_number", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_message_number_reset_date", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_uuid"], ["users.uuid"]),
    )
    op.create_index("ix_printers_id", "printers", ["id"])
    op.create_index("ix_printers_uuid", "printers", ["uuid"], unique=True)
    op.create_index("ix_printers_user_uuid", "printers", ["user_uuid"])

    # Create printer_groups table
    op.create_table(
        "printer_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("printer_uuid", sa.String(length=36), nullable=False),
        sa.Column("group_uuid", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["group_uuid"], ["groups.uuid"]),
        sa.ForeignKeyConstraint(["printer_uuid"], ["printers.uuid"]),
    )
    op.create_index("ix_printer_groups_id", "printer_groups", ["id"])
    op.create_index("ix_printer_groups_printer_uuid", "printer_groups", ["printer_uuid"])
    op.create_index("ix_printer_groups_group_uuid", "printer_groups", ["group_uuid"])

    # Create message_logs table
    op.create_table(
        "message_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sender_uuid", sa.String(length=36), nullable=False),
        sa.Column("recipient_uuid", sa.String(length=36), nullable=False),
        sa.Column("message_body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["recipient_uuid"], ["users.uuid"]),
        sa.ForeignKeyConstraint(["sender_uuid"], ["users.uuid"]),
    )
    op.create_index("ix_message_logs_id", "message_logs", ["id"])
    op.create_index("ix_message_logs_sender_uuid", "message_logs", ["sender_uuid"])
    op.create_index("ix_message_logs_recipient_uuid", "message_logs", ["recipient_uuid"])

    # Create message_cache table
    op.create_table(
        "message_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recipient_id", sa.String(length=36), nullable=False),
        sa.Column("sender_id", sa.String(length=64), nullable=False),
        sa.Column("sender_name", sa.String(length=128), nullable=False),
        sa.Column("message_body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_delivered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_message_cache_id", "message_cache", ["id"])
    op.create_index("ix_message_cache_recipient_id", "message_cache", ["recipient_id"])
    op.create_index("ix_message_cache_is_delivered", "message_cache", ["is_delivered"])

    # Create firmware_versions table
    op.create_table(
        "firmware_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("file_data", sa.LargeBinary(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("md5_checksum", sa.String(length=32), nullable=False),
        sa.Column("sha256_checksum", sa.String(length=64), nullable=True),
        sa.Column("release_notes", sa.Text(), nullable=True),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("mandatory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("min_upgrade_version", sa.String(length=16), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("download_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", "platform", name="uix_version_platform"),
    )
    op.create_index("ix_firmware_versions_id", "firmware_versions", ["id"])
    op.create_index("ix_firmware_versions_version", "firmware_versions", ["version"])
    op.create_index("ix_firmware_versions_platform", "firmware_versions", ["platform"])
    op.create_index("ix_firmware_versions_channel", "firmware_versions", ["channel"])

    # Create update_rollouts table with JSONB columns
    op.create_table(
        "update_rollouts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("firmware_version", sa.String(length=16), nullable=False),
        sa.Column("target_all", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("target_user_ids", postgresql.JSONB(), nullable=True),
        sa.Column("target_printer_ids", postgresql.JSONB(), nullable=True),
        sa.Column("target_channels", postgresql.JSONB(), nullable=True),
        sa.Column("min_version", sa.String(length=16), nullable=True),
        sa.Column("max_version", sa.String(length=16), nullable=True),
        sa.Column("rollout_type", sa.String(length=32), nullable=False),
        sa.Column("rollout_percentage", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("total_targets", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("declined_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("pending_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_update_rollouts_id", "update_rollouts", ["id"])
    op.create_index("ix_update_rollouts_firmware_version", "update_rollouts", ["firmware_version"])
    op.create_index("ix_update_rollouts_status", "update_rollouts", ["status"])

    # Create update_history table with composite index
    op.create_table(
        "update_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rollout_id", sa.Integer(), nullable=True),
        sa.Column("printer_id", sa.String(length=36), nullable=False),
        sa.Column("firmware_version", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_percent", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_status_message", sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["rollout_id"], ["update_rollouts.id"]),
    )
    op.create_index("ix_update_history_id", "update_history", ["id"])
    op.create_index("ix_update_history_rollout_id", "update_history", ["rollout_id"])
    op.create_index("ix_update_history_printer_id", "update_history", ["printer_id"])
    op.create_index("ix_update_history_printer_status", "update_history", ["printer_id", "status"])


def downgrade() -> None:
    # Drop tables in reverse order due to foreign key constraints
    op.drop_index("ix_update_history_printer_status", "update_history")
    op.drop_index("ix_update_history_printer_id", "update_history")
    op.drop_index("ix_update_history_rollout_id", "update_history")
    op.drop_index("ix_update_history_id", "update_history")
    op.drop_table("update_history")

    op.drop_index("ix_update_rollouts_status", "update_rollouts")
    op.drop_index("ix_update_rollouts_firmware_version", "update_rollouts")
    op.drop_index("ix_update_rollouts_id", "update_rollouts")
    op.drop_table("update_rollouts")

    op.drop_index("ix_firmware_versions_channel", "firmware_versions")
    op.drop_index("ix_firmware_versions_platform", "firmware_versions")
    op.drop_index("ix_firmware_versions_version", "firmware_versions")
    op.drop_index("ix_firmware_versions_id", "firmware_versions")
    op.drop_table("firmware_versions")

    op.drop_index("ix_message_cache_is_delivered", "message_cache")
    op.drop_index("ix_message_cache_recipient_id", "message_cache")
    op.drop_index("ix_message_cache_id", "message_cache")
    op.drop_table("message_cache")

    op.drop_index("ix_message_logs_recipient_uuid", "message_logs")
    op.drop_index("ix_message_logs_sender_uuid", "message_logs")
    op.drop_index("ix_message_logs_id", "message_logs")
    op.drop_table("message_logs")

    op.drop_index("ix_printer_groups_group_uuid", "printer_groups")
    op.drop_index("ix_printer_groups_printer_uuid", "printer_groups")
    op.drop_index("ix_printer_groups_id", "printer_groups")
    op.drop_table("printer_groups")

    op.drop_index("ix_printers_user_uuid", "printers")
    op.drop_index("ix_printers_uuid", "printers")
    op.drop_index("ix_printers_id", "printers")
    op.drop_table("printers")

    op.drop_index("ix_group_memberships_group_uuid", "group_memberships")
    op.drop_index("ix_group_memberships_user_uuid", "group_memberships")
    op.drop_index("ix_group_memberships_id", "group_memberships")
    op.drop_table("group_memberships")

    op.drop_index("ix_groups_owner_uuid", "groups")
    op.drop_index("ix_groups_uuid", "groups")
    op.drop_index("ix_groups_id", "groups")
    op.drop_table("groups")

    op.drop_index("ix_users_is_active", "users")
    op.drop_index("ix_users_email", "users")
    op.drop_index("ix_users_username", "users")
    op.drop_index("ix_users_uuid", "users")
    op.drop_index("ix_users_id", "users")
    op.drop_table("users")
