# ME2 Architecture

> M (Meitech) + E2 (Eduardo) = MES with a mirrored S. **"Keep Moving"**

## 1. Overview

ME2 is Meitech Industrial's MES (Manufacturing Execution System) for real-time production monitoring, OEE calculation, and maintenance alerting. It connects PLCs on the factory floor to a web dashboard accessible from any device.

The system evolves through two stages:

- **POC (current):** Single-site, 1 Schneider PLC via VPN, direct Modbus TCP connection.
- **Target SaaS:** Multi-tenant cloud platform with MQTT edge communication, supporting 500+ machines across multiple client sites worldwide.

---

## 2. POC Architecture (Current)

### Components

| Component | Technology | Responsibility |
|-----------|-----------|----------------|
| PLC | Schneider M241 (Modbus TCP) | Runs GVL_ME2 + FB_ME2Status, exposes holding registers |
| VPN Tunnel | Site-to-site VPN | Secure transport between factory and Meitech server |
| Collector | Python 3.11 (asyncio + pymodbus) | Polls PLC, detects changes, buffers locally, syncs to API |
| SQLite Buffer | SQLite (local file) | Offline buffer — survives network outages |
| API | FastAPI + Uvicorn (async) | REST + WebSocket endpoints, business logic, OEE calculation |
| Database | PostgreSQL 16 (Docker) | Persistent storage, time-series partitioned tables |
| Dashboard | React 19 + Vite 8 | Real-time monitor, OEE analytics, alerts, reports |
| Reverse Proxy | Nginx | SSL termination, static file serving, WebSocket upgrade |

### Data Flow

```
 FACTORY FLOOR                          MEITECH SERVER
 =============                          ==============

 +------------------+
 | Schneider M241   |
 | GVL_ME2 registers|
 +--------+---------+
          |
          | Modbus TCP (port 502)
          | over site-to-site VPN
          |
 +--------v---------+     on change     +------------------+
 | ME2 Collector     +------ sync ------>| FastAPI          |
 | (Python asyncio)  |                   | /api/v1/...      |
 |                   |                   | /ws/live          |
 | pymodbus client   |                   +--------+---------+
 | poll every 1s     |                            |
 |                   |                            | SQLAlchemy async
 | +---------------+ |                            | (asyncpg)
 | | SQLite buffer | |                            |
 | | (offline safe)| |                   +--------v---------+
 | +---------------+ |                   | PostgreSQL 16    |
 +-------------------+                   | (Docker)         |
                                         |                  |
                                         | - production_events
                                         | - status_events  |
                                         | - oee_snapshots  |
                                         | - alerts         |
                                         +--------+---------+
                                                  |
                                         +--------v---------+
                                         | React Dashboard  |
                                         | (Vite + MD3)     |
                                         |                  |
                                         | WebSocket: live  |
                                         | REST: historical |
                                         +------------------+
```

### Collector Detail

The collector runs as a standalone Python process (or Docker container alongside the API). Its main loop:

1. Load `config/equipment.json` (reload every 15 min).
2. For each active equipment entry, create the appropriate driver (`ModbusDriver`, `Snap7Driver`, or `OpcUaDriver`) via the driver factory.
3. Poll all variables at the configured `poll_interval_s` (default 1s).
4. `DataProcessor` compares each reading against the previous value. Only **changes** are persisted (trigger-on-change principle from E2 Collector).
5. Changed values are written to the local SQLite buffer first, then synced to the FastAPI API via HTTP POST.
6. `AlertEngine` checks if `word_status` has left the uptime code (18). If downtime exceeds L1/L2 thresholds, email alerts fire via the configured notification groups.

### Key Design Decisions (POC)

- **Trigger on change, not time-series sampling.** We store events (part produced, status changed), not periodic snapshots. This keeps the database small and queries fast.
- **SQLite as offline buffer.** If the VPN drops or the API is unreachable, readings accumulate in SQLite. When connectivity returns, the collector syncs the backlog. No data loss.
- **Driver abstraction.** `BaseDriver` defines `connect()`, `read_variables()`, `disconnect()`. Each PLC family has one driver implementation. Adding a new PLC = new driver, no changes to collector logic.
- **Equipment JSON, not database config.** For the POC, equipment config lives in a JSON file. Adding a machine = edit JSON + restart. No migration, no admin panel.
- **Word overflow correction.** Schneider 16-bit signed registers wrap at 32767. The `DataProcessor` applies correction automatically when `overflow_fix: true` is set in the variable config.

---

## 3. Target SaaS Architecture

### Components Added/Changed

| Component | Technology | Change from POC |
|-----------|-----------|-----------------|
| Edge Collector | Same Python collector | Publishes via MQTT instead of HTTP POST |
| MQTT Broker | Mosquitto / EMQX (TLS) | New — central message bus |
| Ingestion Service | Python consumer | New — subscribes to MQTT topics, writes to PostgreSQL |
| PostgreSQL | Managed (cloud) | Moves from local Docker to managed instance |
| Auth | JWT + tenant isolation | Multi-tenant RBAC |
| Dashboard | Same React app | Tenant selector, multi-site views |

### Data Flow (Target)

```
 SITE A (Factory)                CLOUD                        CLIENTS
 ================        ======================         ================

 +-------------+         +--------------------+
 | PLC 1       |         |  MQTT Broker       |
 | PLC 2       |         |  (TLS, port 8883)  |
 | PLC N       |         |                    |
 +------+------+         |  Topics:           |
        |                |  me2/{tenant}/     |
 +------v------+  MQTT   |    {serial}/data   |
 | Edge        +-------->|    {serial}/status  |
 | Collector   |  TLS    |    {serial}/alert   |
 | + SQLite    |         +--------+-----------+
 +-------------+                  |
                                  | subscribe
 SITE B (Factory)        +--------v-----------+
 ================        | Ingestion Service  |
                         | (Python consumer)  |
 +-------------+         +--------+-----------+
 | PLC 1       |                  |
 +------+------+         +--------v-----------+
        |                | PostgreSQL         |
 +------v------+  MQTT   | (managed, cloud)   |
 | Edge        +-------->| partitioned tables |
 | Collector   |  TLS    +--------+-----------+
 | + SQLite    |                  |
 +-------------+         +--------v-----------+         +--------------+
                         | FastAPI            |         | React        |
                         | (multi-tenant)     +-------->| Dashboard    |
                         | /api/v1/...        |  HTTPS  | (per-tenant) |
                         +--------------------+         +--------------+
```

### MQTT Topic Structure

```
me2/{tenant_id}/{serial_number}/data      — production + cycle time
me2/{tenant_id}/{serial_number}/status    — word_status changes
me2/{tenant_id}/{serial_number}/alert     — downtime alerts from edge
me2/{tenant_id}/{serial_number}/heartbeat — collector alive signal (every 30s)
```

### Multi-Tenant Isolation

- Every database query includes `tenant_id` in the WHERE clause.
- JWT tokens carry `tenant_id` and `role`. Middleware enforces row-level access.
- MQTT credentials are per-tenant. Each edge collector authenticates with tenant-scoped credentials.
- `meitech_admin` and `meitech_support` roles can access all tenants (Meitech internal).

### Key Design Decisions (SaaS)

- **MQTT over TLS, not HTTP polling.** Edge collectors push events via MQTT, which handles intermittent connectivity natively. QoS 1 ensures at-least-once delivery. SQLite buffer remains as secondary safety net.
- **Edge intelligence stays.** Trigger-on-change, overflow correction, and alert detection all run at the edge. The cloud receives only meaningful events, not raw register dumps.
- **Managed PostgreSQL.** Time-series partitioning (by month) scales to millions of events. No need for a dedicated time-series database at this scale.
- **No Supabase, no Firebase.** The entire stack is self-hosted or managed PostgreSQL. Auth is JWT via FastAPI. Realtime is WebSocket via FastAPI's ConnectionManager. This keeps costs predictable and avoids vendor lock-in.

---

## 4. Security

| Layer | Mechanism |
|-------|-----------|
| PLC to Collector (POC) | Site-to-site VPN |
| PLC to Collector (SaaS) | Local network (collector on-site) |
| Collector to Cloud (SaaS) | MQTT over TLS (port 8883), client certificates |
| API | JWT Bearer tokens, HTTPS (Nginx SSL termination) |
| Database | Network-level isolation, password auth, no public exposure |
| Dashboard | HTTPS only, JWT stored in memory (not localStorage) |

---

## 5. Deployment

### POC (Docker Compose)

```yaml
services:
  me2-postgres:    # PostgreSQL 16 with uuid-ossp extension
  me2-api:         # FastAPI + Uvicorn + Collector
  me2-nginx:       # Reverse proxy + SSL
```

All three containers run on Meitech's own server. The collector runs as part of the API container in the POC (separate process, same image). In production, it will be a separate container.

### Target (Per-Site Edge + Central Cloud)

- **Edge:** Single Docker container per site running the collector + SQLite buffer.
- **Cloud:** Kubernetes or Docker Compose with MQTT broker, ingestion service, API, PostgreSQL, Nginx.

---

## 6. Technology Stack Summary

| Layer | Technology |
|-------|-----------|
| PLC Programming | Schneider SoMachine/EcoStruxure (ST), Siemens TIA Portal (ST/LAD) |
| PLC Communication | pymodbus (Modbus TCP), python-snap7 (S7comm), asyncua (OPC-UA) |
| Collector | Python 3.11, asyncio, SQLite |
| API Framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Auth | python-jose (JWT) |
| Database | PostgreSQL 16 |
| Frontend | React 19, Vite 8, Zustand, axios, Material Design 3 |
| Reverse Proxy | Nginx |
| Containerization | Docker + Docker Compose |
| MQTT (future) | Mosquitto or EMQX |
| ML (future) | pandas, numpy, scikit-learn |
