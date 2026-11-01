# Database Schema Planning for Chat2HTML

## Current State: Service-Specific JSON Outputs

As per the integration requirements, we are maintaining **service-specific JSON formats** for now, avoiding forced unification until a proper unified schema is defined.

### Current JSON Formats by Service

#### 1. iMessage JSON Format (Native)
```json
{
  "id": 12345,
  "guid": "p:0/1234567890",
  "text": "Message content",
  "timestamp": "2024-01-15T10:30:00.000000",
  "sender": "John Doe",
  "chat": "Family Group",
  "service": "iMessage",
  "is_from_me": false,
  "is_read": true,
  "attachments": [
    {
      "original_filename": "IMG_1234.HEIC",
      "filename": "(2024-01-15) 10.30.00 [12345].jpg",
      "attachment_path": "/Attachments/iMessage/2024/01 - January/",
      "mime_type": "image/heic",
      "file_size": 2048576,
      "is_sticker": false,
      "file_hash": "sha256:abc123...",
      "is_duplicate": false,
      "conversion_applied": true
    }
  ],
  "tapbacks": [
    {
      "type": "Loved",
      "sender": "Jane Doe",
      "action": "Added"
    }
  ]
}
```

#### 2. WhatsApp JSON Format (Native)
```json
{
  "timestamp": "2024-01-15T10:30:00",
  "sender": "John Doe",
  "message": "Message content",
  "media_path": "/path/to/media.jpg",
  "media_type": "image",
  "is_forwarded": false,
  "reply_to": null
}
```

#### 3. Facebook Messenger JSON Format (Native)
```json
{
  "sender_name": "John Doe",
  "timestamp_ms": 1705312200000,
  "content": "Message content",
  "type": "Generic",
  "photos": [
    {
      "uri": "messages/photos/photo_123.jpg",
      "creation_timestamp": 1705312200
    }
  ],
  "reactions": [
    {
      "reaction": "❤️",
      "actor": "Jane Doe"
    }
  ]
}
```

## Future Unified Schema Design

### Proposed Unified Message Schema

```json
{
  "message_id": "unique_identifier",
  "conversation_id": "conversation_identifier",
  "service": "imessage|whatsapp|messenger",
  "timestamp": "ISO8601_datetime",
  "sender": {
    "id": "sender_identifier",
    "name": "Display Name",
    "phone": "+1234567890",
    "email": "user@example.com"
  },
  "content": {
    "text": "Message text content",
    "type": "text|media|system|reaction",
    "encoding": "utf-8",
    "language": "en"
  },
  "metadata": {
    "is_from_me": true,
    "is_read": true,
    "delivery_status": "delivered|read|failed",
    "edit_history": [],
    "reply_to": "message_id",
    "forwarded_from": "original_message_id"
  },
  "attachments": [
    {
      "id": "attachment_id",
      "original_filename": "IMG_1234.HEIC",
      "processed_filename": "(2024-01-15) 10.30.00 [12345].jpg",
      "mime_type": "image/heic",
      "file_size": 2048576,
      "file_hash": "sha256:abc123...",
      "storage_path": "/Attachments/service/year/month/",
      "processing_info": {
        "conversion_applied": true,
        "original_format": "heic",
        "processed_format": "jpg",
        "is_duplicate": false,
        "quality_settings": 85
      }
    }
  ],
  "reactions": [
    {
      "type": "love|like|laugh|emphasize|dislike|question",
      "emoji": "❤️",
      "sender": "sender_identifier",
      "timestamp": "ISO8601_datetime",
      "action": "added|removed"
    }
  ],
  "service_specific": {
    "imessage": {
      "guid": "p:0/1234567890",
      "item_type": 0,
      "balloon_bundle_id": null,
      "associated_message_type": null
    },
    "whatsapp": {
      "message_type": "text",
      "quoted_message": null
    },
    "messenger": {
      "thread_type": "Regular",
      "thread_path": "messages/inbox/conversation_123"
    }
  }
}
```

### Unified Conversation Schema

```json
{
  "conversation_id": "unique_identifier",
  "service": "imessage|whatsapp|messenger",
  "type": "individual|group",
  "name": "Conversation Name",
  "participants": [
    {
      "id": "participant_id",
      "name": "Display Name",
      "phone": "+1234567890",
      "email": "user@example.com",
      "role": "admin|member"
    }
  ],
  "metadata": {
    "created_date": "ISO8601_datetime",
    "last_activity": "ISO8601_datetime",
    "message_count": 12345,
    "media_count": 567,
    "is_archived": false
  },
  "service_specific": {
    "imessage": {
      "chat_identifier": "chat123456",
      "style": 43
    },
    "whatsapp": {
      "group_id": "group_123",
      "group_description": "Family chat"
    },
    "messenger": {
      "thread_path": "messages/inbox/conversation_123",
      "thread_type": "Regular"
    }
  }
}
```

## Migration Strategy

### Phase 1: Current Implementation ✅
- **Service-specific JSON outputs** maintained
- **No forced unification** - each service exports in its native format
- **AttachmentManager** designed as universal component
- **Configuration system** supports per-service settings

### Phase 2: Schema Standardization (Future)
1. **Define unified schema** based on common patterns across services
2. **Create schema validation** using JSON Schema or Pydantic models
3. **Implement conversion layer** from service-specific to unified format
4. **Maintain backward compatibility** with service-specific exports

### Phase 3: Database Integration (Future)
1. **Design unified SQLite schema** based on unified JSON schema
2. **Create migration tools** from service-specific to unified database
3. **Implement query abstraction layer** for cross-service analytics
4. **Add indexing and optimization** for large datasets

### Phase 4: Advanced Features (Future)
1. **Cross-service conversation linking** (same contact across platforms)
2. **Unified search and filtering** across all services
3. **Advanced analytics and reporting** on combined dataset
4. **Export to other formats** (CSV, XML, etc.)

## Design Principles

### 1. **Preserve Data Fidelity**
- Never lose service-specific information during unification
- Maintain original timestamps, IDs, and metadata
- Store service-specific fields in dedicated sections

### 2. **Flexible Schema Evolution**
- Use extensible JSON structures that can accommodate new fields
- Version schema definitions for backward compatibility
- Support optional fields for service-specific features

### 3. **Performance Optimization**
- Design for efficient querying across large datasets
- Use appropriate indexing strategies for common access patterns
- Support streaming/batch processing for memory efficiency

### 4. **Attachment Handling**
- Unified attachment processing pipeline (already implemented)
- Consistent file naming and organization across services
- SHA-256 deduplication to save storage space
- Format conversion for long-term compatibility

## Current Status

✅ **Service-specific JSON exports** - Each service maintains its native format
✅ **Universal attachment processing** - AttachmentManager works across services  
✅ **Configuration system** - Supports per-service and global settings
✅ **iMessage integration** - Direct database access with 99.887% text extraction
⏳ **Unified schema definition** - Planned for future implementation
⏳ **Database migration tools** - Planned for future implementation
⏳ **Cross-service analytics** - Planned for future implementation

## Recommendations

1. **Continue with service-specific exports** until unified schema is fully designed
2. **Focus on data quality and performance** for individual services
3. **Design unified schema collaboratively** with input from real-world usage patterns
4. **Implement gradual migration** rather than big-bang conversion
5. **Maintain service-specific exports** even after unified schema is available
