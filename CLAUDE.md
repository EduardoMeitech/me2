# CLAUDE.md — ME2

This file provides guidance to Claude Code when working with the ME2 codebase.

## Project Overview

**ME2** is Meitech Industrial's proprietary MES (Manufacturing Execution System). The name
comes from M (Meitech) + E2 (Eduardo² — the original E2 project at Nidec) ≈ MES with a
mirrored S. Slogan: **"Keep Moving"** — aligned with Meitech's "Sempre em Movimento".

Meitech manufactures machines for the chicken processing industry. ME2 connects those
machines to managers in real time, collects production data, calculates OEE, and triggers
maintenance alerts. The long-term goal is a SaaS platform for 500+ machines across multiple
client sites worldwide. The current stage is a **POC with 1 Schneider equipment via VPN**.

## Commands

### Quick start (local dev — Windows)

```bash
# 1. Start PostgreSQL (must be running on port 5432)
# 2. Run migrations
cd api && PYTHONPATH=.. DATABASE_URL="postgresql+asyncpg://me2:me2dev@localhost:5432/me2" python -m alembic upgrade head

# 3. Seed demo data
cd .. && python scripts/seed_demo.py

# 4. Start API (from project root)
PYTHONPATH=. python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --log-level info

# 5. Start frontend (separate terminal)
cd web && npm run dev

# 6. Start PLC simulator (separate terminal — generates fake data)
python scripts/simulator.py
```

### Docker (production)

- `docker compose up -d` — start all services (PostgreSQL + API + Nginx)
- `docker compose --profile dev up` — start with Adminer (DB UI on :8080)

### Individual commands

- `cd api && PYTHONPATH=.. python -m alembic upgrade head` — run pending migrations
- `cd api && PYTHONPATH=.. python -m alembic revision --autogenerate -m "description"` — create migration
- `cd api && pytest` — run API tests
- `cd web && npm run dev` — React frontend dev server (port 3000, proxies API)
- `cd web && npm run build` — production build
- `cd web && npm run lint` — ESLint
- `python scripts/simulator.py` — PLC simulator (writes to collector SQLite)
- `python scripts/seed_demo.py` — seed demo data into PostgreSQL

### Default credentials

- **Login:** `eduardo.rosa@meitech.com.br` / `me2admin`
- **PostgreSQL:** user `me2`, password `me2dev`, database `me2`

No test framework for the frontend yet — backend uses pytest + httpx.

### Windows-specific notes

- Python asyncpg requires `WindowsSelectorEventLoopPolicy` — already set in `api/core/config.py`
- passlib is incompatible with bcrypt 5.0 — we use `bcrypt` directly in `api/core/auth.py`
- pydantic-settings uses `extra="ignore"` to skip `VITE_*` vars from shared `.env`
- `.env` file lives at project root, `config.py` searches CWD + parent + project root

## Architecture

Current stage (POC):

```
Schneider PLC ──(Modbus TCP / VPN)──► ME2 Collector (Python)
       or                                    │
PLC Simulator ──(scripts/simulator.py)───────┘
                                        │
                                   SQLite (local buffer)
                                        │ SyncService (5s)
                                   FastAPI ──► WebSocket broadcast ──► React Dashboard
                                        │
                                   PostgreSQL
                                        │
                                   OEE Calculator (5min) ──► oee_snapshots
```

**Data pipeline (verified working):**
1. Collector (or Simulator) writes events to **SQLite** (trigger-on-change)
2. **SyncService** (background task in FastAPI) reads unsynced rows every 5s
3. Maps `serial_number` → `equipment_id`, inserts into **PostgreSQL**
4. Broadcasts each event via **WebSocket** `/ws/live` to connected clients
5. **OEE Calculator** (background task) recalculates hourly OEE every 5 minutes
6. Frontend fetches via REST API + receives live updates via WebSocket

Target (SaaS): collector publishes via MQTT over TLS → central PostgreSQL → multi-tenant
dashboard. SQLite stays as the offline buffer at the edge. See `docs/architecture.md`.

**Backend:** Python 3.11, FastAPI + Uvicorn, SQLAlchemy 2.0 (async), Alembic migrations, python-jose JWT auth, APScheduler, pandas/numpy/scikit-learn for ML (future).

**Frontend:** React 19 + Vite 8, plain JSX, Material Design 3 (custom tokens from `web/src/styles/theme.js`), Zustand for state, axios for HTTP, native WebSocket hook `useWebSocket.js` for live data.

**Infrastructure:** Docker Compose on Meitech's own server. Three containers: `me2-postgres` (PostgreSQL 16), `me2-api` (FastAPI), `me2-nginx` (reverse proxy + SSL). No Supabase, no external managed services.

**CRITICAL — Auth:** JWT via FastAPI (`python-jose`). No Supabase Auth. Tokens issued by `POST /api/v1/auth/login`, included as `Authorization: Bearer <token>` in all subsequent requests.

**CRITICAL — Realtime:** WebSocket at `/ws/live`. FastAPI manages connections in a `ConnectionManager`. Never use Supabase Realtime — it's not part of this stack.

**CRITICAL — Database:** PostgreSQL 16 via Docker. Use `asyncpg` driver (`postgresql+asyncpg://...`). All queries via SQLAlchemy async session. Migrations via Alembic — never modify schema manually.

**CRITICAL — Equipment ID:** The unique identifier for any machine is `serial_number` (the physical plate on the machine, e.g. `MEI-2024-0042`). There is NO SAP code — Meitech and most clients don't use SAP. Never use `station_sap` or similar names. The GVL variable is `sSerialNumber`, the JSON field is `serial_number`, the DB column is `serial_number`.

## Directory Layout

```
me2/
├── api/                          # Backend Python
│   ├── collector/
│   │   ├── drivers/
│   │   │   ├── base.py           # BaseDriver ABC — interface comum
│   │   │   ├── snap7_driver.py   # Siemens S7 via python-snap7
│   │   │   ├── modbus_driver.py  # Schneider via pymodbus
│   │   │   ├── opcua_driver.py   # Toradex/CODESYS + M580 via asyncua
│   │   │   └── factory.py        # create_driver(config) — registry
│   │   ├── config_loader.py      # Lê equipment.json (local ou API)
│   │   ├── data_processor.py     # Detecta mudanças, corrige overflow, persiste
│   │   ├── alert_engine.py       # Timer de parada L1/L2, envia email
│   │   ├── sync_service.py       # SQLite → PostgreSQL sync + WebSocket broadcast
│   │   └── main.py               # Loop principal assíncrono
│   ├── core/
│   │   ├── database.py           # SQLAlchemy async engine + session
│   │   ├── models.py             # ORM models (PostgreSQL)
│   │   ├── schemas.py            # Pydantic schemas (request/response)
│   │   ├── config.py             # pydantic-settings — lê do .env
│   │   └── auth.py               # JWT — create_token, verify_token, get_current_user
│   ├── routers/
│   │   ├── auth.py               # POST /api/v1/auth/login
│   │   ├── equipment.py          # GET /api/v1/equipment, /equipment/{id}/live
│   │   ├── oee.py                # GET /api/v1/equipment/{id}/oee
│   │   ├── production.py         # GET /api/v1/equipment/{id}/production
│   │   ├── alerts.py             # GET /api/v1/alerts/active, POST /alerts/{id}/ack
│   │   ├── reports.py            # GET /api/v1/reports/shift, /reports/daily
│   │   └── live.py               # WS /ws/live
│   ├── services/
│   │   └── oee_calculator.py     # OEE calculation (hourly + shift, runs every 5min)
│   ├── ml/                       # ML Engine (Fase 2 — não implementar na POC)
│   ├── db/
│   │   └── init.sql              # Extensões PostgreSQL (uuid-ossp, etc.)
│   ├── alembic/                  # Migrations
│   ├── tests/
│   ├── main.py                   # FastAPI app entry point
│   ├── Dockerfile
│   └── requirements.txt
├── web/                          # Frontend React
│   ├── src/
│   │   ├── styles/theme.js       # MD3 tokens Meitech (cores, tipografia, shape)
│   │   ├── components/
│   │   │   ├── ME2Logo.jsx       # Animated logo (2 flips to S → ME2/MES), Baloo 2 font
│   │   │   ├── MachineCard.jsx   # Card status + OEE badge + sparkline
│   │   │   ├── OEEGauge.jsx      # Gauge circular com 3 arcos (configurable size/compact)
│   │   │   ├── StatusTimeline.jsx# Barra de estados colorida (tipo Gantt)
│   │   │   ├── StatusPareto.jsx  # Horizontal bars — accumulated status distribution
│   │   │   ├── ProductionBar.jsx # Barras por hora + linha de meta
│   │   │   ├── AlertBanner.jsx   # Banner persistente para parada ativa
│   │   │   ├── ShiftSelector.jsx # Toggle T1/T2/T3
│   │   │   ├── Button.jsx        # MD3 Button (filled/outlined/text/tonal)
│   │   │   ├── Card.jsx          # MD3 Card
│   │   │   └── Layout.jsx        # Nav Rail (Meitech blue) + SpinCircle footer
│   │   ├── views/
│   │   │   ├── LiveMonitor.jsx   # Grid de máquinas em tempo real
│   │   │   ├── OEEAnalytics.jsx  # OEE dashboard (E2-inspired layout)
│   │   │   ├── Alerts.jsx        # Alertas ativos e histórico
│   │   │   └── Reports.jsx       # Relatório de turno / diário
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js   # Conexão WS com reconnect automático
│   │   │   └── useME2Data.js     # Hooks de dados (equipment, oee, production)
│   │   ├── lib/
│   │   │   ├── api.js            # axios instance com interceptor JWT
│   │   │   └── store.js          # Zustand — estado global
│   │   └── App.jsx               # Auth + routing + layout
│   ├── package.json
│   └── vite.config.js
├── config/
│   └── equipment.json            # Config de equipamentos (ver seção abaixo)
├── nginx/
│   ├── nginx.conf
│   └── certs/                    # SSL (não commitar)
├── docs/
│   ├── architecture.md
│   └── gvl-standard.md           # Padrão GVL_ME2 para o time de automação
├── scripts/
│   ├── seed_demo.py              # Dados sintéticos para demo
│   └── simulator.py              # PLC simulator (generates data without real PLC)
├── docker-compose.yml
├── .env.example                  # Copiar para .env — nunca commitar .env
└── CLAUDE.md
```

## Database Schema (PostgreSQL)

All tables have `id UUID DEFAULT gen_random_uuid() PRIMARY KEY` and `created_at TIMESTAMPTZ DEFAULT now()`.

| Table | Description | Key Columns |
|-------|-------------|-------------|
| `me2_tenants` | Client companies (future multi-tenant) | `id`, `name`, `country`, `timezone` |
| `me2_users` | System users | `id`, `tenant_id`, `name`, `email`, `role`, `password_hash` |
| `me2_plants` | Factories / sites | `id`, `tenant_id`, `name`, `location`, `timezone` |
| `me2_equipment` | Machines | `id`, `plant_id`, `serial_number`, `name`, `model`, `manufacturer`, `standard_cycle_time_s`, `active` |
| `me2_shifts` | Shift config per plant | `id`, `plant_id`, `name`, `start_time`, `end_time`, `days` |
| `me2_targets` | Production targets | `id`, `equipment_id`, `shift_id`, `target_parts_hour`, `valid_from` |
| `production_events` | Part produced (trigger on change) | `id`, `equipment_id`, `serial_number`, `product_no`, `parts_ok`, `cycle_time_s`, `ts` |
| `status_events` | Status change (trigger on change) | `id`, `equipment_id`, `serial_number`, `word_status`, `ts` |
| `process_events` | Process variables (booleans/analogs) | `id`, `equipment_id`, `variable_name`, `value`, `ts` |
| `connection_log` | PLC connect/disconnect events | `id`, `equipment_id`, `status`, `ts` |
| `oee_snapshots` | Calculated OEE per hour/shift/day | `id`, `equipment_id`, `shift_id`, `date`, `hour`, `availability_pct`, `performance_pct`, `quality_pct`, `oee_pct`, `parts_good`, `downtime_min`, `planned_min` |
| `alerts` | Active and historical alerts | `id`, `equipment_id`, `level`, `started_at`, `acknowledged_at`, `resolved_at` |
| `me2_quality` | Manual scrap/rework entries | `id`, `equipment_id`, `operator_id`, `quantity_scrap`, `quantity_rework`, `reason_code`, `ts` |

**IMPORTANT — Time-series tables** (`production_events`, `status_events`, `process_events`): Partition by `date_trunc('month', ts)` for scalability. Use `ts TIMESTAMPTZ NOT NULL` — never store timestamps as integers or strings.

**IMPORTANT — Never query without `equipment_id`** on time-series tables. Always filter by equipment + date range first, then by other conditions. Without this the query will scan the entire table.

## API Design

### Auth
```
POST /api/v1/auth/login       { email, password } → { access_token, token_type }
GET  /api/v1/auth/me          → current user profile
```

### Core endpoints
```
GET  /api/v1/equipment                              → all equipment for tenant
GET  /api/v1/equipment/{id}/live                     → latest reading per station
GET  /api/v1/equipment/{id}/oee?date=&shift=         → OEE for period
GET  /api/v1/equipment/{id}/production?date=&shift=  → parts per hour
GET  /api/v1/equipment/{id}/status?hours=48          → status timeline
POST /api/v1/quality                                 → scrap/rework entry
GET  /api/v1/alerts/active                           → active alerts now
POST /api/v1/alerts/{id}/acknowledge                 → ack alert
GET  /api/v1/reports/shift?equipment=&date=&shift=   → shift report
WS   /ws/live                                        → push on every status/production change
```

### Response envelope
```json
{ "success": true, "data": { ... }, "meta": { "ts": "...", "version": "1.0" } }
```

## Equipment JSON Config

Lives at `config/equipment.json`. The collector reads this file on startup and reloads every 15 minutes. Adding a new machine = edit JSON + restart collector. No code changes needed.

Key fields:
- `serial_number` — physical plate on the machine (e.g. `MEI-2024-0042`)
- `serial_number_source` — `"fixed"` (from JSON) or `"variable"` (read from GVL via Modbus/OPC-UA)
- `protocol` — `"s7"` | `"modbus"` | `"opcua"`
- `variables` — per-protocol address objects: `{"schneider": {...}, "codesys": {...}}`
- `alerts.uptime_status_code` — default `18` — value of `word_status` that means "producing"
- `alerts.downtime_l1_min` / `l2_min` — escalation thresholds
- `alerts.notify_l1` / `notify_l2` — keys into `notification_groups`

See `docs/equipment-json-schema.md` for the full schema with all fields.

## Domain Concepts

### WordStatus encoding (ME2 standard — compatible with E2 Collector)

Machine state is a bitmask WORD calculated by `FB_ME2Status` in the PLC:

| wWordStatus | State | Meaning |
|-------------|-------|---------|
| 18 | Uptime | Running — `bRunning(2) + bReady(16)` |
| 16 | Idle | Ready but not producing |
| 17 | Planned Stop | Scheduled break |
| 20 | Starving | No material upstream |
| 24 | Blocked | Downstream full |
| 32 | Failure | Alarm active |
| 64 | Setup | Changeover |
| 128 | Emergency | E-stop |

**Rule:** `word_status == 18` → machine producing. Any other value → downtime timer starts.
Some stations use `word_status != 18 AND word_status != 19` (Uptime variants) — check the equipment JSON.

### Word overflow correction

Schneider M-series Word variables are signed 16-bit. When `parts_ok` exceeds 32767 it wraps to negative. Always correct before storing:

```python
if parts_ok < 0:
    parts_ok = parts_ok + 32768
```

Configured per-variable in JSON: `"overflow_fix": true`. The `DataProcessor` applies this automatically.

### Trigger on change

Data is only persisted when a value actually changes (or at shift boundary). This is the core efficiency principle inherited from E2 Collector. `DataProcessor` holds `_last_parts_ok` and `_last_word_status` dicts keyed by `equipment_id`.

### Shifts (Meitech standard)

| ID | Name | Hours |
|----|------|-------|
| T100 | Turno 1 | 05:00 – 13:29 |
| T200 | Turno 2 | 13:30 – 21:59 |
| T300 | Turno 3 | 22:00 – 04:59 |

The 13h29 edge on T100 is intentional — preserve it exactly.

### OEE Calculation

```python
availability = (planned_min - downtime_min) / planned_min
performance  = parts_good / ((planned_min * 60) / target_cycle_time_s)
quality      = parts_good / (parts_good + parts_scrap)  # 1.0 if no scrap data
oee          = availability * performance * quality
```

`downtime_min` = sum of durations where `word_status != 18` (and `!= 19` where applicable).
`planned_min` = shift duration in minutes (defaults: T100=509, T200=509, T300=420).

### Alert Engine (2-level escalation)

L1 threshold → notifies operational team. L2 threshold → escalates to management. Both thresholds and notification groups come from `equipment.json`. Alert resets when `word_status` returns to `uptime_status_code`. State is held in `AlertEngine._downtime_start: dict[str, datetime]` and `._alert_sent: dict[str, int]`.

## Hardware Context

The ME2 collector handles 3 PLC families — one driver per family, same `BaseDriver` interface:

| Hardware | Protocol | Driver | Key detail |
|----------|----------|--------|------------|
| Siemens S7-300/400/1200 | S7comm (Profinet) | `Snap7Driver` | rack=0, slot=1 default |
| Schneider M221/M241/M251/M340 | Modbus TCP port 502 | `ModbusDriver` | unit_id=1, Holdings at %MW |
| Schneider M580 | Modbus TCP + OPC-UA | `ModbusDriver` (POC) | OPC-UA later |
| Toradex + CODESYS | OPC-UA port 4840 | `OpcUaDriver` | in development |

**Modbus float:** REALs occupy 2 consecutive holding registers, big-endian. Read 2 registers, `struct.pack('>HH', r[0], r[1])` → `struct.unpack('>f', ...)`.

**Modbus string:** Each holding register holds 2 ASCII chars. `sSerialNumber` (20 chars) = 10 registers starting at the configured address.

**OPC-UA NodeIDs** follow CODESYS convention: `ns=4;s=Application.GVL_ME2.<VariableName>`.

## GVL_ME2 Standard (PLC side)

The automation team (Gabriel, Paulo, Thalis) implements `GVL_ME2` and `FB_ME2Status` in every machine. The collector reads only from this GVL — it never touches the machine's own program logic.

Key variables:
- `sSerialNumber : STRING(20)` — machine serial number, written once at startup
- `sProductNo : STRING(20)` — current product, updated on changeover
- `dwPartsOK : DWORD` — good parts counter (cumulative within shift)
- `rCycleTime : REAL` — last completed cycle time in seconds
- `wWordStatus : WORD` — calculated by `FB_ME2Status` from the 7 status BOOLs
- `bProcess_01..08 : BOOL` — application-specific process variables

Full spec in `docs/gvl-standard.md`. The PLC code template is in `docs/plc-templates/`.

## Design System (Frontend)

Material Design 3 + Meitech visual identity. Token file: `web/src/styles/theme.js`.

**Brand assets** (in `web/public/brand/`):
- `logo-white.svg` — Meitech logo (white, for dark backgrounds like Nav Rail)
- `circle.svg` — animated Meitech spinning circle (used in footer/loading)
- `fonts/amina-regular.woff2` + `amina-bold.woff2` — Amina, Meitech official typeface

**Typography:** System font `'Segoe UI', Roboto, Arial` for body. `'Amina', sans-serif` (`typography.brandFamily`) for brand text (footer, headings). `'Baloo 2'` (Google Fonts, weight 800) for the ME2 logo. `@font-face` declarations in `web/src/styles/global.css`.

**ME2 Logo (`ME2Logo.jsx`):** The "2" in ME2 flips on the Y-axis (3D rotation) and swaps to "S" at the midpoint, creating a visual allusion ME2 ↔ MES. Font: Baloo 2 (rounded "2" resembles "S"). Animation only on Nav Rail; Login and Footer use `ME2LogoStatic`. Cycle: 3s as "2", flip 600ms, show "S" 800ms, flip back.

**Nav Rail:** 88px fixed sidebar in Meitech blue (`#0040f0`). White Meitech logo SVG + animated ME2Logo (34px, Baloo 2). Pill-shaped active indicators with `rgba(255,255,255,0.22)`. Same pattern as RADAR v9.

**Footer:** `ME2Footer` component with dual `SpinCircle` animation flanking static "ME2 / Keep Moving" (Amina + Baloo 2). Animation keyframe `meiSpin` for continuous rotation.

**OEE Analytics layout** (E2-inspired, responsive):
- Two aligned header cards (shared 30px title row + KPI row): Equipment info (left) + OEE Deployment with gauge circle (right). Cards stack vertically on narrow screens (`auto-fit, minmax(420px, 1fr)`).
- OEE gauge colors: green (Availability), blue (Performance), gray (Quality), value centered
- KPI values use `clamp(18px, 2vw, 26px)` for fluid sizing; flex-wrap for narrow layouts
- Grid rows 2-3 (fixed `330px + 100px`): Production chart (left) + Status Pareto spanning both rows (right) + Status Timeline (bottom-left, same width as Production)
- Production chart (Recharts): fills all shift hours with bars, UTC→BRT conversion (-3h), no Y-axis labels
- StatusTimeline labels use Recharts-matching formula `(i + 0.5) / N * 100%` for vertical hour alignment between the two charts
- Status Pareto shows ALL 8 status types (even 0%) to fill the card height
- All three data views (Production, StatusTimeline, StatusPareto) respond to shift filter via `GET /api/v1/equipment/{id}/status?date=&shift=`

**IMPORTANT — Shift time ranges (BRT → UTC):** Shifts are stored in local BRT but all DB queries and OEE calculations use UTC. The conversion is applied in `api/routers/equipment.py`, `api/routers/production.py`, and `api/services/oee_calculator.py`:
- T100: 05:00-13:29 BRT = 08:00-16:29 UTC
- T200: 13:30-21:59 BRT = 16:30-00:59 UTC  
- T300: 22:00-04:59 BRT = 01:00-07:59 UTC (crosses midnight)

**IMPORTANT — OEE Calculator timezone:** `SHIFT_DEFS` in `oee_calculator.py` uses `start_utc`/`end_utc` fields (not local time). The `run_periodic` recalculates ALL 24 hours of the current day every cycle to ensure snapshots exist for past hours.

**IMPORTANT — Production hours UTC→BRT:** The frontend `ProductionBar` converts API hour data from UTC to BRT (`UTC_OFFSET = -3`) before mapping to shift hours. The `OEEAnalytics` aggregation recalculates OEE from raw totals (E2 formula) instead of averaging percentages.

**Colors:**
- Primary: `#0066CC`
- Meitech brand: `#0040f0` (Nav Rail, logo circle, buttons)
- Error: `#BA1A1A` (critical stop)
- Warning: `#F57C00` (attention / setup)
- Success: `#388E3C` (uptime / running)
- Background: `#F0F2F8`

**Status → color mapping:**

| WordStatus | Color token | Hex |
|------------|-------------|-----|
| 18 (Uptime) | `success` | `#388E3C` |
| 16 (Idle) | `warning-light` | `#F9A825` |
| 20 (Starving) | `secondary` | `#00897B` |
| 24 (Blocked) | `warning` | `#E65100` |
| 32 (Failure) | `error` | `#D32F2F` |
| 64 (Setup) | `primary` | `#0066CC` |
| 128 (Emergency) | `error-dark` | `#7B0000` |

**Formatting dates:** never use `new Date(str).toLocaleDateString()` on date-only strings — UTC midnight shifts to previous day in BRT. Use `str.split('-')` and format manually.

**Timestamps:** always store and transmit as ISO 8601 with timezone (`TIMESTAMPTZ`). Display in `America/Sao_Paulo` unless the client tenant has a different timezone.

## Roles

| Role | Who | Access |
|------|-----|--------|
| `meitech_admin` | Eduardo + team | All tenants, full config |
| `meitech_support` | Support team | All tenants, read-only |
| `client_admin` | Client manager | Own tenant only, config |
| `client_operator` | Factory operator | Own tenant, read + quality entry |

## POC Scope (current)

The POC targets exactly: **1 Schneider equipment via VPN, Modbus TCP, live status + production per hour + OEE on the dashboard.**

Success criteria:
1. A manager opens the dashboard on mobile and sees the machine in real time — **DONE (Sprint 0-2)**
2. A second equipment is added by editing only `equipment.json` — no code change — **DONE (config-driven)**
3. Email alert fires when machine is stopped for more than L1 threshold — **PARTIAL (alert engine exists, email placeholder)**

What has been completed:
- Full data pipeline: PLC Collector → SQLite → PostgreSQL → WebSocket → Dashboard
- PLC Simulator for testing without real hardware
- OEE automatic calculation (hourly, per equipment)
- JWT authentication + login flow
- Live Monitor, OEE Analytics, Alerts, Reports views
- Config-driven equipment registration (equipment.json)
- Modbus, Snap7, OPC-UA driver framework

What is explicitly **OUT OF SCOPE** for the POC:
- MQTT / cloud communication
- Multi-tenant
- OPC-UA / Toradex integration
- ML engine
- User registration / admin panel
- Production deployment with SSL

## Style Conventions

- Python: PEP 8, type hints everywhere, async/await throughout the API and collector
- Never use `eval()` — this was an antipattern in E2 Collector, do not repeat it
- Never use global variables for equipment state — use `DataProcessor._state: dict`
- Equipment iteration: always loop over config, never hardcode per-machine blocks
- All timestamps: `datetime` with timezone (`datetime.now(timezone.utc)`) — never naive datetimes
- SQL: always parameterised queries — never f-string SQL
- Frontend: JSX only (no TypeScript), Tailwind core utilities + MD3 theme tokens
- Texts: Brazilian Portuguese in UI, English in code identifiers and comments
- Log levels: `logging.getLogger(__name__)` — DEBUG for read cycles, INFO for state changes, WARNING for reconnects, ERROR for persistent failures
