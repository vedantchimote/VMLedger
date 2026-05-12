# VMLedger Frontend

Next.js 14 dashboard for VMLedger — a lightweight CMDB and observability platform for VM infrastructure.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: TailwindCSS with custom design system (glass-card, surface tokens)
- **Data Fetching**: TanStack Query (React Query) with 30s auto-refresh
- **HTTP Client**: Axios with interceptors
- **State Management**: React Query + localStorage for auth tokens

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout with QueryProvider
│   ├── page.tsx                # Home page (redirects to dashboard)
│   ├── login/page.tsx          # Login form
│   ├── register/page.tsx       # Registration form
│   ├── dashboard/
│   │   ├── page.tsx            # Dashboard (6 view modes + analytics)
│   │   └── KanbanCard.tsx      # Kanban view card component
│   └── vms/
│       ├── new/page.tsx        # VM registration with credential validation
│       └── [id]/page.tsx       # VM details (monitoring/ping/DNS/specs/alerts)
├── lib/
│   ├── api-client.ts           # Axios instance + token manager + error extraction
│   ├── query-provider.tsx      # React Query provider config
│   ├── validation.ts           # Form validation utilities
│   └── hooks/
│       ├── use-auth.ts         # useLogin, useLogout, useRegister, useAuth
│       ├── use-vms.ts          # useVMs, useVM, useVMSpecs, useCreateVM, useDeleteVM
│       ├── use-dashboard.ts    # useDashboard (auto-refresh, auth-gated)
│       ├── use-monitoring.ts   # useVMMetrics, useVMPingHistory
│       └── use-alerts.ts       # useAlertConfig, useAlertHistory
├── types/
│   └── api.ts                  # TypeScript interfaces (VM, Metric, PingResult, etc.)
└── public/                     # Static assets
```

## Getting Started

```bash
# Install dependencies
npm install

# Configure API URL (optional — defaults to http://localhost:8000)
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" > .env.local

# Start dev server
npm run dev

# Type check
npx tsc --noEmit
```

Open http://localhost:3000 in your browser.

## Dashboard View Modes

The dashboard supports 6 view modes, switchable via toolbar icons:

| Mode      | Description                                                   |
|-----------|---------------------------------------------------------------|
| Grid      | VM cards with status dot, CPU/RAM/Disk bars, tags             |
| List      | Compact rows with inline metrics                              |
| Table     | Sortable tabular data                                         |
| Kanban    | Status-grouped columns (online/offline)                       |
| Minimal   | Ultra-compact status dot grid                                 |
| Analytics | Fleet-wide metrics: 6 KPI cards, resource pools, top consumers, DNS health, latency ranking, tag distribution, per-instance table |

## VM Detail Page Tabs

### Overview Tab
- **SVG ring gauges**: CPU, Memory, Disk with animated fill and color thresholds (green/blue/amber/red)
- **Health summary**: 4 KPI cards — Uptime %, Avg Latency, Status (glowing dot + relative time), Last Metric
- **Connectivity log**: Compact table rows with status dots and latency
- **Deployment manifest**: Markdown-rendered notes via ReactMarkdown + remark-gfm

### Metrics Tab
- **Time range selector**: 1H / 6H / 24H / 7D / All
- **Chart mode**: Individual (3 separate charts) or Combined (overlay with toggle legends)
- **Stats cards**: Current, Min, Avg, Max for each metric; Max ≥ 90% highlighted red
- **Custom tooltip**: Full datetime, colored metric dots, RAM MB sub-breakdown

### Other Tabs
| Tab    | Description                                                      |
|--------|------------------------------------------------------------------|
| Specs  | Live hardware specs (OS, CPU, RAM, partitions) fetched via SSH   |
| Ping   | Full ping history with response times and success/failure        |
| Notes  | Full Markdown-rendered deployment notes                          |
| Alerts | Alert webhook configuration and event history                    |

### Trigger Actions
Ping Now / DNS Check / Collect Metrics buttons fire backend tasks and show a **radar-style pinging animation** with a 5-second progress bar. Data refreshes silently via React Query `refetch()` — no page reload.

## React Query Hooks

### Authentication
- `useLogin()` — Login mutation, stores JWT + redirects to dashboard
- `useRegister()` — Register mutation with auto-login
- `useLogout()` — Logout mutation, clears token + redirects to login
- `useAuth()` — Auth state (isAuthenticated, isMounted, token)

### VM Management
- `useVMs()` — Fetch all VMs for current user
- `useVM(id)` — Fetch single VM details
- `useVMSpecs(id)` — Fetch live hardware specs (5-min stale time)
- `useVMSearch(query)` — Full-text search with prefix matching (results enriched with dashboard metrics)
- `useCreateVM()` — Register new VM
- `useUpdateVM()` — Update VM fields
- `useDeleteVM()` — Delete VM and all associated data

### Monitoring
- `useVMMetrics(vmId, limit)` — Historical CPU/RAM/Disk metrics
- `useVMPingHistory(vmId, limit)` — Historical ping results
- `useDashboard()` — Aggregated dashboard data (30s auto-refresh, auth-gated)

### Alerts
- `useAlertConfig(vmId)` — Get alert webhook configuration
- `useUpdateAlertConfig()` — Update alert settings
- `useAlertHistory(vmId)` — Get alert event history

## API Client Features

The Axios client (`lib/api-client.ts`) handles:

- **Token injection**: Automatically attaches `Bearer` token to all requests
- **Token expiry check**: Falls back to JWT `exp` claim when localStorage expiry is missing
- **Backend error extraction**: Parses `error.message` from API responses instead of showing raw HTTP status codes
- **Auth redirect**: On 401, removes token and redirects to `/login` (skipped on login/register pages)
- **Network errors**: Shows user-friendly "Network error" message

## Token Management

```typescript
tokenManager.getToken()         // Get JWT from localStorage
tokenManager.setToken(t, exp)   // Store JWT + expiry
tokenManager.removeToken()      // Clear auth state
tokenManager.isAuthenticated()  // Token exists and not expired
tokenManager.isTokenExpired()   // Check expiry (falls back to JWT decode)
```

## License

Part of the VMLedger system — MIT License.
