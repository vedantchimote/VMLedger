# VMLedger Frontend

Next.js 14 frontend application for VMLedger - a lightweight CMDB and monitoring tool for personal VM infrastructure.

## Tech Stack

- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: TailwindCSS
- **Data Fetching**: TanStack Query (React Query)
- **HTTP Client**: Axios
- **State Management**: React Query + localStorage for auth

## Project Structure

```
frontend/
├── app/                    # Next.js App Router pages
│   ├── layout.tsx         # Root layout with QueryProvider
│   └── page.tsx           # Home page
├── components/            # Reusable React components
├── lib/                   # Utilities and configurations
│   ├── api-client.ts     # Axios instance with auth interceptors
│   ├── query-provider.tsx # React Query provider
│   └── hooks/            # Custom React Query hooks
│       ├── use-auth.ts   # Authentication hooks
│       ├── use-vms.ts    # VM management hooks
│       ├── use-monitoring.ts # Monitoring data hooks
│       └── use-dashboard.ts  # Dashboard hooks
├── types/                 # TypeScript type definitions
│   └── api.ts            # API response types
└── public/               # Static assets

```

## Getting Started

### Prerequisites

- Node.js 20.x or higher
- npm 10.x or higher

### Installation

1. Install dependencies:
```bash
npm install
```

2. Configure environment variables:
```bash
cp .env.example .env.local
```

Edit `.env.local` and set the API base URL:
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Development

Run the development server:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build

Build for production:
```bash
npm run build
```

Start production server:
```bash
npm start
```

## Features

### API Client

The API client (`lib/api-client.ts`) provides:

- **Authentication Token Management**: Automatic token storage and retrieval from localStorage
- **Request Interceptors**: Automatically attach JWT tokens to requests
- **Response Interceptors**: Handle 401 errors and redirect to login
- **Token Expiry Handling**: Check token expiry before requests
- **Error Handling**: Centralized error handling for API requests

### React Query Hooks

Custom hooks for data fetching with automatic caching and refetching:

- `useVMs()` - Fetch all VMs
- `useVM(id)` - Fetch single VM
- `useCreateVM()` - Create new VM
- `useUpdateVM()` - Update VM
- `useDeleteVM()` - Delete VM
- `useVMSearch(query)` - Search VMs
- `useVMMetrics(vmId)` - Fetch VM metrics
- `useVMPingHistory(vmId)` - Fetch ping history
- `useDashboard()` - Fetch dashboard summary (auto-refresh every 30s)

### Authentication

Authentication is handled via JWT tokens stored in localStorage:

- `tokenManager.getToken()` - Get current token
- `tokenManager.setToken(token, expiresAt)` - Store token
- `tokenManager.removeToken()` - Clear token
- `tokenManager.isAuthenticated()` - Check if user is authenticated
- `tokenManager.isTokenExpired()` - Check if token is expired

## Configuration

### React Query

Default configuration in `lib/query-provider.tsx`:

- **Stale Time**: 30 seconds (dashboard auto-refresh interval)
- **Cache Time**: 5 minutes
- **Retry**: 3 attempts with exponential backoff
- **Refetch on Window Focus**: Enabled
- **Refetch on Reconnect**: Enabled

### API Client

Configuration in `lib/api-client.ts`:

- **Base URL**: Configurable via `NEXT_PUBLIC_API_BASE_URL`
- **Timeout**: 30 seconds
- **Auto Token Attachment**: Enabled
- **401 Redirect**: Automatic redirect to `/login`

## TypeScript Types

All API types are defined in `types/api.ts`:

- `ApiResponse<T>` - Standard API response wrapper
- `User` - User model
- `VM` - Virtual machine model
- `Metric` - Resource metric model
- `PingResult` - Ping check result
- `Alert` - Alert notification
- `AlertConfig` - Alert configuration

## Next Steps

The following pages need to be implemented:

1. **Authentication Pages** (Task 17.2)
   - `/login` - Login page
   - `/register` - Registration page

2. **Dashboard** (Task 17.4)
   - `/dashboard` - Main dashboard with VM list

3. **VM Management** (Task 17.3)
   - `/vms/new` - VM registration form
   - `/vms/[id]/edit` - VM edit form

4. **VM Details** (Task 17.5)
   - `/vms/[id]` - VM details with metrics and history

5. **Search** (Task 17.7)
   - `/search` - Search interface

6. **Alert Configuration** (Task 17.8)
   - `/vms/[id]/alerts` - Alert configuration page

## License

This project is part of the VMLedger system.
