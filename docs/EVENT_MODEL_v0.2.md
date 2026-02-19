# Emberlog Event Model

**Version:** 0.2  
**Status:** Foundational Contract Definition  
**Applies To:** All modules, hub ingestion, REST responses, and SSE streams  

---

## 1. Purpose

The Emberlog Event Model defines the canonical structure for all events within the platform.

- All modules MUST emit events conforming to this model.
- All hub publications (REST and SSE) MUST use this model.

The event model is the platform’s shared language.

---

## 2. Event Envelope

Every event in Emberlog MUST use the following envelope:

```json
{
  "event_id": "uuid",
  "event_type": "string",
  "schema_version": "1.0.0",
  "timestamp": "ISO-8601 UTC string",
  "correlation_id": "optional uuid|string",
  "source": {
    "module": "string",
    "instance": "string",
    "system": "optional string"
  },
  "payload": {}
}
```

### 2.1 Field Definitions

#### event_id
- Globally unique identifier (UUID v4 preferred)
- Used for idempotency and deduplication

#### event_type
Namespaced string in dot-notation:

```
domain.entity.action
```

Examples:
- `traffic.call.started`
- `traffic.call.ended`
- `system.site.decode_rate.updated`
- `dispatch.incident.created`
- `dispatch.incident.updated`

#### schema_version
Semantic version for the specific event type schema (not the platform as a whole).

Examples:
- `1.0.0`
- `1.1.0`
- `2.0.0`

#### timestamp
UTC ISO-8601 timestamp representing when the event occurred (not when processed).

#### correlation_id (optional)
Optional identifier used to associate related events across domains.

Examples:
- A `traffic.call.*` series that results in a `dispatch.incident.created`
- An incident that receives multiple updates

UUID is recommended, but any stable opaque string is acceptable.

#### source
Metadata describing the origin of the event.

- `module`: name of module producing the event (e.g., `emberlog-transcriber`)
- `instance`: identifier of the running instance (hostname, pod name, etc.)
- `system` (optional): trunked system identifier (e.g., PRWC, AZWINS)

#### payload
The structured data specific to the event type.

---

## 3. Shared Concepts

### 3.1 Audio Reference

Events MAY include audio references using the following structure:

```json
{
  "audio": {
    "ref": "string",
    "kind": "file|object|stream",
    "format": "optional string (wav|mp3|opus|...)",
    "uri": "optional string",
    "segment": {
      "start_ms": 0,
      "end_ms": 12345
    }
  }
}
```

Guidance:
- `ref` is a stable identifier (TR recording key, DB id, content hash, etc.).
- `uri` may be omitted if audio is not directly accessible to the client.
- `segment` is optional and enables future “play the call” and “play the snippet” features.

This structure intentionally supports evolution from “file path” to streaming without breaking schema shape.

---

## 4. Domain Taxonomy

Event types are grouped by domain.

---

### 4.1 Traffic Domain

Represents raw trunked radio call activity.

#### traffic.call.started (suggested payload)

```json
{
  "system": "string",
  "site": "string",
  "call_id": "string",
  "trunkgroup_id": "number|string",
  "trunkgroup_label": "optional string",
  "frequency": "optional number",
  "audio": {
    "ref": "optional string",
    "kind": "file|object|stream",
    "format": "optional string",
    "uri": "optional string",
    "segment": { "start_ms": 0, "end_ms": 0 }
  }
}
```

Notes:
- `call_id` MUST remain stable across call lifecycle events.
- `audio` is optional and may be omitted until available.

#### traffic.call.ended (suggested payload)

```json
{
  "system": "string",
  "site": "string",
  "call_id": "string",
  "trunkgroup_id": "number|string",
  "duration_seconds": "optional number",
  "audio": {
    "ref": "optional string",
    "kind": "file|object|stream",
    "format": "optional string",
    "uri": "optional string",
    "segment": { "start_ms": 0, "end_ms": 0 }
  }
}
```

Notes:
- `duration_seconds` MAY be computed by the hub if not provided.
- `audio` MAY appear here even if it was unknown at call start.

---

### 4.2 System Domain

Represents monitoring system health and telemetry.

#### system.site.decode_rate.updated (suggested payload)

```json
{
  "system": "string",
  "site": "string",
  "decode_rate": "float (0-1)",
  "control_channel_frequency": "optional number"
}
```

Future system event types may include:
- `system.site.online`
- `system.site.offline`
- `system.error.*`

Signal-level telemetry (RSSI/BER/etc.) is explicitly deferred.

---

### 4.3 Dispatch Domain

Represents structured intelligence derived from modules (e.g., transcription).

The dispatch domain MUST remain generic. Region/system-specific semantics belong in module adapters and/or the `parsed` field.

#### dispatch.incident.created (canonical payload)

```json
{
  "incident_id": "string",
  "dispatched_at": "ISO-8601 UTC string",
  "special_call": false,
  "units": ["string"],
  "channel": "optional string",
  "incident_type": "optional string",
  "address": "optional string",
  "audio": {
    "ref": "string",
    "kind": "file|object|stream",
    "format": "optional string",
    "uri": "optional string",
    "segment": { "start_ms": 0, "end_ms": 0 }
  },
  "original_text": "optional string",
  "transcript": "optional string",
  "parsed": {}
}
```

Notes:
- `audio.ref` replaces older notions of “source audio path” while remaining compatible with file-based storage.
- `parsed` is the adapter sandbox: it may contain region-specific extraction, but consumers must treat it as optional and non-canonical.

#### dispatch.incident.updated (suggested payload)

```json
{
  "incident_id": "string",
  "changes": {}
}
```

Notes:
- `changes` is intentionally flexible for v0.x.
- A stricter patch format may be defined later.

---

## 5. Extension Rules

To prevent schema rigidity while keeping contracts stable:

- Payloads MAY include `metadata` objects where useful.
- Module-specific fields MUST NOT override canonical field meanings.
- New required fields require a major schema version bump for that event type.
- Consumers MUST tolerate unknown optional fields (forward compatibility).

---

## 6. Correlation Guidance

- `correlation_id` SHOULD be used when an event is derived from another event.
- One `correlation_id` may span multiple calls if an incident involves multiple related transmissions.
- Correlation is primarily for cross-domain association (calls ↔ incidents ↔ notifications ↔ audio playback).

---

## 7. Versioning Rules

Emberlog follows semantic versioning for event schemas:

- Patch (`1.0.1`): non-breaking clarifications or tightening constraints that do not invalidate existing payloads
- Minor (`1.1.0`): backward-compatible additions (new optional fields)
- Major (`2.0.0`): breaking changes

Breaking change examples:
- Removing a required field
- Changing a field type
- Renaming fields
- Changing semantics of an existing field

---

## 8. Ordering & Idempotency

The platform does NOT guarantee strict global ordering across all event types.

Consumers must:

- Use `event_id` for deduplication
- Use `timestamp` for ordering within a domain (when needed)
- Treat events as immutable once published

---

## 9. REST and SSE Consistency

- All REST endpoints returning event data MUST use the same envelope.
- All SSE streams MUST deliver events using the same envelope.

There are no transport-specific schemas.

---

## 10. Ingest Requirements

Modules sending events to the hub:

- MUST validate against canonical schemas
- MUST include `schema_version`
- MUST provide stable identifiers (`event_id`, and domain IDs like `call_id` / `incident_id`)
- MUST NOT write directly to hub storage outside the hub’s ingest path

---

## 11. Design Guardrails

- The event model must remain generic to trunked radio systems.
- Region-specific intelligence belongs in modules (adapters).
- The hub enforces structure, not interpretation.
- Payloads should favor extensibility over unnecessary rigidity.

---

## 12. Future Considerations (Not v1)

- Signal quality metrics (RSSI/BER/etc.)
- Explicit audio lifecycle events (e.g., `audio.available`, `audio.stream.ready`)
- Stricter patch formats for updates
- Event replay streams / backfill semantics after reconnect
- Batch ingestion and bulk query

---

# End of Event Model v0.2
