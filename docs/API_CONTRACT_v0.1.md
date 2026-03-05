# Emberlog API Contract

**Version:** 0.1\
**Status:** Foundational Transport & Integration Contract\
**Applies To:** emberlog-api (Hub), modules, and emberlog-web

------------------------------------------------------------------------

## 1. Purpose

This document defines the transport and integration rules for the
Emberlog platform.

It specifies:

-   REST API conventions
-   SSE (Server-Sent Events) conventions
-   Module ingest interface
-   Event consistency guarantees

All Emberlog components MUST conform to this contract.

------------------------------------------------------------------------

## 2. Core Principles

1.  The hub is the single source of truth.
2.  All published data conforms to the canonical Event Model.
3.  REST and SSE use identical event envelopes.
4.  No module writes directly to platform storage.
5.  Backward compatibility is preserved once 1.0 is declared.

------------------------------------------------------------------------

# 3. REST API Conventions

All REST responses returning event data MUST use the canonical event
envelope defined in EVENT_MODEL.md.

## 3.1 Base Versioning

The API is versioned at the path level:

    /api/v1/

Breaking API changes require a new version path (e.g., `/api/v2/`).

------------------------------------------------------------------------

## 3.2 Event Query Endpoints

### GET /api/v1/events

Returns canonical events with filtering options.

Query parameters may include:

-   `domain` (traffic, system, dispatch)
-   `event_type`
-   `system`
-   `from` (ISO timestamp)
-   `to` (ISO timestamp)
-   `limit`
-   `offset`

Response:

``` json
{
  "data": [ { event_envelope }, ... ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 1234
  }
}
```

------------------------------------------------------------------------

## 3.3 Domain-Specific Endpoints

The hub MAY provide optimized domain views for convenience.

Examples:

-   `GET /api/v1/traffic/calls`
-   `GET /api/v1/system/sites`
-   `GET /api/v1/dispatch/incidents`

These endpoints MUST still return canonical event envelopes or clearly
documented domain projections derived from them.

Domain projections MUST NOT invent incompatible schemas.

------------------------------------------------------------------------

# 4. SSE (Server-Sent Events) Conventions

SSE provides live event streaming.

## 4.1 Base Endpoint

    GET /api/v1/sse

Query parameters:

-   `domain`
-   `event_type` (repeatable; OR match when provided multiple times)
-   `system`

If no filter is provided, all events may be streamed.
When multiple filter categories are provided (`domain`, `event_type`, `system`), they are combined with AND semantics.

------------------------------------------------------------------------

## 4.2 SSE Event Format

Each SSE message MUST contain:

    event: <event_type>
    data: <JSON canonical event envelope>

Example:

    event: traffic.call.started
    data: { ...canonical envelope... }

Transport format MUST NOT diverge from REST envelope format.

------------------------------------------------------------------------

## 4.3 Reconnection Behavior

Clients:

-   MUST handle reconnect automatically.
-   MUST deduplicate using `event_id`.
-   SHOULD use `Last-Event-ID` when supported.

The platform does NOT guarantee replay unless explicitly implemented
later.

------------------------------------------------------------------------

# 5. Module Ingest Interface

Modules integrate with the hub via an ingest API.

## 5.1 Ingest Endpoint

    POST /api/v1/ingest/events

Payload:

``` json
{
  "events": [ { canonical_event_envelope }, ... ]
}
```

Rules:

-   Each event MUST validate against EVENT_MODEL.
-   Invalid events MUST be rejected with validation errors.
-   Partial success MAY be supported but must be clearly reported.

------------------------------------------------------------------------

## 5.2 Idempotency

The hub MUST treat `event_id` as idempotent.

Duplicate `event_id` submissions MUST NOT create duplicate stored
events.

------------------------------------------------------------------------

# 6. Error Handling

All API errors MUST use consistent JSON structure:

``` json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

Validation errors SHOULD clearly indicate schema violations.

------------------------------------------------------------------------

# 7. Authentication (Deferred)

Authentication is not required in v0.x for local deployments.

Future versions MAY introduce:

-   Token-based ingest authentication
-   Role-based access for command endpoints
-   Audit logging

These will not alter canonical event schemas.

------------------------------------------------------------------------

# 8. Backward Compatibility Policy

Pre-1.0:

-   Breaking changes are allowed but discouraged.
-   Contracts should stabilize before 1.0.

Post-1.0:

-   Event envelope changes require major version bumps.
-   Deprecated fields MUST be supported for at least one minor version
    cycle.

------------------------------------------------------------------------

# 9. Design Guardrails

-   REST and SSE must remain symmetrical.
-   Transport format must remain thin; business logic belongs in modules
    or hub core.
-   Domain projections must be derived from canonical events.
-   The hub enforces structure, not interpretation.

------------------------------------------------------------------------

# End of API Contract v0.1
