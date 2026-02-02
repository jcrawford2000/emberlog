# Integrations: emberlog -> emberlog-api

This document describes the integration contract observable from this repo (`emberlog`) for calls into `emberlog-api`.

## Scope

- In scope: outbound REST integration used by `ApiSink`.
- Out of scope: API server implementation details (owned by `emberlog-api`).
- SSE note: SSE is owned and implemented by `emberlog-api`; this repo does not implement SSE.

## 1) Required REST Endpoints Used by `ApiSink`

Base URL source:
- `settings.api_base_url` from `emberlog/config/config.py`
- Default: `http://localhost:8080/api/v1`

### Endpoint A: Create Incident
- Method: `POST`
- Path: `/incidents/`
- Full URL: `{api_base_url}/incidents/`
- Caller: `emberlog/io/api_sink.py` via `EmberlogAPIClient.create_incident(...)`

Payload fields sent (JSON):
- `dispatched_at` (datetime)
- `special_call` (bool)
- `units` (list[str] | null)
- `channel` (str | null)
- `incident_type` (str | null)
- `address` (str | null)
- `source_audio` (str)
- `original_text` (str | null)
- `transcript` (str | null)
- `parsed` (object | null; currently `{}` from `ApiSink`)

Headers used by client:
- `Accept: application/json`
- `Content-Type: application/json`
- `X-API-Key: <value>` (currently instantiated as empty string in `ApiSink`)

## 2) Expected Response and Error Handling Expectations

### Success response (as expected by client model)
- JSON object containing:
  - `id` (int)
  - `created_at` (ISO datetime string)
  - `links.self._url` (string)

Client behavior:
- `r.raise_for_status()` is called; non-2xx is treated as error.
- `created_at` string is parsed to datetime.
- Response is validated into `NewIncident` model.

### Error handling in this repo
- API HTTP errors are logged in `emberlog/api/client.py` and re-raised.
- Worker catches exceptions, increments attempts, and retries with backoff until max attempts.
- Current sink chain order is API -> JSON -> Ledger, so API failure can prevent later sinks in the same attempt.

## 3) SSE Ownership Note

- SSE endpoints and stream semantics are owned by `emberlog-api`.
- `emberlog` does not open SSE connections or publish SSE directly.
- `emberlog` contributes data by POSTing incidents; downstream SSE fan-out is external.

## 4) Needs Verification (Fill-ins Required)

The following details are not fully discoverable from this repo and should be confirmed in `emberlog-api`:

1. Exact success status code(s) for `POST /incidents/` (e.g., `201` vs `200`).
2. Canonical error response schema (validation errors, auth errors, server errors).
3. Required authentication policy for `X-API-Key` (required/optional, key format, rotation).
4. Idempotency/duplicate handling contract for repeated incident POSTs.
5. Rate limiting behavior and retry guidance (`429`, `Retry-After`, backoff recommendations).
6. Final SSE event schema(s) and event names emitted after incident creation.
7. Versioning policy for REST paths/payloads and backward compatibility guarantees.
