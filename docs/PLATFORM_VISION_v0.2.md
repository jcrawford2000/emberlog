# Emberlog Platform Vision

**Version:** 0.2 (Foundational Draft -- Revised)\
**Status:** Pre-1.0 Platform Definition

------------------------------------------------------------------------

## 1. What Emberlog Is

Emberlog is an open-source platform for Trunk Recorder ecosystems.

It provides:

-   Real-time traffic activity monitoring\
-   System health telemetry (including decode rates and site health)\
-   Structured intelligence modules (e.g., dispatch transcription)\
-   A modular web console\
-   A future control plane for configuration and management

Emberlog is not just a dashboard.\
It is not just a transcript viewer.\
It is not just a web frontend for Trunk Recorder.

Emberlog is a **contract-first, hub-centric platform** that transforms
raw trunked radio activity into structured, observable, and extensible
intelligence.

------------------------------------------------------------------------

## 2. Core Philosophy

### 2.1 Contract-First

All integration within Emberlog happens through stable, versioned event
contracts.

Modules do not write directly to core storage.\
Modules do not bypass the hub.\
Modules emit canonical events into the platform.

The hub enforces schemas and publishes them consistently.

Contracts are the constitution of Emberlog.

------------------------------------------------------------------------

### 2.2 Live-First

Emberlog prioritizes real-time visibility.

The platform is designed to answer:

-   What is happening right now?
-   What just happened?
-   What is the current health and activity of my monitoring systems?

Historical views are important and will be supported, but live activity
is the primary design axis.

------------------------------------------------------------------------

### 2.3 Hub-Centric Architecture

The core of Emberlog is the Hub:

-   Receives events from modules and external systems
-   Validates and normalizes them
-   Persists structured data
-   Publishes live streams (SSE)
-   Serves historical queries (REST)

The hub is the single source of truth.

------------------------------------------------------------------------

### 2.4 Modular by Design

Emberlog is built as a platform, not a monolithic app.

There are three architectural layers:

1.  **Core Platform**
    -   emberlog-api (Hub)
    -   emberlog-web (UI Shell)
2.  **Modules**
    -   Built-in modules (shipped with the platform)
    -   Third-party modules (separate repositories)
3.  **Runtime Ecosystem**
    -   Trunk Recorder
    -   MQTT
    -   External audio sources
    -   Notification systems

Region-specific logic belongs in modules.\
Generic platform behavior belongs in the core.

------------------------------------------------------------------------

### 2.5 Domain Separation

Emberlog distinguishes between different conceptual domains:

-   Traffic (live trunkgroup activity)
-   Systems (site health, decode rates)
-   Dispatch Intelligence (structured incident data)
-   Scanner (audio playback)
-   Command (future control plane)

These domains are independent but interoperable.

The UI reflects this separation.

------------------------------------------------------------------------

## 3. Platform Scope (v1 Direction)

### 3.1 Core Platform Capabilities

-   Canonical event model
-   Ingest API for modules
-   REST API for historical queries
-   SSE for live updates
-   Modular web interface
-   System monitoring console
-   Traffic monitoring console

------------------------------------------------------------------------

### 3.2 Built-In Modules

The platform will ship with selected built-in modules.

Example: - **emberlog-transcriber** (Whisper-based transcription
engine) - Converts radio audio into structured dispatch events - May
include region-specific adapters (e.g., Phoenix Fire)

Built-in modules serve as: - Reference implementations - Immediate value
for users - Examples for third-party developers

------------------------------------------------------------------------

### 3.3 Third-Party Modules

Third-party modules:

-   Live in independent repositories
-   Integrate through the canonical ingest interface
-   Must conform to Emberlog event contracts
-   Run as independent services

The platform does not require modules to be compiled into the core.

Integration is contract-based, not code-linked.

------------------------------------------------------------------------

## 4. Non-Goals (v1)

The following are explicitly out of scope for the initial platform
definition:

-   Multi-tenant SaaS architecture
-   Enterprise-grade RBAC
-   Complex analytics dashboards
-   Machine learning pipelines
-   Full audio streaming and storage subsystem redesign
-   Distributed cluster orchestration features

These may be explored in future phases but are not foundational to the
platform definition.

------------------------------------------------------------------------

## 5. Long-Term Vision (5-Year Horizon)

Emberlog aims to become:

-   The preferred companion platform for Trunk Recorder users
-   A modular intelligence layer over trunked radio systems
-   A community-extensible ecosystem of adapters and modules
-   A unified console for monitoring, intelligence, and eventually
    control

Over time, Emberlog may support:

-   Audio streaming integration
-   Advanced rule-based notifications
-   Historical analytics
-   Control and configuration of Trunk Recorder
-   Enhanced module capability discovery

But the platform will evolve incrementally, anchored by stable contracts
and disciplined architecture.

------------------------------------------------------------------------

## 6. Governance & Stability Philosophy

Emberlog follows these guiding principles:

-   Contracts are versioned.
-   Breaking changes are intentional.
-   Modules must integrate through the hub.
-   The platform prioritizes clarity over feature velocity.
-   Architectural integrity is favored over short-term convenience.

Pre-1.0 releases may evolve rapidly.\
Once 1.0 is declared, backward compatibility becomes a formal
commitment.

------------------------------------------------------------------------

## 7. One-Sentence Definition

Emberlog is an open-source, contract-first platform that transforms
Trunk Recorder data into real-time, modular intelligence and monitoring
capabilities.
