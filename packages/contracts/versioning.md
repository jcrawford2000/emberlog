# Contract Versioning

Emberlog contracts are versioned to preserve compatibility across independent services.

## Contract types

1. **Event schemas** (event envelope + event_type payloads)
2. **API schemas** (REST/SSE endpoints and response shapes)

## Versioning rules

Use semantic versioning (SemVer) for contract artifacts:

- **Patch** (`1.0.1`): Clarifications or non-breaking constraint tightening
- **Minor** (`1.1.0`): Backward-compatible additions (new optional fields, new event types)
- **Major** (`2.0.0`): Breaking changes (removed fields, renamed fields, type changes, semantic changes)

## Source of truth

- During **v0.x**, the canonical contract source is the documentation in `docs/`.
- When schemas are introduced, docs must remain aligned with schema files in this package.

## Forward compatibility expectations

Consumers MUST:
- tolerate unknown optional fields
- ignore unknown event types unless explicitly subscribed/handled
- deduplicate by `event_id` where needed

Producers MUST:
- include `schema_version` on events
- avoid breaking changes without a major version bump

## Suggested artifact naming

When adding schemas, prefer versioned file names:

- `schemas/event-envelope.v1.json`
- `schemas/dispatch.incident.created.v1.json`
- `schemas/system.site.decode_rate.updated.v1.json`
