// API Response Types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ApiError;
  timestamp: string;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  pagination: {
    page: number;
    per_page: number;
    total: number;
    pages: number;
  };
  timestamp: string;
}

// User and Authentication Types
export interface User {
  id: number;
  username: string;
  email: string;
  created_at: string;
  is_active: boolean;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface AuthResponse {
  token: string;
  user: User;
  expires_at: string;
}

// VM Types
export interface VM {
  id: number;
  ip_address: string;
  hostname: string;
  domain?: string;
  ssh_port: number;
  tags: string[];
  deployment_notes?: string;
  created_at: string;
  updated_at: string;
  last_seen?: string;
  is_reachable?: boolean;
  latest_cpu?: number;
  latest_ram_used?: number;
  latest_ram_total?: number;
  latest_disk_percent?: number;
  latest_disk_used_gb?: number;
  latest_disk_total_gb?: number;
  latest_response_time_ms?: number;
  latest_metrics_timestamp?: string;
  resolved_ip?: string;
  dns_last_checked?: string;
  dns_mismatch?: boolean;
  ping_interval_minutes?: number;
  dns_interval_hours?: number;
}

export interface VMCreateRequest {
  ip_address: string;
  hostname: string;
  domain?: string;
  ssh_port?: number;
  tags?: string[];
  deployment_notes?: string;
  ssh_username?: string;
  ssh_private_key?: string;
  ssh_password?: string;
  ping_interval_minutes?: number;
  dns_interval_hours?: number;
}

export interface VMUpdateRequest {
  ip_address?: string;
  hostname?: string;
  domain?: string;
  ssh_port?: number;
  tags?: string[];
  deployment_notes?: string;
  ssh_username?: string;
  ssh_private_key?: string;
  ssh_password?: string;
  ping_interval_minutes?: number;
  dns_interval_hours?: number;
}

// Metric Types
export interface Metric {
  id: number;
  vm_id: number;
  timestamp: string;
  cpu_usage_percent?: number;
  ram_used_mb?: number;
  ram_total_mb?: number;
  disk_used_gb?: number;
  disk_total_gb?: number;
  disk_usage_percent?: number;
  collection_success: boolean;
  error_message?: string;
}

// Ping Result Types
export interface PingResult {
  id: number;
  vm_id: number;
  timestamp: string;
  success: boolean;
  response_time_ms?: number;
  error_type?: string;
  icmp_success?: boolean;
  tcp_success?: boolean;
}

// Alert Types
export interface Alert {
  id: number;
  vm_id: number;
  alert_type: string;
  sent_at: string;
  notification_method: string;
  success: boolean;
  error_message?: string;
}

export interface AlertConfig {
  enabled: boolean;
  webhook_url?: string;
  email_recipient?: string;
  cooldown_minutes?: number;
}

// Dashboard Types
export interface DashboardVM extends VM {
  status: 'online' | 'offline' | 'unknown';
  last_ping?: PingResult;
  latest_metrics?: Metric;
}

// Search Types
export interface SearchResult {
  vm: VM;
  highlights?: {
    field: string;
    text: string;
  }[];
  rank: number;
}

// Service Types
export interface ServiceWithStatus {
  id: number;
  vm_id: number;
  service_name: string;
  display_name: string | null;
  check_command: string | null;
  enabled: boolean;
  status: 'active' | 'inactive' | 'failed' | 'unknown' | 'error' | string | null;
}

export interface ServiceCreateRequest {
  service_name: string;
  display_name?: string;
  check_command?: string;
}

// LXC Types
export interface LxcContainer {
  vmid: string;
  status: string;
  name: string;
}

export interface LxcResponse {
  is_proxmox: boolean;
  provider: string;
  containers: LxcContainer[];
}

export interface UptimeDailyBreakdown {
  date: string;
  uptime_percent: number;
  checks: number;
}

export interface UptimeStatsResponse {
  vm_id: number;
  period: string;
  uptime_percent: number;
  sla_tier: string;
  total_checks: number;
  successful_checks: number;
  failed_checks: number;
  avg_latency_ms: number | null;
  max_latency_ms: number | null;
  min_latency_ms: number | null;
  daily_breakdown: UptimeDailyBreakdown[];
}

export interface BatchUptimeResponse {
  vm_id: number;
  uptime_percent: number;
  sla_tier: string;
}

export interface ProcessInfo {
  pid: number;
  user: string;
  cpu_percent: number;
  mem_percent: number;
  vsz_kb: number;
  rss_kb: number;
  stat: string;
  started: string;
  time: string;
  command: string;
}

export interface ProcessListResponse {
  container_id: string;
  process_count: number;
  processes: ProcessInfo[];
}

export interface LxcResources {
  cpu_cores?: number;
  memory_mb?: number;
  swap_mb?: number;
  disk_gb?: number;
  disk_used_gb?: number;
}

export interface LxcResourcesResponse {
  container_id: string;
  provider: string;
  resources: LxcResources;
  raw_config: string;
}

export interface UpdateLxcResourcesRequest {
  cpu_cores?: number;
  memory_mb?: number;
  swap_mb?: number;
  disk_gb?: number;
}

export interface TopologyNode {
  id: string;
  type: string;
  label: string;
  ip: string;
  status: string;
}

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  label: string;
}

export interface TopologyResponse {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}
