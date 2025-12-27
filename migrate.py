#!/usr/bin/env python3
"""Database migration utility script for PaperMinder Server.

This script provides convenient commands for managing database migrations using Alembic.

Usage:
    python migrate.py [command] [options]

Commands:
    init              Initialize the database with the latest schema
    upgrade           Apply pending migrations
    downgrade [rev]   Revert to a previous migration (default: -1)
    current           Show current migration version
    history           Show migration history
    create <msg>      Create a new migration with auto-generated changes
    revision <msg>    Create a new empty migration file
    reset             Drop all tables and reinitialize (DEV ONLY!)

Examples:
    python migrate.py init                    # Initialize database
    python migrate.py upgrade                 # Apply all pending migrations
    python migrate.py downgrade               # Rollback one migration
    python migrate.py downgrade -2            # Rollback two migrations
    python migrate.py create "add user avatar"  # Auto-generate migration
    python migrate.py revision "fix index"    # Create empty migration
    python migrate.py current                 # Check current version
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path


def get_alembic_command(args: list[str]) -> list[str]:
    """Build alembic command with proper arguments."""
    # Ensure DATABASE_URL is set
    if not os.getenv("DATABASE_URL"):
        print("WARNING: DATABASE_URL environment variable not set")
        print("Using default: sqlite:///./paperminder.db")
        os.environ["DATABASE_URL"] = "sqlite:///./paperminder.db"

    return ["uv", "run", "alembic"] + args


def run_command(cmd: list[str]) -> int:
    """Run a command and return exit code."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


def cmd_init(_args: argparse.Namespace) -> int:
    """Initialize the database with the latest schema."""
    print("Initializing database...")
    return run_command(get_alembic_command(["upgrade", "head"]))


def cmd_upgrade(_args: argparse.Namespace) -> int:
    """Apply pending migrations."""
    print("Applying pending migrations...")
    return run_command(get_alembic_command(["upgrade", "head"]))


def cmd_downgrade(args: argparse.Namespace) -> int:
    """Revert to a previous migration."""
    revision = args.revision if args.revision else "-1"
    print(f"Downgrading to revision: {revision}")
    return run_command(get_alembic_command(["downgrade", str(revision)]))


def cmd_current(_args: argparse.Namespace) -> int:
    """Show current migration version."""
    print("Current migration version:")
    return run_command(get_alembic_command(["current"]))


def cmd_history(_args: argparse.Namespace) -> int:
    """Show migration history."""
    print("Migration history:")
    return run_command(get_alembic_command(["history"]))


def cmd_create(args: argparse.Namespace) -> int:
    """Create a new migration with auto-generated changes."""
    if not args.message:
        print("ERROR: Migration message is required")
        print("Usage: python migrate.py create \"your message here\"")
        return 1

    print(f"Creating migration: {args.message}")
    return run_command(get_alembic_command(["revision", "--autogenerate", "-m", args.message]))


def cmd_revision(args: argparse.Namespace) -> int:
    """Create a new empty migration file."""
    if not args.message:
        print("ERROR: Migration message is required")
        print("Usage: python migrate.py revision \"your message here\"")
        return 1

    print(f"Creating empty migration: {args.message}")
    return run_command(get_alembic_command(["revision", "-m", args.message]))


def cmd_reset(args: argparse.Namespace) -> int:
    """Drop all tables and reinitialize (DEV ONLY!)."""
    if not args.force:
        print("ERROR: This will DELETE ALL DATA in the database!")
        print("Use --force to confirm you want to proceed.")
        return 1

    print("WARNING: Resetting database...")
    confirm = input("Type 'yes' to confirm: ")
    if confirm.lower() != "yes":
        print("Aborted.")
        return 1

    # Import database module to use reset_database function
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from src.database import reset_database

        database_url = os.getenv("DATABASE_URL", "sqlite:///./paperminder.db")
        print(f"Resetting database: {database_url}")
        reset_database(database_url)
        print("Database reset complete.")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to reset database: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Database migration utility for PaperMinder Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Migration command")

    # Init command
    subparsers.add_parser("init", help="Initialize the database with the latest schema")

    # Upgrade command
    subparsers.add_parser("upgrade", help="Apply pending migrations")

    # Downgrade command
    downgrade_parser = subparsers.add_parser("downgrade", help="Revert to a previous migration")
    downgrade_parser.add_argument(
        "revision",
        nargs="?",
        help="Revision to downgrade to (default: -1 for one step back)",
    )

    # Current command
    subparsers.add_parser("current", help="Show current migration version")

    # History command
    subparsers.add_parser("history", help="Show migration history")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new migration with auto-generated changes")
    create_parser.add_argument("message", help="Migration message/description")

    # Revision command
    revision_parser = subparsers.add_parser("revision", help="Create a new empty migration file")
    revision_parser.add_argument("message", help="Migration message/description")

    # Reset command
    reset_parser = subparsers.add_parser("reset", help="Drop all tables and reinitialize (DEV ONLY)")
    reset_parser.add_argument("--force", action="store_true", help="Force reset without confirmation")

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if not args.command:
        parser.print_help()
        return 1

    command_map = {
        "init": cmd_init,
        "upgrade": cmd_upgrade,
        "downgrade": cmd_downgrade,
        "current": cmd_current,
        "history": cmd_history,
        "create": cmd_create,
        "revision": cmd_revision,
        "reset": cmd_reset,
    }

    command_func = command_map.get(args.command)
    if not command_func:
        print(f"ERROR: Unknown command: {args.command}")
        return 1

    return command_func(args)


if __name__ == "__main__":
    sys.exit(main())
