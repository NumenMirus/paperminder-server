# Server-Side Implementation Guide: PaperMinder OTA Updates

This document provides complete specifications for implementing server-side components to support Over-The-Air (OTA) firmware updates for PaperMinder printers.

## Overview

The ESP8266 firmware now supports receiving firmware updates via WebSocket messages. The server needs to:

1. Store and serve firmware binaries
2. Track printer firmware versions
3. Push updates to targeted printers
4. Handle update progress reporting
5. Provide management interface for rollouts

## WebSocket Protocol Extensions

### Subscribe Message (Printer → Server)

When a printer connects, it sends a subscribe message with update information:

```json
{
  "printer_name": "Front Desk",
  "api_key": "user-api-key",
  "user_id": "user-123",
  "firmware_version": "1.0.0",
  "auto_update": true,
  "update_channel": "stable"
}
```

**New Fields:**
- `firmware_version` (string): Current firmware version on printer
- `auto_update` (boolean): Whether printer accepts automatic updates
- `update_channel` (string): One of "stable", "beta", "canary"

### Firmware Update Message (Server → Printer)

To push an update to a printer, send this message type:

```json
{
  "kind": "firmware_update",
  "version": "1.1.0",
  "url": "https://your-server.com/firmware/paperminder-1.1.0.bin",
  "md5": "5d41402abc4b2a76b9719d911017c592"
}
```

**Fields:**
- `kind`: Must be "firmware_update"
- `version`: Target firmware version (semantic versioning like "1.2.3")
- `url`: HTTPS URL to download firmware binary
- `md5`: MD5 checksum of firmware file (optional but recommended)

### Printer Response Messages

#### 1. Firmware Declined (if auto-update is disabled)

```json
{
  "kind": "firmware_declined",
  "version": "1.1.0",
  "auto_update": false
}
```

#### 2. Firmware Progress (during download/install)

```json
{
  "kind": "firmware_progress",
  "percent": 45,
  "status": "Downloading 45%"
}
```

Percent ranges from 0-100, or -1 for errors.

#### 3. Firmware Complete (successful update)

```json
{
  "kind": "firmware_complete",
  "version": "1.1.0"
}
```

Printer will reboot after sending this message.

#### 4. Firmware Failed (update error)

```json
{
  "kind": "firmware_failed",
  "error": "Update failed: HTTP error 404"
}
```

## Database Schema

### Printers Table

Track all registered printers and their firmware status:

```sql
CREATE TABLE printers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  printer_id VARCHAR(36) UNIQUE NOT NULL,  -- UUID from ESP8266
  user_id VARCHAR(32),
  printer_name VARCHAR(32),
  api_key VARCHAR(64),

  -- Firmware tracking
  firmware_version VARCHAR(16) DEFAULT '0.0.0',
  auto_update BOOLEAN DEFAULT true,
  update_channel VARCHAR(16) DEFAULT 'stable',

  -- Connection tracking
  last_connected TIMESTAMP,
  last_ip VARCHAR(45),
  online BOOLEAN DEFAULT false,

  -- Metadata
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_printers_user_id ON printers(user_id);
CREATE INDEX idx_printers_printer_id ON printers(printer_id);
```

### Firmware Versions Table

Store firmware metadata and binaries:

```sql
CREATE TABLE firmware_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  version VARCHAR(16) UNIQUE NOT NULL,
  channel VARCHAR(16) NOT NULL,  -- stable, beta, canary

  -- File info
  file_url VARCHAR(512) NOT NULL,
  file_size BIGINT NOT NULL,
  md5_checksum VARCHAR(32) NOT NULL,
  sha256_checksum VARCHAR(64),

  -- Release info
  release_notes TEXT,
  changelog TEXT,
  mandatory BOOLEAN DEFAULT false,
  min_upgrade_version VARCHAR(16),  -- Minimum version that can upgrade to this

  -- Availability
  released_at TIMESTAMP DEFAULT NOW(),
  deprecated_at TIMESTAMP,

  -- Statistics
  download_count INTEGER DEFAULT 0,
  success_count INTEGER DEFAULT 0,
  failure_count INTEGER DEFAULT 0,

  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_firmware_versions_version ON firmware_versions(version);
CREATE INDEX idx_firmware_versions_channel ON firmware_versions(channel, released_at DESC);
```

### Update Rollouts Table

Track update rollout campaigns:

```sql
CREATE TABLE update_rollouts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firmware_version_id UUID NOT NULL REFERENCES firmware_versions(id),

  -- Targeting
  target_all BOOLEAN DEFAULT false,
  target_user_ids TEXT[],  -- Array of user IDs to target
  target_printer_ids TEXT[],  -- Array of printer IDs to target
  target_channels TEXT[],  -- Array of update channels to target
  min_version VARCHAR(16),  -- Only update printers on this version or higher
  max_version VARCHAR(16),  -- Only update printers on this version or lower

  -- Rollout strategy
  rollout_type VARCHAR(32) NOT NULL,  -- immediate, gradual, scheduled
  rollout_percentage INTEGER DEFAULT 0,  -- For gradual rollouts (0-100)
  scheduled_for TIMESTAMP,  -- For scheduled rollouts

  -- Status
  status VARCHAR(32) NOT NULL DEFAULT 'pending',  -- pending, active, paused, completed, cancelled

  -- Progress tracking
  total_targets INTEGER DEFAULT 0,
  completed_count INTEGER DEFAULT 0,
  failed_count INTEGER DEFAULT 0,
  declined_count INTEGER DEFAULT 0,
  pending_count INTEGER DEFAULT 0,

  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_update_rollouts_status ON update_rollouts(status, created_at DESC);
```

### Update History Table

Track individual update attempts:

```sql
CREATE TABLE update_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rollout_id UUID REFERENCES update_rollouts(id),
  printer_id VARCHAR(36) NOT NULL,
  firmware_version VARCHAR(16) NOT NULL,

  -- Status tracking
  status VARCHAR(32) NOT NULL,  -- pending, downloading, completed, failed, declined
  error_message TEXT,

  -- Timing
  started_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP,

  -- Progress
  last_percent INTEGER DEFAULT 0,
  last_status_message VARCHAR(256)
);

CREATE INDEX idx_update_history_printer_id ON update_history(printer_id, started_at DESC);
CREATE INDEX idx_update_history_rollout_id ON update_history(rollout_id, started_at);
```

## REST API Endpoints

### 1. Firmware Management

#### Upload Firmware

```
POST /api/firmware/upload
Content-Type: multipart/form-data

Form fields:
  - file: firmware.bin (the compiled firmware binary)
  - version: "1.1.0"
  - channel: "stable" | "beta" | "canary"
  - release_notes: "Bug fixes and improvements"
  - mandatory: true/false
  - min_upgrade_version: "1.0.0" (optional)

Response:
{
  "id": "uuid",
  "version": "1.1.0",
  "file_url": "https://cdn.server.com/firmware/paperminder-1.1.0.bin",
  "md5": "checksum",
  "uploaded_at": "2025-12-24T10:00:00Z"
}
```

#### Get Latest Firmware

```
GET /api/firmware/latest?channel=stable

Response:
{
  "version": "1.1.0",
  "channel": "stable",
  "file_url": "https://...",
  "md5": "checksum",
  "release_notes": "...",
  "released_at": "2025-12-24T10:00:00Z"
}
```

#### Get Firmware by Version

```
GET /api/firmware/{version}

Response: Same as above
```

### 2. Printer Management

#### List Printers

```
GET /api/printers?user_id={user_id}&online=true&firmware_version=1.0.0

Response:
{
  "printers": [
    {
      "printer_id": "uuid",
      "printer_name": "Front Desk",
      "firmware_version": "1.0.0",
      "auto_update": true,
      "update_channel": "stable",
      "online": true,
      "last_connected": "2025-12-24T10:00:00Z"
    }
  ],
  "total": 42
}
```

#### Get Printer Details

```
GET /api/printers/{printer_id}

Response:
{
  "printer_id": "uuid",
  "user_id": "user-123",
  "printer_name": "Front Desk",
  "firmware_version": "1.0.0",
  "auto_update": true,
  "update_channel": "stable",
  "online": true,
  "last_connected": "2025-12-24T10:00:00Z",
  "last_ip": "192.168.1.100",
  "created_at": "2025-01-01T00:00:00Z"
}
```

### 3. Update Rollout Management

#### Create Rollout

```
POST /api/rollouts

Request:
{
  "firmware_version": "1.1.0",
  "target": {
    "all": false,
    "user_ids": ["user-123", "user-456"],
    "printer_ids": ["printer-abc", "printer-def"],
    "channels": ["stable"],
    "min_version": "1.0.0",
    "max_version": "1.0.5"
  },
  "rollout_type": "gradual",
  "rollout_percentage": 10,  // Start with 10% of targets
  "scheduled_for": "2025-12-25T02:00:00Z"  // Optional
}

Response:
{
  "id": "rollout-uuid",
  "status": "pending",
  "total_targets": 150,
  "rollout_percentage": 10
}
```

#### List Rollouts

```
GET /api/rollouts?status=active

Response:
{
  "rollouts": [
    {
      "id": "rollout-uuid",
      "firmware_version": "1.1.0",
      "status": "active",
      "rollout_percentage": 25,
      "total_targets": 150,
      "completed_count": 37,
      "failed_count": 2,
      "pending_count": 111,
      "created_at": "2025-12-24T10:00:00Z"
    }
  ]
}
```

#### Get Rollout Details

```
GET /api/rollouts/{rollout_id}

Response: Same as create rollout response, plus:
{
  "targets": [
    {
      "printer_id": "uuid",
      "status": "completed",
      "started_at": "...",
      "completed_at": "..."
    }
  ]
}
```

#### Update Rollout (pause/resume/cancel)

```
PATCH /api/rollouts/{rollout_id}

Request:
{
  "status": "paused" | "active" | "cancelled",
  "rollout_percentage": 50  // Increase to 50%
}
```

#### Delete Rollout

```
DELETE /api/rollouts/{rollout_id}
```

### 4. Update History

#### Get Update History for Printer

```
GET /api/printers/{printer_id}/updates

Response:
{
  "updates": [
    {
      "id": "uuid",
      "firmware_version": "1.0.5",
      "status": "completed",
      "started_at": "2025-12-20T10:00:00Z",
      "completed_at": "2025-12-20T10:02:30Z"
    }
  ]
}
```

## WebSocket Service Implementation

### Update Push Service

The existing WebSocket handler needs extensions to support firmware updates:

```python
class WebSocketPrinterHandler:
    def on_subscribe(self, printer_id, message):
        """Handle printer subscription message"""
        # Update printer status in database
        printer = db.get_printer(printer_id)
        printer.firmware_version = message.get('firmware_version')
        printer.auto_update = message.get('auto_update', True)
        printer.update_channel = message.get('update_channel', 'stable')
        printer.online = True
        printer.last_connected = now()
        db.save(printer)

        # Check if update is available
        self.check_and_push_update(printer)

    def check_and_push_update(self, printer):
        """Check if an update is available and push to printer"""
        if not printer.auto_update:
            return

        # Get latest firmware for printer's channel
        latest = db.get_latest_firmware(printer.update_channel)

        # Check if update is needed
        if compare_versions(latest.version, printer.firmware_version) > 0:
            # Check if there's an active rollout for this printer
            rollout = db.get_active_rollout_for_printer(
                printer.printer_id,
                latest.version
            )

            if rollout and self.should_update_now(rollout, printer):
                self.push_update(printer, latest)

    def push_update(self, printer, firmware):
        """Push firmware update to printer"""
        update_message = {
            "kind": "firmware_update",
            "version": firmware.version,
            "url": firmware.file_url,
            "md5": firmware.md5_checksum
        }

        self.send_to_printer(printer.printer_id, update_message)

        # Record in update history
        db.create_update_record(
            printer_id=printer.printer_id,
            firmware_version=firmware.version,
            status='pending'
        )

    def on_firmware_progress(self, printer_id, message):
        """Handle firmware update progress"""
        db.update_update_progress(
            printer_id=printer_id,
            percent=message.get('percent'),
            status=message.get('status')
        )

    def on_firmware_complete(self, printer_id, message):
        """Handle successful firmware update"""
        db.mark_update_complete(
            printer_id=printer_id,
            version=message.get('version')
        )

        # Update printer's firmware version
        printer = db.get_printer(printer_id)
        printer.firmware_version = message.get('version')
        db.save(printer)

    def on_firmware_failed(self, printer_id, message):
        """Handle failed firmware update"""
        db.mark_update_failed(
            printer_id=printer_id,
            error=message.get('error')
        )

    def on_firmware_declined(self, printer_id, message):
        """Handle declined firmware update"""
        db.mark_update_declined(
            printer_id=printer_id,
            version=message.get('version')
        )
```

### Gradual Rollout Logic

```python
def should_update_now(rollout, printer):
    """Determine if printer should receive update now (for gradual rollouts)"""
    if rollout.rollout_type == 'immediate':
        return True

    if rollout.rollout_type == 'gradual':
        # Use consistent hashing to assign printers to rollout buckets
        bucket = consistent_hash(printer.printer_id) % 100
        return bucket < rollout.rollout_percentage

    if rollout.rollout_type == 'scheduled':
        return now() >= rollout.scheduled_for

    return False
```

## Firmware File Storage

### Storage Options

1. **Object Storage (Recommended)**
   - AWS S3, Google Cloud Storage, Azure Blob Storage
   - Pre-signed URLs for secure downloads
   - CDN integration for faster downloads

2. **Local File Storage**
   - Store in `/var/www/firmware/`
   - Serve via nginx/Apache
   - Less scalable but simpler for small deployments

### File Naming Convention

```
paperminder-{version}-{channel}.bin
Example: paperminder-1.1.0-stable.bin
```

### Security Considerations

1. **Pre-signed URLs**
   ```python
   # Generate time-limited download URL
   url = s3.generate_presigned_url(
       'get_object',
       Params={'Bucket': 'firmware', 'Key': 'paperminder-1.1.0.bin'},
       ExpiresIn=3600  # 1 hour
   )
   ```

2. **Firmware Signing** (Future Enhancement)
   - Sign firmware binaries with RSA/ECDSA
   - Include signature in update message
   - Verify signature on device before applying

## Admin Interface

### Required Features

1. **Dashboard**
   - Total printers online/offline
   - Firmware version distribution chart
   - Active rollouts status
   - Recent update success/failure rates

2. **Firmware Management**
   - Upload new firmware versions
   - View firmware versions and metadata
   - Mark firmware as mandatory
   - Deprecate old versions

3. **Rollout Management**
   - Create new rollout campaign
   - Target specific printers or user groups
   - Set rollout percentage for gradual deployments
   - Monitor rollout progress in real-time
   - Pause/resume/cancel rollouts

4. **Printer Management**
   - View all printers with status
   - Filter by user, version, online status
   - Force update specific printers
   - View update history per printer

5. **Update History**
   - View all update attempts
   - Filter by printer, version, status
   - View error messages for failed updates
   - Export update reports

## Deployment Checklist

### Backend Tasks

- [ ] Set up database tables (PostgreSQL recommended)
- [ ] Implement REST API endpoints
- [ ] Extend WebSocket handler for firmware update messages
- [ ] Implement firmware file storage (S3 or local)
- [ ] Build admin interface (Web UI or CLI)
- [ ] Set up CDN for firmware downloads (if using S3)
- [ ] Implement rollout logic with gradual deployment
- [ ] Add monitoring and alerting
- [ ] Create backup and recovery procedures

### Security Tasks

- [ ] Enable HTTPS on all endpoints
- [ ] Implement authentication for API endpoints
- [ ] Add rate limiting for firmware downloads
- [ ] Set up firewall rules for database access
- [ ] Implement audit logging for all update operations
- [ ] Consider firmware signing (future enhancement)

### Testing Tasks

- [ ] Test firmware upload and storage
- [ ] Test update push to single device
- [ ] Test gradual rollout logic
- [ ] Test rollback mechanisms
- [ ] Load test with multiple concurrent updates
- [ ] Test error handling (network failures, corrupt firmware, etc.)

## Monitoring and Metrics

### Key Metrics to Track

1. **Update Success Rate**
   - Percentage of updates that complete successfully
   - Track by firmware version, device type, region

2. **Update Duration**
   - Time from start to completion
   - Identify slow or stuck updates

3. **Rollout Progress**
   - Percentage of devices updated in active rollouts
   - Track completion over time

4. **Error Rates**
   - Most common error types
   - Error rates by firmware version

5. **Device Online Status**
   - Number of devices online/offline
   - Connection uptime statistics

### Alerting

- Alert on high failure rates (>10%)
- Alert on stuck updates (>30 minutes)
- Alert on devices offline >24 hours
- Alert on rollback events

## Example Rollout Workflow

### Scenario: Deploy version 1.1.0 to all printers

1. **Upload Firmware**
   ```bash
   curl -X POST https://api.server.com/api/firmware/upload \
     -F file=@paperminder-1.1.0.bin \
     -F version="1.1.0" \
     -F channel="stable" \
     -F release_notes="Bug fixes and performance improvements"
   ```

2. **Create Gradual Rollout**
   ```bash
   curl -X POST https://api.server.com/api/rollouts \
     -H "Content-Type: application/json" \
     -d '{
       "firmware_version": "1.1.0",
       "target": {
         "all": true,
         "channels": ["stable"],
         "min_version": "1.0.0"
       },
       "rollout_type": "gradual",
       "rollout_percentage": 5
     }'
   ```

3. **Monitor Progress**
   ```bash
   curl https://api.server.com/api/rollouts/{rollout_id}
   ```

4. **Increase Rollout** (after verifying success)
   ```bash
   curl -X PATCH https://api.server.com/api/rollouts/{rollout_id} \
     -H "Content-Type: application/json" \
     -d '{"rollout_percentage": 25}'
   ```

5. **Complete Rollout**
   ```bash
   curl -X PATCH https://api.server.com/api/rollouts/{rollout_id} \
     -H "Content-Type: application/json" \
     -d '{"rollout_percentage": 100}'
   ```

## Troubleshooting

### Common Issues

1. **Printers not receiving updates**
   - Check printer's `auto_update` setting
   - Verify printer is online and connected
   - Check WebSocket connection logs
   - Verify firmware version comparison logic

2. **Updates failing**
   - Check firmware file URL is accessible
   - Verify MD5 checksum matches
   - Check printer has enough flash space
   - Review error messages in update history

3. **Rollout not progressing**
   - Verify rollout status is "active"
   - Check targeting criteria match printers
   - Review gradual rollout percentage logic
   - Check for errors in rollout worker logs

4. **Printers stuck in "downloading"**
   - May indicate network issues
   - Check firmware file size and CDN performance
   - Monitor update progress callbacks
   - Consider increasing timeout values

## Future Enhancements

1. **Delta Updates**
   - Only send changed portions of firmware
   - Reduce bandwidth and download time
   - Requires more complex build and patching system

2. **Firmware Signing**
   - Sign binaries with private key
   - Verify signature on device
   - Prevent malicious firmware installation

3. **A/B Testing**
   - Deploy different firmware versions to different groups
   - Compare performance and stability
   - Gradually move successful versions to all devices

4. **Scheduled Maintenance Windows**
   - Configure time windows for updates
   - Avoid business hours
   - Per-timezone scheduling

5. **Configuration Updates**
   - Push configuration changes without full firmware update
   - Separate config from firmware
   - Faster iteration cycles

6. **Rollback on Failure**
   - Detect if new firmware has issues
   - Automatically roll back to previous version
   - Requires dual-partition OTA with rollback support

## Support and Contact

For questions about implementing this server-side system:
- Review the ESP8266 firmware code in `esp8266/src/ota_manager.cpp`
- Check WebSocket message handling in `esp8266/src/websocket.cpp`
- Test with the captive portal configuration interface

The printer-side implementation is complete and ready for server integration.
