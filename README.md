# VMLedger

<div align="center">

**Lightweight CMDB & Observability Platform for VM Infrastructure**

[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D)](https://redis.io/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[Features](#-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [API Reference](#-api-reference) • [Dashboard](#-dashboard)

</div>

---

## Overview

VMLedger is an agentless monitoring and configuration management database (CMDB) for personal and team VM infrastructure. It connects to your VMs via SSH to collect real-time metrics, performs health checks, detects DNS drift, and provides a rich dashboard for fleet-wide observability — all without installing agents on your VMs.

## ✨ Features

### VM Registry & Lifecycle
- Register VMs with IP, hostname, domain, SSH port, and tags
- SSH credential validation on registration (password or key)
- AES-256 encrypted credential storage with per-user key derivation
- Bulk select and delete VMs from dashboard
- Tag-based organization and filtering

### Real-Time Monitoring
- Automated ICMP + TCP ping checks every 60 seconds
- SSH-based system metrics collection (CPU, RAM, Disk) every 5 minutes
- On-demand triggers: Ping, DNS Check, and Metrics Collection with animated radar feedback
- Historical data retention (last 1000 data points per VM)
- Trigger actions refetch data silently (no page reload)

### Live VM Specs
- One-click hardware spec fetch via SSH (`lscpu`, `free`, `df`, `/etc/os-release`)
- Displays: OS name, kernel version, CPU model & cores, total RAM, storage partitions
- Dedicated Specs tab on each VM's detail page

### DNS Drift Detection
- Periodic forward DNS resolution of VM hostnames
- Compares resolved IP vs registered IP to detect DNS mismatches
- DNS health summary in analytics dashboard

### Fleet Analytics Dashboard
- **6 KPI summary cards**: Total VMs, Online count, Avg CPU / Memory / Disk / Latency
- **Fleet resource pools**: Aggregate RAM and Disk usage with progress bars
- **Top consumers**: Ranked CPU, Memory, and Disk usage per VM
- **Ping latency ranking**: Fastest to slowest response times
- **DNS health panel**: Healthy / Mismatched / Unchecked breakdown
- **Tag distribution**: Visual breakdown of tag usage across fleet
- **Per-instance table**: Full resource breakdown with threshold highlighting (≥80% = red)

### Multi-View Dashboard
- **Grid view**: VM cards with status indicator, metrics bars, and tags
- **List view**: Compact row-based layout
- **Table view**: Sortable tabular data
- **Kanban view**: Status-grouped columns
- **Minimal view**: Ultra-compact status dots
- **Analytics view**: Full fleet-wide metrics dashboard

### Alerting System
- Webhook notifications (Slack, Discord, custom endpoints)
- Configurable cooldown periods (default: 15 minutes)
- Alert history and acknowledgment tracking
- Per-VM alert configuration

### Search
- Partial/prefix matching: typing `harbor` finds `harbornode`
- Full-text search with PostgreSQL tsquery + ILIKE fallback
- Search results display full resource metrics (cross-referenced with dashboard data)
- Relevance ranking with highlighted matches in deployment notes

### Security
- JWT authentication with 24-hour sessions
- Bcrypt password hashing (cost factor 12)
- Rate limiting: 5 failed login attempts per 15 minutes
- Account lockout: 30-minute lockout after 5 failures
- CORS protection with configurable origins
- Backend error messages surfaced to UI (no raw HTTP status codes)

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+ & Docker Compose 2.0+
- Node.js 18+ (for frontend)

### Start Backend (Docker)

```bash
git clone https://github.com/vedantchimote/VMLedger.git
cd VMLedger

# Start PostgreSQL, Redis, FastAPI, Celery worker & beat
docker-compose up -d

# Run database migrations
docker-compose exec api alembic upgrade head
```

### Start Frontend

```bash
cd frontend
npm install
npm run dev
```

### Access

| Service        | URL                          |
|----------------|------------------------------|
| Frontend       | http://localhost:3000         |
| Backend API    | http://localhost:8000         |
| Swagger Docs   | http://localhost:8000/api/docs |
| ReDoc          | http://localhost:8000/api/redoc |

### Register & Login

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@example.com",
    "password": "SecurePass123!@"
  }'
```

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────┐
│   Next.js 14    │────▶│   FastAPI        │────▶│ PostgreSQL   │
│   Frontend      │     │   Backend        │     │ (Data Store) │
│   :3000         │     │   :8000          │     │ :5432        │
└─────────────────┘     └────────┬─────────┘     └──────────────┘
                                 │
                        ┌────────┴─────────┐
                        │                  │
                   ┌────▼────┐      ┌──────▼──────┐
                   │  Redis  │      │   Celery     │
                   │  Cache  │◀────▶│   Workers    │
                   │  :6379  │      │   + Beat     │
                   └─────────┘      └──────┬───────┘
                                           │ SSH
                                    ┌──────▼───────┐
                                    │  Your VMs    │
                                    │  (Agentless) │
                                    └──────────────┘
```

### Component Breakdown

| Layer      | Technology                        | Purpose                                    |
|------------|-----------------------------------|--------------------------------------------|
| Frontend   | Next.js 14, React 18, TanStack Query | Dashboard UI, VM management, analytics   |
| API        | FastAPI, SQLAlchemy 2.0, Pydantic v2 | REST API, auth middleware, CORS          |
| Workers    | Celery 5.3, Redis broker          | Ping checks, metrics collection, DNS checks |
| Scheduler  | Celery Beat                       | Periodic task scheduling (60s/300s intervals) |
| Database   | PostgreSQL 15, Alembic            | Persistent storage, full-text search       |
| Cache      | Redis 7                           | Dashboard caching (30s TTL), task broker   |
| SSH        | Paramiko 3.4                      | Agentless metric collection from VMs       |

## 📡 API Reference

### Authentication
| Method | Endpoint             | Description          |
|--------|----------------------|----------------------|
| POST   | `/api/auth/register` | Register new user    |
| POST   | `/api/auth/login`    | Login, get JWT token |
| POST   | `/api/auth/logout`   | Invalidate token     |
| POST   | `/api/auth/refresh`  | Refresh JWT token    |

### VM Management
| Method | Endpoint                              | Description                      |
|--------|---------------------------------------|----------------------------------|
| GET    | `/api/vms`                            | List all VMs (paginated)         |
| POST   | `/api/vms`                            | Register new VM                  |
| GET    | `/api/vms/{id}`                       | Get VM details                   |
| PUT    | `/api/vms/{id}`                       | Update VM                        |
| DELETE | `/api/vms/{id}`                       | Delete VM and all associated data |
| GET    | `/api/vms/{id}/specs`                 | Fetch live hardware specs via SSH |

### Monitoring
| Method | Endpoint                              | Description                      |
|--------|---------------------------------------|----------------------------------|
| GET    | `/api/vms/{id}/metrics`               | Get historical metrics           |
| GET    | `/api/vms/{id}/ping`                  | Get ping history                 |
| GET    | `/api/vms/{id}/status`                | Get current VM status            |
| POST   | `/api/vms/{id}/trigger/ping`          | Trigger on-demand ping           |
| POST   | `/api/vms/{id}/trigger/dns-check`     | Trigger on-demand DNS check      |
| POST   | `/api/vms/{id}/trigger/collect-metrics` | Trigger on-demand metric collection |

### Alerts
| Method | Endpoint                              | Description                      |
|--------|---------------------------------------|----------------------------------|
| GET    | `/api/vms/{id}/alerts/config`         | Get alert configuration          |
| PUT    | `/api/vms/{id}/alerts/config`         | Update alert configuration       |
| GET    | `/api/vms/{id}/alerts/history`        | Get alert history                |

### Dashboard & Search
| Method | Endpoint          | Description                              |
|--------|-------------------|------------------------------------------|
| GET    | `/api/dashboard`  | Aggregated dashboard with all VMs + metrics |
| GET    | `/api/search`     | Full-text search with prefix matching    |

## 🖥️ Dashboard

The dashboard provides 6 view modes for different use cases:

- **Grid**: VM cards with health bars and status badges
- **List**: Compact rows for large fleets
- **Table**: Sortable columns for data comparison
- **Kanban**: Drag-style columns grouped by status
- **Minimal**: Ultra-compact status dots
- **Analytics**: Fleet-wide KPIs, resource pools, top consumers, DNS health, latency ranking, tag distribution, per-instance table

### VM Detail Page

#### Overview Tab
- **SVG ring gauges** for CPU, Memory, Disk with color-coded thresholds
- **Health summary**: Uptime %, Avg Latency, Status (with relative time), Last Metric timestamp
- **Connectivity log**: Compact table with status dots
- **Deployment manifest**: Markdown-rendered notes with prose styling

#### Metrics Tab
- **Time range selector**: 1H / 6H / 24H / 7D / All
- **Chart mode toggle**: Individual (3 separate) or Combined (overlay)
- **Stats summary**: Current, Min, Avg, Max per metric
- **Custom tooltip**: Full timestamp, colored dots, RAM MB breakdown
- In Combined mode: clickable legend toggles to show/hide each metric

#### Other Tabs
| Tab    | Content                                                      |
|--------|--------------------------------------------------------------|
| Specs  | Live OS, CPU, RAM, storage partition data fetched via SSH    |
| Ping   | Full ping history with response times and success/failure    |
| Notes  | Markdown-rendered deployment notes                           |
| Alerts | Alert webhook configuration and event history                |

## 📁 Project Structure

```
VMLedger/
├── vmledger/                    # Backend application
│   ├── api/
│   │   ├── auth.py             # Auth endpoints (register/login/logout/refresh)
│   │   └── vms.py              # VM CRUD, dashboard, triggers, specs, alerts
│   ├── middleware/
│   │   ├── auth.py             # JWT validation middleware
│   │   └── rate_limit.py       # Rate limiting middleware
│   ├── models/                 # SQLAlchemy models (user, vm, credential, metric, etc.)
│   ├── schemas/                # Pydantic validation schemas
│   ├── services/
│   │   ├── auth_service.py     # Authentication & JWT management
│   │   ├── vm_registry_service.py  # VM CRUD + delete with cascade
│   │   ├── metric_collector_service.py  # SSH metrics + VM specs fetch
│   │   ├── credential_manager.py  # AES-256 encrypt/decrypt
│   │   ├── search_engine_service.py  # Full-text search with Redis cache
│   │   └── data_cleanup_service.py   # Historical data retention
│   ├── tasks/                  # Celery tasks (ping, metrics, DNS)
│   ├── main.py                 # FastAPI app + router registration
│   ├── config.py               # Settings from environment
│   └── database.py             # SQLAlchemy engine + session
├── frontend/                   # Next.js 14 frontend
│   ├── app/
│   │   ├── dashboard/          # Main dashboard with 6 view modes
│   │   │   ├── page.tsx        # Dashboard page (grid/list/table/kanban/minimal/analytics)
│   │   │   └── KanbanCard.tsx  # Draggable kanban card component
│   │   ├── vms/
│   │   │   ├── new/page.tsx    # VM registration form with credential validation
│   │   │   └── [id]/page.tsx   # VM detail page (monitoring/ping/DNS/specs/alerts)
│   │   ├── login/page.tsx      # Login page
│   │   └── register/page.tsx   # Registration page
│   ├── lib/
│   │   ├── api-client.ts       # Axios client with token injection + error extraction
│   │   └── hooks/              # React Query hooks (useVMs, useDashboard, useAuth, etc.)
│   └── types/api.ts            # TypeScript interfaces
├── alembic/                    # Database migrations
├── docker-compose.yml          # Full stack: postgres, redis, api, celery worker, beat
├── Dockerfile                  # Backend container image
└── requirements.txt            # Python dependencies
```

## ⚙️ Configuration

All configuration via environment variables (see `docker-compose.yml` or `.env`):

| Variable                  | Default   | Description                     |
|---------------------------|-----------|---------------------------------|
| `DATABASE_URL`            | required  | PostgreSQL connection string    |
| `REDIS_URL`               | required  | Redis connection string         |
| `SECRET_KEY`              | required  | JWT signing key                 |
| `ENCRYPTION_MASTER_KEY`   | required  | AES credential encryption key   |
| `PING_INTERVAL_SECONDS`   | 60        | Health check frequency          |
| `METRICS_INTERVAL_SECONDS`| 300       | Metric collection frequency     |
| `ALERT_COOLDOWN_MINUTES`  | 15        | Alert cooldown period           |
| `CONCURRENT_WORKERS`      | 10        | Max parallel SSH connections    |
| `JWT_EXPIRATION_HOURS`    | 24        | Token lifetime                  |
| `CORS_ORIGINS`            | localhost | Allowed frontend origins        |

## 🧪 Development

```bash
# Backend (without Docker)
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
uvicorn vmledger.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend && npm install && npm run dev

# TypeScript check
cd frontend && npx tsc --noEmit

# Database migrations
alembic upgrade head              # Apply all
alembic revision --autogenerate -m "description"  # Generate new
alembic downgrade -1              # Rollback one
```

## License

MIT License — see [LICENSE](LICENSE) for details.
