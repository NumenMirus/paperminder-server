# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PaperMinder Server is a FastAPI-based WebSocket messaging service that enables real-time communication between PaperMinder clients (web UI, ESP printers, etc.). The service provides user authentication, printer management, group-based messaging, firmware update orchestration, and message caching for offline clients.

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
The application uses SQLAlchemy with PostgreSQL by default. Database URL must be provided via `DATABASE_URL` environment variable.

```bash
# Set database URL (required for PostgreSQL)
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"

# Initialize database with migrations (apply all migrations)
DATABASE_URL="..." uv run alembic upgrade head

# Reset database (for development/testing - DELETES ALL DATA)
DATABASE_URL="..." uv run python -c "from src.database import reset_database; reset_database()"
```

### Database Migrations
The project uses Alembic for database migrations. Use Alembic commands directly to manage schema changes.

**Important:** Always set `DATABASE_URL` before running migration commands.

```bash
# Apply pending migrations
DATABASE_URL="..." uv run alembic upgrade head

# Rollback one migration
DATABASE_URL="..." uv run alembic downgrade -1

# Rollback multiple migrations
DATABASE_URL="..." uv run alembic downgrade -2

# Create a new migration with auto-generated changes
DATABASE_URL="..." uv run alembic revision --autogenerate -m "add user avatar field"

# Create a new empty migration
DATABASE_URL="..." uv run alembic revision -m "fix index on users table"

# Show current migration version
DATABASE_URL="..." uv run alembic current

# Show migration history
DATABASE_URL="..." uv run alembic history

# View detailed migration info
DATABASE_URL="..." uv run alembic show <revision_id>
```

**Migration Workflow:**
1. Make model changes in `src/database.py`
2. Run `DATABASE_URL="..." uv run alembic revision --autogenerate -m "description"` to auto-generate migration
3. Review the generated migration file in `alembic/versions/`
4. Run `DATABASE_URL="..." uv run alembic upgrade head` to apply the migration
5. Test the changes

**Important Notes:**
- Always review auto-generated migrations before applying
- Use `op.batch_alter_table()` for table alterations (better for SQLite compatibility and reproducibility)
- PostgreSQL requires string defaults to be quoted in migrations: `server_default=sa.text("'value'")`
- For JSONB columns, use `postgresql.JSONB()` type
- Boolean defaults use lowercase text: `server_default=sa.text("true")` or `sa.text("false")`
- Integer defaults don't need quotes: `server_default=sa.text("0")`
- PostgreSQL is the only supported database engine


## Architecture Overview

### Directory Structure
```
src/
├── main.py              # FastAPI application factory
├── config.py            # Settings and AuthX configuration
├── database.py          # SQLAlchemy ORM models and DB utilities
├── dependencies.py      # FastAPI dependency injection (CurrentUser, AdminUser)
├── crud.py              # Database CRUD operations
├── models/              # Pydantic schemas (auth, message, firmware)
├── views/               # API route handlers (auth, firmware, ws)
├── services/            # Business logic (firmware, message, rollout, update)
├── controllers/         # WebSocket connection management
└── utils/               # Utilities (sanitization, etc.)
```

### Core Components

**FastAPI Application (`src/main.py`)**
- Simple app factory that registers all routers
- CORS middleware configured via `CORS_ALLOWED_ORIGINS` env var
- No application-level middleware (all in routers)

**Database Layer (`src/database.py`)**
- SQLAlchemy 2.0 with declarative base
- PostgreSQL-specific types: JSONB for complex fields, proper server defaults
- **All models use `server_default=text(...)` for defaults** (not just `default=...`)
- Password hashing with Argon2 (primary) and bcrypt (fallback) via passlib
- Connection pooling for PostgreSQL (pool_size=10, max_overflow=20)
- Thread-safe async patterns using `asyncio.to_thread()` for CRUD calls

**WebSocket System (`src/views/ws.py`, `src/controllers/message_controller.py`)**
- Single endpoint `/ws/{user_id}` handles all WebSocket connections
- Connection manager (singleton) tracks user and printer connections
- **Two types of clients connect:**
  - Web users (send/receive messages)
  - Printers (subscribe to firmware updates, receive print jobs)
- Message routing by recipient UUID
- Automatic delivery of cached messages on reconnect
- Printer subscription handshake on connection

**Authentication & Authorization**
- JWT-based using AuthX library
- Two dependency injection helpers in `src/dependencies.py`:
  - `CurrentUser`: Authenticated user (may not be admin)
  - `AdminUser`: Authenticated admin user only
- Admin endpoints require `AdminUser` dependency
- JWT secret is hardcoded in `src/config.py` (should be in env for production)

**Message System**
- **Models**: Pydantic schemas for InboundMessage, OutboundMessage, StatusMessage
- **Service** (`src/services/message_service.py`): Message validation, sanitization, routing
- **Controller** (`src/controllers/message_controller.py`): WebSocket message handling
- **CRUD** (`src/crud.py`): Database persistence

**Printer Management System**
- **Models**: Pydantic schemas for PrinterRegistrationRequest, PrinterResponse
- **Service** (`src/services/printer_service.py`): Printer registration, deletion, group membership
- **Views** (`src/views/printer.py`): HTTP endpoints for printer CRUD and group management
- **CRUD** (`src/crud.py`): Database persistence

**Bitmap Printing System**
- **Models** (`src/models/bitmap.py`): PrintBitmapMessage (server→printer), BitmapPrintingMessage (printer→server), BitmapErrorMessage (printer→server)
- **Service** (`src/services/bitmap_service.py`): QR code generation, image processing (resizing, Floyd-Steinberg dithering), conversion to 1-bit packed bitmap format
- **Utilities** (`src/utils/bitmap.py`): Validation functions, printer specifications, size limits
- **Views** (`src/views/message.py`): HTTP endpoints for QR codes, image upload, test patterns
- **Controller** (`src/controllers/message_controller.py`): `send_bitmap_to_printer()` method
- **WebSocket Handler** (`src/views/ws.py`): Handles bitmap printing responses from printers

**Firmware Update System**
This is a multi-tier orchestration system for ESP printer firmware updates:
- **Models**: Pydantic schemas for firmware metadata, rollout config, update messages
- **Service** (`src/services/firmware_service.py`): Firmware upload, storage, retrieval, MD5/SHA256 checksums
- **Rollout Service** (`src/services/rollout_service.py`): Campaign-based deployments with:
  - **Immediate rollout**: Push to all eligible connected printers immediately
  - **Gradual rollout**: MD5-hash-based bucket assignment (0-99), enable by percentage
  - **Scheduled rollout**: Begin at specific timestamp
  - Targeting: by user IDs, printer IDs, firmware channels, min/max versions
- **Update Service** (`src/services/update_service.py`): Track individual update attempts (progress, errors)
- **Views** (`src/views/firmware.py`): Admin-only HTTP CRUD for firmware and rollouts

### Critical Implementation Patterns

**1. Async Database Access from Async Context**
All database CRUD operations are synchronous (SQLAlchemy). When calling from async endpoints or WebSocket handlers:
```python
# Wrap sync CRUD calls with asyncio.to_thread()
from src.crud import get_user
user = await asyncio.to_thread(get_user, uuid=user_uuid)
```

**2. PostgreSQL JSONB Handling**
JSONB columns (like `UpdateRollout.target_user_ids`) store Python lists/dicts directly:
- **No manual serialization** - SQLAlchemy handles Python dict ↔ JSONB conversion
- When writing: pass Python list/dict directly (don't call `json.dumps()`)
- When reading: you get Python list/dict back (don't call `json.loads()`)
- Example: `target_user_ids: Mapped[list | None] = mapped_column(JSONB)`

**3. Printer Subscription Handshake**
Printers connect via WebSocket and immediately send a `SubscriptionRequest` message:
```json
{
  "kind": "subscription",
  "printer_name": "My Printer",
  "printer_id": "printer-uuid-here",
  "platform": "esp32-c3",
  "firmware_version": "1.2.0",
  "auto_update": true,
  "update_channel": "stable"
}
```
The server updates the printer's online status and firmware version, then checks for available firmware updates.

**Important notes:**
- `printer_id` is the printer's UUID (used to identify printer in database)
- `platform` field is REQUIRED for correct firmware updates (e.g., esp8266, esp32, esp32-c3, esp32-s3)
- Platform strings are normalized to dashed format (esp32-c3, esp32-s3) but accept variants (esp32c3, esp32_s3)
- Firmware is stored per-platform, so the same version number can have different binaries for different platforms

**4. Gradual Rollout Hashing**
Gradual rollouts use consistent MD5 hashing to assign printers to buckets 0-99:
```python
printer_hash = int(hashlib.md5(printer.uuid.encode()).hexdigest(), 16)
bucket = printer_hash % 100
if bucket < rollout_percentage:
    # Printer is eligible for update
```
This ensures the same printers are always in the same buckets.

**5. Daily Message Numbers**
Each printer tracks `daily_message_number` that resets daily. Messages include a sequential number that resets at midnight. This is used by printers to track if they missed messages.

**6. Bitmap Printing**
The server processes all images for thermal printing:
- **Image Processing Pipeline**: QR code generation → Resize (width multiple of 8) → Floyd-Steinberg dithering → 1-bit packed format → Base64 encoding
- **Bitmap Format**: 1-bit monochrome, MSB-first (bit 7 = leftmost pixel), row-major order, 1 = black (print), 0 = white (no print)
- **Size Limits**: Maximum 50KB bitmap data, width must be multiple of 8
- **WebSocket Messages**: Server sends `print_bitmap`, printer responds with `bitmap_printing` (success) or `bitmap_error` (failure)
- **HTTP API**: `/api/message/bitmap/qr` (QR codes), `/api/message/bitmap/image` (upload), `/api/message/bitmap/test` (debugging)

### Database Schema Highlights

**Important Tables:**
- **Users**: UUID-based identification, `is_admin` flag for authorization
- **Groups**: User-created groups for organizing printers (many-to-many with users and printers)
- **Printers**: Device registry with platform, firmware version, auto_update preference, update_channel, online status, daily_message_number
- **MessageLog**: Historical record of all delivered messages (recipient references printer UUID)
- **MessageCache**: Temporary storage for offline recipients (delivered on reconnect via `is_delivered` flag)
- **FirmwareVersion**: Firmware binaries stored as BLOB with MD5/SHA256 checksums, **platform-specific** (unique constraint on version + platform), mandatory flag
- **UpdateRollout**: Campaign configuration with JSONB targeting fields (target_user_ids, target_printer_ids, target_channels, channel) - platform-agnostic version strings only
- **UpdateHistory**: Individual update attempts with progress tracking (status: pending/downloading/completed/failed/declined)

**Key Relationships:**
- Users own Groups ( Groups.owner_uuid → Users.uuid)
- Users and Printers belong to Groups (many-to-many via GroupMemberships and PrinterGroups)
- Rollouts track individual UpdateHistory records

### WebSocket Message Flow

**All WebSocket communication goes through `/ws/{user_id}` endpoint.**

**Message Types (identified by "kind" field):**
- `subscription`: Printer handshake (api_key=printer_uuid, firmware_version, auto_update, update_channel)
- `message`: User-to-user messages (recipient_id, sender_name, message)
- `firmware_progress`: Printer reports download progress (percent, status)
- `firmware_complete`: Printer reports successful update (version)
- `firmware_failed`: Printer reports update failure (error)
- `firmware_declined`: Printer declines update (version, auto_update)
- `print_bitmap`: Server sends bitmap to printer (width, height, data, caption)
- `bitmap_printing`: Printer acknowledges bitmap print started (width, height)
- `bitmap_error`: Printer reports bitmap printing failure (error)

**Server → Client messages:**
- `OutboundMessage`: Delivered messages with daily_number and timestamp
- `StatusMessage`: System notifications (validation errors, connection status)
- `FirmwareUpdateMessage`: Pushed to printers (version, url, md5 checksum)
- `PrintBitmapMessage`: Pushed to printers (width, height, base64-encoded bitmap data)

### Message Delivery Flow
1. Client sends `InboundMessage` via WebSocket
2. Message is sanitized using `MessageSanitizer` (removes non-ASCII, control chars except \n\r\t)
3. Daily message number is incremented for recipient printer
4. If recipient is online: send immediately as `OutboundMessage`
5. If recipient is offline: cache in `MessageCache` table, deliver on reconnect
6. Message is logged to `MessageLog` for history

### Firmware Update Flow
1. Printer connects and sends `SubscriptionRequest` with platform and firmware version
2. Connection manager normalizes platform string, updates printer's firmware_version, auto_update, update_channel, online status
3. If `auto_update=true`, server checks for active rollouts targeting this printer
4. If rollout eligible, server finds firmware for printer's platform and pushes `FirmwareUpdateMessage` with download URL
5. Printer downloads and reports progress via `FirmwareProgressMessage`
6. On completion: `FirmwareCompleteMessage` or `FirmwareFailedMessage`
7. Server updates `UpdateHistory` and `UpdateRollout` counters

**Important:** Each printer receives firmware for its specific platform. A rollout for version "1.5.0" will deliver different firmware binaries to esp8266 vs esp32-c3 printers.

### Bitmap Printing Flow
1. HTTP API endpoint receives request (QR code URL, image upload, or test pattern)
2. Server validates printer exists and is connected
3. **Image Processing** (via `BitmapService`):
   - **QR Code**: Generate using `qrcode` library with error correction M
   - **Image Upload**: Load from bytes, convert to grayscale
   - **Resize**: Scale to target width (multiple of 8, default 384px for 58mm paper)
   - **Dither**: Apply Floyd-Steinberg dithering for quality
   - **Pack**: Convert to 1-bit packed bitmap format (MSB-first, row-major)
   - **Encode**: Base64-encode the bitmap data
4. Server sends `PrintBitmapMessage` via WebSocket to printer
5. Printer receives message and decodes base64 data
6. Printer prints bitmap and sends response:
   - `BitmapPrintingMessage`: Success (width, height)
   - `BitmapErrorMessage`: Failure (error description)
7. Server logs the response

**Important**: All image processing happens server-side. Printers only receive the final 1-bit packed bitmap format.

### Dependency Injection for Authorization
```python
# For authenticated user endpoints (any user)
from src.dependencies import CurrentUser

@router.post("/example")
async def my_endpoint(current_user: CurrentUser):
    user_uuid = current_user["uid"]
    # current_user is a dict with "uid", "email", etc.

# For admin-only endpoints
from src.dependencies import AdminUser

@router.post("/admin/example")
async def admin_endpoint(admin_user: AdminUser):
    user_uuid = admin_user["uid"]
    # Returns 403 if user is not admin
```

## Environment Variables

**Required:**
- `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:pass@host:5432/dbname`)

**Optional:**
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed origins (default: "*")
- `base_url`: Base URL for firmware download links (default: `http://localhost:8000`)
- `max_firmware_size`: Maximum firmware file size in bytes (default: 5MB)

**Important Notes:**
- Settings are loaded from `.env` file if present (via `src/config.py`)
- JWT secret key is hardcoded in `src/config.py` - should be moved to environment for production

## Common Gotchas

**1. Platform Normalization**
Platform strings must be normalized consistently when querying or storing:
```python
from src.utils.platform import normalize_platform, platform_variants

# Normalize input to canonical form
platform = normalize_platform("esp32c3")  # Returns "esp32-c3"

# Query firmware - check all variants
variants = platform_variants("esp32-c3")  # Returns ["esp32-c3", "esp32c3", "esp32_c3"]
firmware = session.query(FirmwareVersion).filter(
    FirmwareVersion.platform.in_(variants)
).first()
```
When uploading firmware, always normalize the platform field. When querying for firmware matching a printer's platform, use `platform_variants()` to handle legacy formats.

**2. Forgetting `server_default` in Models**
When adding new fields to models in `src/database.py`, always add `server_default=text(...)`, not just `default=...`:
```python
# WRONG
is_active: Mapped[bool] = mapped_column(Boolean, default=True)

# CORRECT
is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
```

**3. Manual JSON Serialization/Deserialization**
Don't manually call `json.dumps()` or `json.loads()` on JSONB columns. SQLAlchemy handles it:
```python
# WRONG
rollout.target_user_ids = json.dumps(["uuid1", "uuid2"])

# CORRECT
rollout.target_user_ids = ["uuid1", "uuid2"]
```

**4. Forgetting `asyncio.to_thread()` in Async Context**
All CRUD functions in `src/crud.py` are synchronous. When calling from async endpoints, wrap them:
```python
# WRONG
user = get_user(uuid=user_uuid)

# CORRECT
user = await asyncio.to_thread(get_user, uuid=user_uuid)
```

**5. Unquoted String Defaults in Migrations**
PostgreSQL string defaults must be quoted:
```python
# WRONG
server_default=sa.text("pending")

# CORRECT
server_default=sa.text("'pending'")
```

**6. Not Using AdminUser Dependency**
Admin endpoints must use `AdminUser`, not `CurrentUser`:
```python
# WRONG - lets any user access admin endpoint
@router.post("/firmware/upload")
async def upload_firmware(current_user: CurrentUser):
    ...

# CORRECT - only allows admins
@router.post("/firmware/upload")
async def upload_firmware(admin_user: AdminUser):
    ...
```

**7. Printer Identification in Subscription**
When printers send subscription messages, they must use `printer_id` (not `api_key`) for identification:
```json
{
  "kind": "subscription",
  "printer_name": "My Printer",
  "printer_id": "printer-uuid-here",  // Correct field name
  "platform": "esp32-c3"
}
```
The `api_key` field is deprecated and ignored. Always use `printer_id` with the printer's UUID.

**8. Custom Exceptions**
Use the custom exceptions from `src/exceptions.py` for specific error conditions:
```python
from src.exceptions import RecipientNotConnectedError, RecipientNotFoundError

# Raise when recipient has no active WebSocket connections
raise RecipientNotConnectedError(f"Recipient {recipient_id} is not connected")

# Raise when recipient UUID doesn't exist in database
raise RecipientNotFoundError(f"Recipient {recipient_id} does not exist")
```

**9. Bitmap Width Must Be Multiple of 8**
When working with bitmap images for thermal printers, width must always be a multiple of 8:
```python
from src.services.bitmap_service import BitmapService

# WRONG - width not multiple of 8
qr_img = BitmapService.generate_qr_code(url, size=100)  # Will raise ValueError

# CORRECT - width is multiple of 8
qr_img = BitmapService.generate_qr_code(url, size=128)  # OK
```
This is because bitmap data is packed into bytes (8 pixels per byte). The validation utilities in `src/utils/bitmap.py` will enforce this constraint.