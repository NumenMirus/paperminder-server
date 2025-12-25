# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PaperMinder Server is a FastAPI-based WebSocket messaging service that enables real-time communication between PaperMinder clients. The service provides user authentication, printer management, group-based messaging, and message caching for offline clients.

## Development Commands

### Environment Setup
```bash
# Install dependencies using uv
uv sync --extra dev

# Alternative: Install with pip
pip install -r requirements.txt
```

### Running the Application
```bash
# Development with auto-reload
uv run uvicorn src.main:app --reload

# Production mode
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000

# Using Docker
docker build -t paperminder-server .
docker run -p 8000:8000 paperminder-server
```

### Testing
```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov

# Run specific test file
uv run pytest test_specific_file.py

# Run tests in verbose mode
uv run pytest -v
```

### Database Operations
The application uses SQLAlchemy with SQLite by default. Database URL can be configured via `DATABASE_URL` environment variable.

```bash
# Reset database (for development/testing)
# This is handled automatically by the init_db() function in src/main.py
```

## Architecture Overview

### Core Components

**FastAPI Application (`src/main.py`)**
- Application factory pattern with `create_app()`
- CORS middleware configuration (via `CORS_ALLOWED_ORIGINS` env var)
- Router registration for all endpoints

**Database Layer (`src/database.py`)**
- SQLAlchemy ORM models: User, Group, Printer, MessageLog, MessageCache, FirmwareVersion, UpdateRollout, UpdateHistory
- Password hashing with Argon2 (primary) and bcrypt (fallback)
- Session management with context managers (`session_scope()`)
- Database initialization and utilities
- Thread-safe async patterns using `asyncio.to_thread()`

**WebSocket System (`src/views/ws.py`, `src/controllers/message_controller.py`)**
- Real-time messaging between clients
- Connection manager (singleton pattern) tracking active WebSocket connections
- Message caching for offline recipients
- Daily message number tracking for printers (resets daily)
- Printer subscription handling with firmware update integration

**Authentication & Authorization (`src/config.py`, `src/models/auth.py`, `src/views/auth.py`, `src/dependencies.py`)**
- JWT-based authentication using AuthX
- User registration and login endpoints
- Protected route dependencies: `CurrentUser` and `AdminUser`
- Admin-only endpoints for firmware and rollout management

**Message System**
- **Models (`src/models/message.py`)**: Pydantic schemas for inbound/outbound messages
- **Service (`src/services/message_service.py`)**: Business logic for message operations
- **Controller (`src/controllers/message_controller.py`)**: WebSocket connection management
- **CRUD (`src/crud.py`)**: Database operations for all entities

**Firmware Update System**
- **Models (`src/models/firmware.py`)**: Pydantic schemas for firmware metadata and update messages
- **Service (`src/services/firmware_service.py`)**: Firmware upload, version management, checksums
- **Rollout Service (`src/services/rollout_service.py`)**: Campaign-based firmware deployments with targeting (immediate, gradual, scheduled)
- **Update Service (`src/services/update_service.py`)**: Update progress tracking and history
- **Views (`src/views/firmware.py`)**: Admin-only HTTP endpoints for firmware/rollout CRUD

### Key Patterns

1. **Connection Manager**: Singleton pattern managing WebSocket connections with async locks
2. **Message Caching**: Messages for offline clients are cached in MessageCache and delivered on reconnect
3. **Daily Message Numbers**: Each printer receives sequentially numbered messages that reset daily (tracked in Printer model)
4. **Group-based Access**: Users can create groups and assign printers to enable group messaging
5. **Content Sanitization**: All message content is sanitized using `MessageSanitizer` (src/utils/sanitizer.py) before storage/delivery
6. **Async-to-Sync Bridge**: Database operations use `asyncio.to_thread()` for thread-safe execution from async contexts
7. **Admin Authorization**: Use `AdminUser` dependency for endpoints that require admin privileges
8. **Printer Subscription**: Printers subscribe via WebSocket with SubscriptionRequest (api_key=printer_uuid, firmware_version, auto_update, update_channel)
9. **Firmware Rollouts**: Support immediate, gradual (percentage-based with consistent hashing), and scheduled rollouts with rich targeting

### Database Schema

- **Users**: Authentication and user management with UUID-based identification, includes `is_admin` flag
- **Groups**: User-created groups for organizing printers (owner_uuid, name, colour)
- **Printers**: Registered devices with daily message tracking, firmware version, auto_update preference, update_channel, online status
- **MessageLog**: Historical record of delivered messages (sender_uuid, recipient_uuid, message_body)
- **MessageCache**: Temporary storage for messages to offline recipients (undelivered messages tracked via is_delivered flag)
- **FirmwareVersion**: Firmware binaries with metadata (version, channel, file_data BLOB, checksums, release notes, mandatory flag, statistics)
- **UpdateRollout**: Firmware update campaigns with targeting filters, rollout type (immediate/gradual/scheduled), and progress tracking
- **UpdateHistory**: Individual firmware update attempts with status (pending/downloading/completed/failed/declined)
- **GroupMemberships/PrinterGroups**: Many-to-many relationships

### WebSocket Message Types

- **InboundMessage**: User-to-user messages with recipient_id, sender_name, message body
- **OutboundMessage**: Delivered messages with daily_number and timestamp
- **StatusMessage**: System notifications (validation errors, connection status)
- **SubscriptionRequest**: Printer subscription with printer_name, api_key (printer_uuid), firmware_version, auto_update, update_channel
- **FirmwareUpdateMessage**: Pushed to printers with version, url, md5 checksum
- **FirmwareProgressMessage**: Printer reports download progress (percent, status)
- **FirmwareCompleteMessage**: Printer reports successful update (version)
- **FirmwareFailedMessage**: Printer reports update failure (error)
- **FirmwareDeclinedMessage**: Printer declines update (version, auto_update)

### Security Considerations

- Password hashing with Argon2 (primary) and bcrypt (fallback)
- JWT token-based authentication
- Input validation and sanitization for all user content
- CORS configuration for cross-origin requests

## Development Notes

- The application uses uv for dependency management (pyproject.toml)
- Tests use pytest with httpx for async HTTP testing
- WebSocket connections support multiple concurrent connections per user/printer
- Message sanitization prevents XSS and content injection attacks (removes non-ASCII, control chars except \n\r\t)
- Database operations use thread-safe async patterns with `asyncio.to_thread()` wrapping sync CRUD calls
- When adding new async endpoints that query the database, wrap CRUD calls with `asyncio.to_thread()`
- Admin-only endpoints must use the `AdminUser` dependency from `src.dependencies`
- Firmware files are stored as BLOBs in the database (max size configured via `max_firmware_size` in Settings)
- Gradual rollouts use consistent MD5 hashing of printer UUIDs to determine eligibility buckets

## Environment Variables

- `DATABASE_URL`: Database connection string (default: `sqlite:///./paperminder.db`)
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed origins (default: "*", set to specific origins in production)
- Settings are loaded from `.env` file if present (see `src/config.py`)
- JWT secret key is hardcoded in `src/config.py` (should be moved to environment in production)
- `base_url`: Base URL for firmware download links (default: `http://localhost:8000`)
- `max_firmware_size`: Maximum firmware file size in bytes (default: 5MB)

## Important Implementation Details

### Message Flow
1. Client sends `InboundMessage` via WebSocket to `/ws/{user_id}`
2. Message is sanitized using `MessageSanitizer`
3. Daily message number is incremented for recipient
4. If recipient is online: send immediately as `OutboundMessage`
5. If recipient is offline: cache in `MessageCache` table, deliver on reconnect
6. Message is logged to `MessageLog` for history

### Printer Subscription Flow
1. Printer connects via WebSocket and sends `SubscriptionRequest`
2. Connection manager updates printer's firmware_version, auto_update, update_channel, online status
3. If `auto_update=true`, server checks for available firmware updates
4. If update available, push `FirmwareUpdateMessage` with download URL
5. Printer reports progress via `FirmwareProgressMessage`, `FirmwareCompleteMessage`, or `FirmwareFailedMessage`

### Rollout Execution
- **Immediate**: All targeted printers with `auto_update=true` and currently connected receive update immediately
- **Gradual**: Printers assigned to buckets 0-99 via MD5(printer_uuid) % 100; only printers in buckets 0 to (rollout_percentage-1) are eligible
- **Scheduled**: Rollout begins when `scheduled_for` timestamp is reached
- Rollout progress is tracked in `UpdateRollout` table (total_targets, completed_count, failed_count, declined_count, pending_count)
- Individual attempts are recorded in `UpdateHistory` table

### Dependency Injection Patterns
```python
# For authenticated user endpoints
from src.dependencies import CurrentUser
async def my_endpoint(current_user: CurrentUser):
    user_uuid = current_user["uid"]

# For admin-only endpoints
from src.dependencies import AdminUser
async def admin_endpoint(admin_user: AdminUser):
    user_uuid = admin_user["uid"]
```

### Database Access from Async Context
```python
# Wrap sync CRUD calls with asyncio.to_thread()
from src.crud import get_user
user = await asyncio.to_thread(get_user, uuid=user_uuid)

# Use session_scope context manager for transactions
from src.database import session_scope
with session_scope() as session:
    session.add(model)
    session.flush()
```