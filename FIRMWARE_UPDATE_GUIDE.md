# PaperMinder Firmware Update Guide

This guide explains how to push firmware updates to PaperMinder printers using the PaperMinder Server.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Firmware Management](#firmware-management)
5. [Creating Rollouts](#creating-rollouts)
6. [Monitoring Updates](#monitoring-updates)
7. [Rollout Strategies](#rollout-strategies)
8. [API Reference](#api-reference)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The PaperMinder firmware update system consists of three main components:

- **Firmware Upload**: Upload firmware binaries with version tracking
- **Rollout Management**: Create and manage update campaigns with flexible targeting
- **Printer Updates**: WebSocket-based push updates to connected printers

### Key Features

- ✅ Multiple update channels (stable, beta, canary)
- ✅ Flexible targeting (all users, specific users, specific printers, channels)
- ✅ Multiple rollout strategies (immediate, gradual, scheduled)
- ✅ Version constraints (min/max version targeting)
- ✅ Progress tracking and history
- ✅ Automatic update delivery to connected printers

---

## Prerequisites

### Server Requirements

- Python 3.12+
- FastAPI with uvicorn
- SQLAlchemy (SQLite by default)
- python-multipart dependency

### Printer Requirements

- WebSocket client support
- HTTP/HTTPS download capability
- MD5 checksum verification
- Storage space for firmware binary (max 5MB)

### Configuration

Environment variables (optional):

```bash
DATABASE_URL=sqlite:///./paperminder.db
CORS_ALLOWED_ORIGINS=*
base_url=http://localhost:8000
max_firmware_size=5242880  # 5MB in bytes
```

---

## Quick Start

### 1. Start the Server

```bash
cd /home/numen/Desktop/paperminder-server
uv run uvicorn src.main:app --reload
```

The API will be available at `http://localhost:8000`
Interactive docs: `http://localhost:8000/docs`

### 2. Upload Firmware

```bash
curl -X POST http://localhost:8000/api/firmware/upload \
  -F "file=@firmware.bin" \
  -F "version=1.5.0" \
  -F "channel=stable" \
  -F "release_notes=Bug fixes and performance improvements"
```

### 3. Create Rollout

```bash
curl -X POST http://localhost:8000/api/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "1.5.0",
    "target": {
      "channels": ["stable"]
    },
    "rollout_type": "immediate"
  }'
```

### 4. Printers Receive Update Automatically

When printers connect with `auto_update: true`, they will automatically receive and install the update.

---

## Firmware Management

### Uploading Firmware

**Endpoint:** `POST /api/firmware/upload`

**Method:** `multipart/form-data`

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | file | ✅ Yes | Firmware binary file (max 5MB) |
| `version` | string | ✅ Yes | Semantic version (e.g., "1.0.0", "2.3.15") |
| `channel` | string | ❌ No | Update channel: "stable", "beta", or "canary" (default: "stable") |
| `release_notes` | string | ❌ No | Brief release notes |
| `changelog` | string | ❌ No | Detailed changelog |
| `mandatory` | boolean | ❌ No | Whether this is a mandatory update (default: false) |
| `min_upgrade_version` | string | ❌ No | Minimum version that can upgrade to this version |

**Example with curl:**

```bash
curl -X POST http://localhost:8000/api/firmware/upload \
  -F "file=@/path/to/paperminder-1.5.0.bin" \
  -F "version=1.5.0" \
  -F "channel=stable" \
  -F "release_notes=Fixed critical security issues" \
  -F "changelog=- Fixed CVE-2024-1234\n- Improved battery life\n- Enhanced print quality" \
  -F "mandatory=false" \
  -F "min_upgrade_version=1.0.0"
```

**Example with Python requests:**

```python
import requests

url = "http://localhost:8000/api/firmware/upload"
files = {"file": open("paperminder-1.5.0.bin", "rb")}
data = {
    "version": "1.5.0",
    "channel": "stable",
    "release_notes": "Bug fixes and improvements",
    "mandatory": False
}

response = requests.post(url, files=files, data=data)
print(response.json())
```

**Response:**

```json
{
  "id": 42,
  "version": "1.5.0",
  "channel": "stable",
  "file_size": 1048576,
  "md5_checksum": "d41d8cd98f00b204e9800998ecf8427e",
  "sha256_checksum": "e3b0c44298fc1c149afbf4c8996fb924...",
  "release_notes": "Bug fixes and improvements",
  "changelog": null,
  "mandatory": false,
  "min_upgrade_version": "1.0.0",
  "released_at": "2025-01-15T10:30:00Z",
  "deprecated_at": null,
  "download_count": 0,
  "success_count": 0,
  "failure_count": 0
}
```

### Querying Firmware

#### Get Latest Firmware

```bash
# Get latest stable firmware
curl http://localhost:8000/api/firmware/latest?channel=stable

# Get latest beta firmware
curl http://localhost:8000/api/firmware/latest?channel=beta
```

#### Get Specific Version

```bash
curl http://localhost:8000/api/firmware/1.5.0
```

#### List All Firmware

```bash
# All firmware
curl http://localhost:8000/api/firmware

# Filter by channel
curl http://localhost:8000/api/firmware?channel=stable
```

#### Download Firmware Binary

```bash
curl -O http://localhost:8000/api/firmware/download/1.5.0
# Output: paperminder-1.5.0.bin
```

---

## Creating Rollouts

### Rollout Targeting Options

You can target printers in several ways (use one primary method):

#### 1. Target All Printers

Updates all printers in the system:

```json
{
  "firmware_version": "1.5.0",
  "target": {
    "all": true
  },
  "rollout_type": "immediate"
}
```

#### 2. Target Specific Users

Updates printers owned by specific users:

```json
{
  "firmware_version": "1.5.0",
  "target": {
    "user_ids": [
      "550e8400-e29b-41d4-a716-446655440000",
      "660e8400-e29b-41d4-a716-446655440001"
    ]
  },
  "rollout_type": "immediate"
}
```

#### 3. Target Specific Printers

Updates specific printer devices:

```json
{
  "firmware_version": "1.5.0",
  "target": {
    "printer_ids": [
      "770e8400-e29b-41d4-a716-446655440000",
      "880e8400-e29b-41d4-a716-446655440001"
    ]
  },
  "rollout_type": "immediate"
}
```

#### 4. Target by Channel

Updates printers subscribed to specific channels:

```json
{
  "firmware_version": "1.5.0",
  "target": {
    "channels": ["stable", "beta"]
  },
  "rollout_type": "immediate"
}
```

#### 5. Target by Channel with Version Constraints

Updates printers on specific channels running certain firmware versions:

```json
{
  "firmware_version": "1.5.0",
  "target": {
    "channels": ["stable"],
    "min_version": "1.0.0",
    "max_version": "1.4.0"
  },
  "rollout_type": "immediate"
}
```

**Use case:** Update all printers running version 1.0.0 to 1.4.0 to version 1.5.0, excluding printers already on 1.5.0 or higher.

### Rollout Types

#### Immediate Rollout

All targeted printers receive the update immediately upon connection:

```json
{
  "firmware_version": "1.5.0",
  "target": {
    "channels": ["stable"]
  },
  "rollout_type": "immediate"
}
```

#### Gradual Rollout

A percentage of targeted printers receive the update based on deterministic hashing:

```json
{
  "firmware_version": "1.5.0",
  "target": {
    "channels": ["stable"]
  },
  "rollout_type": "gradual",
  "rollout_percentage": 20
}
```

**How it works:**
- Printers are assigned to buckets 0-99 using MD5 hash of their UUID
- Printers with bucket < `rollout_percentage` receive the update
- Same printer always gets the same bucket (deterministic)
- Increase `rollout_percentage` over time to roll out to more printers

**Example gradual rollout schedule:**
1. Start with 10% - monitor for issues
2. Increase to 30% after 24 hours if no issues
3. Increase to 50% after another 24 hours
4. Increase to 100% after final verification

#### Scheduled Rollout

Updates begin at a specified future time:

```json
{
  "firmware_version": "1.5.0",
  "target": {
    "channels": ["stable"]
  },
  "rollout_type": "scheduled",
  "scheduled_for": "2025-01-20T02:00:00Z"
}
```

**Use case:** Schedule updates during off-peak hours (e.g., 2 AM) to minimize disruption.

### Creating a Rollout

**Endpoint:** `POST /api/rollouts`

**Request Body:**

```json
{
  "firmware_version": "string (required)",
  "target": {
    "all": "boolean (optional)",
    "user_ids": ["UUID"] (optional),
    "printer_ids": ["UUID"] (optional),
    "channels": ["string"] (optional),
    "min_version": "string (optional)",
    "max_version": "string (optional)"
  },
  "rollout_type": "immediate | gradual | scheduled (required)",
  "rollout_percentage": "integer 0-100 (required for gradual)",
  "scheduled_for": "ISO 8601 datetime (required for scheduled)"
}
```

**Examples:**

**Immediate rollout to all stable channel printers:**

```bash
curl -X POST http://localhost:8000/api/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "1.5.0",
    "target": {
      "channels": ["stable"]
    },
    "rollout_type": "immediate"
  }'
```

**Gradual rollout starting at 10%:**

```bash
curl -X POST http://localhost:8000/api/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "1.5.0",
    "target": {
      "channels": ["stable"],
      "min_version": "1.0.0"
    },
    "rollout_type": "gradual",
    "rollout_percentage": 10
  }'
```

**Scheduled rollout for 2 AM UTC:**

```bash
curl -X POST http://localhost:8000/api/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "1.5.0",
    "target": {
      "all": true
    },
    "rollout_type": "scheduled",
    "scheduled_for": "2025-01-20T02:00:00Z"
  }'
```

---

## Monitoring Updates

### List Rollouts

```bash
# All rollouts
curl http://localhost:8000/api/rollouts

# Filter by status
curl http://localhost:8000/api/rollouts?status=active
curl http://localhost:8000/api/rollouts?status=completed
curl http://localhost:8000/api/rollouts?status=paused
```

### Get Rollout Details

```bash
curl http://localhost:8000/api/rollouts/42
```

**Response:**

```json
{
  "id": 42,
  "firmware_version": "1.5.0",
  "firmware_version_id": 15,
  "target_all": false,
  "target_user_ids": null,
  "target_printer_ids": null,
  "target_channels": "[\"stable\"]",
  "min_version": "1.0.0",
  "max_version": null,
  "rollout_type": "gradual",
  "rollout_percentage": 20,
  "scheduled_for": null,
  "status": "active",
  "created_at": "2025-01-15T10:00:00Z",
  "total_targets": 150,
  "completed_count": 30,
  "failed_count": 2,
  "declined_count": 5,
  "pending_count": 113
}
```

### Update Rollout

Change rollout status or percentage:

```bash
# Pause rollout
curl -X PATCH http://localhost:8000/api/rollouts/42 \
  -H "Content-Type: application/json" \
  -d '{"status": "paused"}'

# Resume rollout
curl -X PATCH http://localhost:8000/api/rollouts/42 \
  -H "Content-Type: application/json" \
  -d '{"status": "active"}'

# Cancel rollout
curl -X PATCH http://localhost:8000/api/rollouts/42 \
  -H "Content-Type: application/json" \
  -d '{"status": "cancelled"}'

# Increase gradual rollout percentage
curl -X PATCH http://localhost:8000/api/rollouts/42 \
  -H "Content-Type: application/json" \
  -d '{"rollout_percentage": 50}'
```

### Delete Rollout

```bash
curl -X DELETE http://localhost:8000/api/rollouts/42
```

### List Printers

```bash
# All printers
curl http://localhost:8000/api/printers

# Filter by user
curl http://localhost:8000/api/printers?user_id=550e8400-e29b-41d4-a716-446655440000

# Filter by online status
curl http://localhost:8000/api/printers?online=true

# Filter by firmware version
curl http://localhost:8000/api/printers?firmware_version=1.4.0

# Filter by update channel
curl http://localhost:8000/api/printers?channel=stable
```

### Get Printer Update History

```bash
curl http://localhost:8000/api/printers/42/updates?limit=50
```

**Response:**

```json
{
  "updates": [
    {
      "id": 123,
      "rollout_id": 42,
      "printer_id": "770e8400-e29b-41d4-a716-446655440000",
      "firmware_version": "1.5.0",
      "status": "completed",
      "error_message": null,
      "started_at": "2025-01-15T10:05:00Z",
      "completed_at": "2025-01-15T10:07:30Z",
      "last_percent": 100,
      "last_status_message": "Update completed successfully"
    },
    {
      "id": 120,
      "rollout_id": 40,
      "printer_id": "770e8400-e29b-41d4-a716-446655440000",
      "firmware_version": "1.4.0",
      "status": "completed",
      "error_message": null,
      "started_at": "2025-01-10T14:00:00Z",
      "completed_at": "2025-01-10T14:02:15Z",
      "last_percent": 100,
      "last_status_message": "Update completed successfully"
    }
  ]
}

---

## Rollout Strategies

### Strategy 1: Canal Release (Recommended)

Release firmware gradually through channels:

```bash
# 1. Release to canary channel (1% of users)
curl -X POST http://localhost:8000/api/firmware/upload \
  -F "file=@firmware-1.5.0.bin" \
  -F "version=1.5.0" \
  -F "channel=canary"

curl -X POST http://localhost:8000/api/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "1.5.0",
    "target": {"channels": ["canary"]},
    "rollout_type": "gradual",
    "rollout_percentage": 100
  }'

# Monitor for 24-48 hours, then release to beta
curl -X POST http://localhost:8000/api/firmware/upload \
  -F "file=@firmware-1.5.0.bin" \
  -F "version=1.5.0" \
  -F "channel=beta"

curl -X POST http://localhost:8000/api/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "1.5.0",
    "target": {"channels": ["beta"]},
    "rollout_type": "gradual",
    "rollout_percentage": 20
  }'

# Gradually increase beta to 100%

# Finally release to stable
curl -X POST http://localhost:8000/api/firmware/upload \
  -F "file=@firmware-1.5.0.bin" \
  -F "version=1.5.0" \
  -F "channel=stable"

curl -X POST http://localhost:8000/api/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "1.5.0",
    "target": {"channels": ["stable"]},
    "rollout_type": "gradual",
    "rollout_percentage": 10
  }'
```

### Strategy 2: Phased Gradual Rollout

Release to all stable users in phases:

```bash
# Phase 1: 10% of stable users
curl -X POST http://localhost:8000/api/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "1.5.0",
    "target": {"channels": ["stable"]},
    "rollout_type": "gradual",
    "rollout_percentage": 10
  }'

# Wait 24 hours, monitor metrics
# Phase 2: Increase to 30%
curl -X PATCH http://localhost:8000/api/rollouts/1 \
  -H "Content-Type: application/json" \
  -d '{"rollout_percentage": 30}'

# Wait 24 hours, monitor metrics
# Phase 3: Increase to 50%
curl -X PATCH http://localhost:8000/api/rollouts/1 \
  -H "Content-Type: application/json" \
  -d '{"rollout_percentage": 50}'

# Wait 24 hours, monitor metrics
# Phase 4: Increase to 100%
curl -X PATCH http://localhost:8000/api/rollouts/1 \
  -H "Content-Type: application/json" \
  -d '{"rollout_percentage": 100}'
```

### Strategy 3: Scheduled Off-Peak Updates

Schedule updates for low-traffic periods:

```bash
# Schedule for 2 AM UTC
curl -X POST http://localhost:8000/api/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "1.5.0",
    "target": {"channels": ["stable"]},
    "rollout_type": "scheduled",
    "scheduled_for": "2025-01-20T02:00:00Z"
  }'
```

### Strategy 4: Targeted Beta Testing

Test with specific users before broad release:

```bash
# Upload to beta channel
curl -X POST http://localhost:8000/api/firmware/upload \
  -F "file=@firmware-1.5.0.bin" \
  -F "version=1.5.0" \
  -F "channel=beta"

# Roll out to specific beta testers
curl -X POST http://localhost:8000/api/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "1.5.0",
    "target": {
      "user_ids": [
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001"
      ]
    },
    "rollout_type": "immediate"
  }'
```

---

## API Reference

### Firmware Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/firmware/upload` | Upload firmware binary |
| GET | `/api/firmware/latest?channel={channel}` | Get latest firmware version |
| GET | `/api/firmware/{version}` | Get specific firmware details |
| GET | `/api/firmware?channel={channel}` | List all firmware versions |
| GET | `/api/firmware/download/{version}` | Download firmware binary |
| DELETE | `/api/firmware/{version}` | Delete firmware version |

### Rollout Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/rollouts` | Create new rollout |
| GET | `/api/rollouts?status={status}` | List rollouts |
| GET | `/api/rollouts/{rollout_id}` | Get rollout details |
| PATCH | `/api/rollouts/{rollout_id}` | Update rollout (status/percentage) |
| DELETE | `/api/rollouts/{rollout_id}` | Delete rollout |

### Printer Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/printers` | List printers with filters |
| GET | `/api/printers/{printer_id}` | Get printer details |
| GET | `/api/printers/{printer_id}/updates` | Get printer update history |

### WebSocket Endpoint

| Endpoint | Description |
|----------|-------------|
| `WS /ws/{user_id}` | WebSocket connection for printers |

---

## Best Practices

### 1. Testing Strategy

**Always test in stages:**

```
canary (1%) → beta (10-20%) → stable (gradual 10% → 50% → 100%)
```

### 2. Gradual Rollouts

**Start small, monitor, then increase:**

- Start with 10% of users
- Monitor error rates and user feedback for 24-48 hours
- Increase to 30%, then 50%, then 100%
- Pause immediately if critical issues are found

### 3. Version Constraints

**Use version constraints to skip problematic versions:**

```json
{
  "target": {
    "channels": ["stable"],
    "min_version": "1.5.0",
    "max_version": "1.9.0"
  }
}
```

This excludes printers on 1.4.x or earlier (may have compatibility issues) and 2.0.0+ (already newer).

### 4. Mandatory Updates

**Use mandatory flag sparingly:**

Only for:
- Critical security fixes
- Breaking service changes
- Compliance requirements

```bash
curl -X POST http://localhost:8000/api/firmware/upload \
  -F "file=@critical-fix.bin" \
  -F "version=1.5.1" \
  -F "channel=stable" \
  -F "mandatory=true" \
  -F "release_notes=Critical security fix - update immediately"
```

### 5. Monitoring

**Monitor these metrics during rollout:**

- Success rate (should be >95%)
- Failure rate (should be <5%)
- Error messages (look for patterns)
- Rollout counters (pending, completed, failed, declined)

**Check rollout status:**

```bash
watch -n 5 'curl -s http://localhost:8000/api/rollouts/1 | jq'
```

### 6. Rollback Plan

**Have a rollback plan:**

```bash
# If issues found, cancel rollout immediately
curl -X PATCH http://localhost:8000/api/rollouts/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "cancelled"}'

# Upload previous stable version
curl -X POST http://localhost:8000/api/firmware/upload \
  -F "file=@firmware-1.4.0.bin" \
  -F "version=1.4.0" \
  -F "channel=stable"

# Create rollback rollout
curl -X POST http://localhost:8000/api/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "1.4.0",
    "target": {"channels": ["stable"]},
    "rollout_type": "immediate"
  }'
```

### 7. Communication

**Provide clear release notes:**

- What's new
- What's fixed
- What's changed
- Known issues
- Migration steps (if any)

### 8. Off-Peak Updates

**Schedule major updates for low-traffic periods:**

```json
{
  "rollout_type": "scheduled",
  "scheduled_for": "2025-01-20T02:00:00Z"
}
```

### 9. Printer Auto-Update Settings

**Educate users to enable auto-update:**

Printers should connect with:
```json
{
  "auto_update": true,
  "update_channel": "stable"
}
```

### 10. Backup Before Updates

**Ensure printers can recover:**

- Keep previous firmware version available
- Implement rollback mechanism on printer
- Handle update failures gracefully

---

## Troubleshooting

### Firmware Upload Issues

**Error: "Firmware version already exists"**

Solution: Use a different version number or delete the existing version first.

```bash
# Delete existing version
curl -X DELETE http://localhost:8000/api/firmware/1.5.0
```

**Error: "File too large"**

Solution: The firmware file exceeds the 5MB limit. Either:
1. Reduce firmware size, or
2. Increase `max_firmware_size` in config

### Rollout Issues

**Error: "Firmware version not found"**

Solution: Ensure the firmware version exists before creating a rollout:

```bash
# Check if firmware exists
curl http://localhost:8000/api/firmware/1.5.0
```

**No printers are receiving updates**

Possible causes:
1. Printers are offline
2. Printers have `auto_update: false`
3. Rollout targeting doesn't match any printers
4. Rollout status is not "active"

**Check rollout targeting:**

```bash
# Get rollout details
curl http://localhost:8000/api/rollouts/1 | jq '.total_targets'

# List matching printers
curl http://localhost:8000/api/printers?channel=stable
```

### Printer Not Updating

**Check printer settings:**

```bash
# Get printer details
curl http://localhost:8000/api/printers/42

# Look for:
# - auto_update: true
# - update_channel matches rollout target
# - firmware_version is older than target version
```

**Check printer update history:**

```bash
curl http://localhost:8000/api/printers/42/updates | jq '.updates[0]'
```

Look for:
- `status: "failed"` with error message
- `status: "declined"` if auto_update is false
- `status: "pending"` if printer hasn't connected yet

### High Failure Rate

**Check error messages:**

```bash
curl http://localhost:8000/api/printers/42/updates | jq '.updates[] | select(.status == "failed") | .error_message'
```

Common causes:
- Insufficient storage space
- Network connectivity issues
- Invalid firmware format
- MD5 checksum mismatch
- Printer hardware issues

### Gradual Rollout Not Working

**Ensure deterministic hashing:**

The same printer should always get the same bucket. Test with:

```bash
# Create 10% rollout
curl -X POST http://localhost:8000/api/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "1.5.0",
    "target": {"channels": ["stable"]},
    "rollout_type": "gradual",
    "rollout_percentage": 10
  }'

# Check if specific printer got update
curl http://localhost:8000/api/printers/42/updates | jq '.updates[0].firmware_version'
```

If printer didn't get update at 10%, it should get it when increased to 20-30%.

### Scheduled Rollout Not Starting

**Check timezone:**

The `scheduled_for` timestamp is in UTC. Ensure you're using the correct timezone:

```bash
# Current time in UTC
date -u

# Schedule for 2 AM UTC tomorrow
date -u -d "tomorrow 02:00" +%Y-%m-%dT%H:%M:%SZ
```

---

## Complete Workflow Example

Here's a complete end-to-end example of pushing a firmware update:

### Step 1: Prepare Firmware

```bash
# Build your firmware
./build-firmware.sh
# Output: paperminder-1.5.0.bin

# Calculate checksums (optional, server does this automatically)
md5sum paperminder-1.5.0.bin
sha256sum paperminder-1.5.0.bin
```

### Step 2: Upload Firmware

```bash
curl -X POST http://localhost:8000/api/firmware/upload \
  -F "file=@paperminder-1.5.0.bin" \
  -F "version=1.5.0" \
  -F "channel=stable" \
  -F "release_notes=Major update: New features and bug fixes" \
  -F "changelog=- Added support for new paper types\n- Fixed print quality issues\n- Improved battery life\n- Enhanced security" \
  -F "mandatory=false" \
  -F "min_upgrade_version=1.0.0"
```

Response:
```json
{
  "id": 42,
  "version": "1.5.0",
  "channel": "stable",
  "file_size": 1048576,
  "md5_checksum": "d41d8cd98f00b204e9800998ecf8427e",
  ...
}
```

### Step 3: Create Gradual Rollout

```bash
curl -X POST http://localhost:8000/api/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "1.5.0",
    "target": {
      "channels": ["stable"],
      "min_version": "1.0.0"
    },
    "rollout_type": "gradual",
    "rollout_percentage": 10
  }'
```

Response:
```json
{
  "id": 15,
  "firmware_version": "1.5.0",
  "rollout_type": "gradual",
  "rollout_percentage": 10,
  "status": "active",
  "total_targets": 500,
  "pending_count": 450,
  "completed_count": 0,
  ...
}
```

### Step 4: Monitor Rollout

```bash
# Watch rollout progress
watch -n 10 'curl -s http://localhost:8000/api/rollouts/15 | jq "{
  status: .status,
  total: .total_targets,
  completed: .completed_count,
  failed: .failed_count,
  pending: .pending_count,
  success_rate: (.completed_count / .total_targets * 100)
}"'
```

### Step 5: Check for Issues

```bash
# Check failed updates
curl http://localhost:8000/api/printers/42/updates | \
  jq '.updates[] | select(.status == "failed") | {printer: .printer_id, error: .error_message}'

# List all printers that haven't updated yet
curl http://localhost:8000/api/printers?channel=stable | \
  jq '.printers[] | select(.firmware_version != "1.5.0") | {name: .name, version: .firmware_version, online: .online}'
```

### Step 6: Increase Rollout Percentage

After 24 hours with no issues:

```bash
# Increase to 30%
curl -X PATCH http://localhost:8000/api/rollouts/15 \
  -H "Content-Type: application/json" \
  -d '{"rollout_percentage": 30}'

# After another 24 hours, increase to 50%
curl -X PATCH http://localhost:8000/api/rollouts/15 \
  -H "Content-Type: application/json" \
  -d '{"rollout_percentage": 50}'

# After final verification, increase to 100%
curl -X PATCH http://localhost:8000/api/rollouts/15 \
  -H "Content-Type: application/json" \
  -d '{"rollout_percentage": 100}'
```

### Step 7: Verify Completion

```bash
# Check final rollout status
curl http://localhost:8000/api/rollouts/15 | jq '{
  total: .total_targets,
  completed: .completed_count,
  failed: .failed_count,
  declined: .declined_count,
  success_rate: (.completed_count / .total_targets * 100)
}'

# Check printer versions
curl http://localhost:8000/api/printers?channel=stable | \
  jq '.printers | group_by(.firmware_version) | map({version: .[0].firmware_version, count: length})'
```

---

## Conclusion

The PaperMinder firmware update system provides a robust, flexible way to manage and deliver firmware updates to your printer fleet. By following the best practices outlined in this guide, you can ensure smooth, safe, and reliable updates.

### Key Takeaways

1. **Test thoroughly** - Use canary/beta channels before stable release
2. **Roll out gradually** - Start small, monitor, then increase
3. **Monitor metrics** - Track success rates and error messages
4. **Plan for rollback** - Have a plan to revert if issues arise
5. **Communicate clearly** - Provide detailed release notes
6. **Use version constraints** - Target specific version ranges
7. **Schedule wisely** - Update during off-peak hours when possible

For questions or issues, refer to the [Troubleshooting](#troubleshooting) section or check the API documentation at `http://localhost:8000/docs`.
