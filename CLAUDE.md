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
- CORS middleware configuration
- Router registration for all endpoints

**Database Layer (`src/database.py`)**
- SQLAlchemy ORM models: User, Group, Printer, MessageLog, MessageCache
- Password hashing with Argon2/bcrypt
- Session management with context managers
- Database initialization and utilities

**WebSocket System (`src/views/ws.py`, `src/controllers/message_controller.py`)**
- Real-time messaging between clients
- Connection manager tracking active WebSocket connections
- Message caching for offline recipients
- Daily message number tracking for printers

**Authentication (`src/config.py`, `src/models/auth.py`, `src/views/auth.py`)**
- JWT-based authentication using AuthX
- User registration and login endpoints
- Protected route middleware

**Message System**
- **Models (`src/models/message.py`)**: Pydantic schemas for inbound/outbound messages
- **Service (`src/services/message_service.py`)**: Business logic for message operations
- **Controller (`src/controllers/message_controller.py`)**: WebSocket connection management
- **CRUD (`src/crud.py`)**: Database operations for all entities

### Key Patterns

1. **Connection Manager**: Singleton pattern managing WebSocket connections with async locks
2. **Message Caching**: Messages for offline clients are cached and delivered on reconnect
3. **Daily Message Numbers**: Each printer receives sequentially numbered messages that reset daily
4. **Group-based Access**: Users can create groups and assign printers to enable group messaging
5. **Content Sanitization**: All message content is sanitized using `MessageSanitizer` before storage/delivery

### Database Schema

- **Users**: Authentication and user management with UUID-based identification
- **Groups**: User-created groups for organizing printers
- **Printers**: Registered devices with daily message tracking
- **MessageLog**: Historical record of delivered messages
- **MessageCache**: Temporary storage for messages to offline recipients
- **GroupMemberships/PrinterGroups**: Many-to-many relationships

### WebSocket Message Types

- **InboundMessage**: User-to-user messages with recipient_id, sender_name, message body
- **OutboundMessage**: Delivered messages with daily_number and timestamp
- **StatusMessage**: System notifications (validation errors, connection status)
- **SubscriptionRequest**: Printer subscription with printer_name and api_key

### Security Considerations

- Password hashing with Argon2 (primary) and bcrypt (fallback)
- JWT token-based authentication
- Input validation and sanitization for all user content
- CORS configuration for cross-origin requests

## Development Notes

- The application uses uv for dependency management
- Tests use pytest with httpx for async HTTP testing
- WebSocket connections support multiple concurrent connections per user
- Message sanitization prevents XSS and content injection attacks
- Database operations use thread-safe async patterns with asyncio.to_thread()

## Environment Variables

- `DATABASE_URL`: Database connection string (default: SQLite)
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed origins (default: "*")
- JWT secret key is configured in `src/config.py` (should be moved to environment in production)