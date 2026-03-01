# Emberlog Deployment Model

**Version:** 0.1\
**Status:** Foundational Runtime Topology Definition

------------------------------------------------------------------------

## 1. Purpose

This document defines the intended runtime deployment model of the
Emberlog platform.

Emberlog is a **distributed platform**.\
The monorepo organizes source code. It does not imply a monolithic
runtime.

Each major component is designed to run independently, potentially on
separate hardware systems.

------------------------------------------------------------------------

## 2. Core Runtime Components

### 2.1 Trunk Recorder

-   Typically runs on dedicated hardware or VM
-   Requires SDR hardware access
-   Publishes activity via MQTT (or similar)
-   Owns raw audio capture

Trunk Recorder is external to Emberlog but is a primary data source.

------------------------------------------------------------------------

### 2.2 Emberlog Transcriber (Module)

-   GPU-bound workload
-   Consumes audio artifacts or call references
-   Emits `dispatch.*` events to Emberlog API
-   May run on bare metal or GPU-enabled container runtime

The transcriber is logically a module and must communicate via API or
message queue boundaries.

It must not assume shared disk access to the API or Web services.

------------------------------------------------------------------------

### 2.3 Emberlog API (Hub)

-   Stateless service (container/pod friendly)
-   Receives events from:
    -   Trunk Recorder (via MQTT or adapter)
    -   Transcriber modules
-   Persists canonical events
-   Publishes REST and SSE endpoints
-   Enforces `EVENT_MODEL.md` and `API_CONTRACT.md`

The API is the single source of truth.

------------------------------------------------------------------------

### 2.4 Emberlog Web

-   Stateless frontend
-   Connects only to Emberlog API
-   Uses REST for history
-   Uses SSE for live updates
-   Must not connect directly to Transcriber or Trunk Recorder

------------------------------------------------------------------------

## 3. Communication Topology

### Primary Data Flow

    Trunk Recorder → MQTT → Emberlog API
    Emberlog Transcriber → REST Ingest → Emberlog API
    Emberlog API → REST/SSE → Emberlog Web

All cross-component communication must occur over network boundaries.

No shared filesystem assumptions are permitted between services.

------------------------------------------------------------------------

## 4. Distributed-by-Design Rules

1.  Each component must run independently.
2.  Cross-component integration must occur via documented contracts.
3.  No runtime imports across service boundaries.
4.  No shared storage assumptions.
5.  No hidden backchannels.

This ensures: - Horizontal scalability - Hardware specialization - Clear
failure domains - Future multi-host deployment flexibility

------------------------------------------------------------------------

## 5. Deployment Shapes

### 5.1 Development Mode (All-in-One)

For local development only:

-   API + Web may run on same host
-   Transcriber may be stubbed or disabled
-   Mock event producers permitted

This mode is for development convenience only.

------------------------------------------------------------------------

### 5.2 Distributed Homelab Mode (Recommended)

Example:

-   Host A: Trunk Recorder (SDR hardware)
-   Host B: Transcriber (GPU)
-   Host C: Kubernetes cluster (API + Web)
-   Network-based communication only

This reflects the intended production topology.

------------------------------------------------------------------------

## 6. Scaling Considerations

-   API should remain stateless and horizontally scalable.
-   Web should remain stateless and horizontally scalable.
-   Transcriber instances may scale independently based on GPU capacity.
-   Message ingestion should tolerate burst traffic.

------------------------------------------------------------------------

## 7. Future: Command Plane (v2+)

Future versions may introduce control capabilities:

-   Configuration management for Trunk Recorder
-   Service orchestration
-   Authentication and authorization

Command functionality must: - Be isolated from data ingestion paths -
Require authentication - Preserve auditability

------------------------------------------------------------------------

## 8. Security (Deferred)

Current v0.x deployments may run in trusted environments.

Future production deployments should consider:

-   Authenticated ingest endpoints
-   TLS between services
-   Role-based access control
-   Audit logging

Security must not alter canonical event schemas.

------------------------------------------------------------------------

## 9. Non-Goals

-   Monolithic single-process deployment
-   Tight coupling via shared libraries across services
-   Implicit local-only assumptions
-   Hard dependency on Kubernetes (platform must remain portable)

------------------------------------------------------------------------

# End of Deployment Model v0.1
