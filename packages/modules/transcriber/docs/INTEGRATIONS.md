# Integrations: transcriber -> emberlog-api

Type: Operational Integration Note  
Normative references: `/docs/API_CONTRACT_v0.1.md`, `/docs/EVENT_MODEL_v0.2.md`, `/docs/DEPLOYMENT_MODEL_v0.1.md`  
Last verified: 2026-03-06

## Scope

This document describes current implementation behavior in this module.

- In scope: outbound REST integration used by `ApiSink`
- Out of scope: API server implementation details

## Current Active Integration

Base URL source:

- `EMBERLOG_API_BASE_URL` from transcriber settings (`api_base_url`)
- Default: `http://localhost:8080/api/v1`

Endpoint currently used by code:

- Method: `POST`
- Path: `/incidents/`
- Full URL: `{api_base_url}/incidents/`
- Caller: `emberlog/io/api_sink.py` via `emberlog/api/client.py`

Payload fields posted:

- `dispatched_at`
- `special_call`
- `units`
- `channel`
- `incident_type`
- `address`
- `source_audio`
- `original_text`
- `transcript`
- `parsed`

## Current Sink Behavior

In default worker flow, sinks are composed local-first:

1. JSON file sink
2. Ledger sink
3. API sink

`CompositeSink` runs all sinks and captures sink-level failures.

## Canon Alignment Note

Root canon defines module ingest via `/api/v1/ingest/events` using canonical event envelopes.
This module is intentionally still on `/incidents` for current production behavior.
Migration to canonical ingest is a future phase.
