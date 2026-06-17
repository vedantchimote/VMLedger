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
