import axios, {
  AxiosInstance,
  AxiosError,
  InternalAxiosRequestConfig,
} from "axios";
import type {
  ApiResponse,
  AuthResponse,
  LoginRequest,
  RegisterRequest,
  VM,
  VMCreateRequest,
  VMUpdateRequest,
  Metric,
  PingResult,
  Alert,
  AlertConfig,
  SearchResult,
  ServiceWithStatus,
  ServiceCreateRequest,
  LxcResponse,
  BatchUptimeResponse,
  UptimeStatsResponse,
  ProcessListResponse,
  LxcResourcesResponse,
  UpdateLxcResourcesRequest,
  TopologyResponse,
} from "@/types/api";

// Token storage keys
const TOKEN_KEY = "vmledger_token";
const TOKEN_EXPIRY_KEY = "vmledger_token_expiry";

/**
 * Extract expiry date from a JWT token's exp claim.
 * Falls back to 24 hours from now if decoding fails.
 */
function getExpiryFromToken(token: string): string {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    if (payload.exp) {
      return new Date(payload.exp * 1000).toISOString();
    }
  } catch {
    // Decoding failed
  }
  // Default: 24 hours from now
  return new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
}

// API Client Configuration
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/**
 * Token Management Utilities
 */
export const tokenManager = {
  getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(TOKEN_KEY);
  },

  setToken(token: string, expiresAt: string): void {
    if (typeof window === "undefined") return;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(TOKEN_EXPIRY_KEY, expiresAt);
  },

  removeToken(): void {
    if (typeof window === "undefined") return;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
  },

  isTokenExpired(): boolean {
    if (typeof window === "undefined") return true;
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return true;
    const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
    // If no expiry record but token exists, try to decode it directly
    if (!expiry) {
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        if (payload.exp) {
          return new Date(payload.exp * 1000) <= new Date();
        }
      } catch {
        // Can't decode — assume valid to avoid locking user out
      }
      return false; // Token exists but no expiry — assume valid
    }
    return new Date(expiry) <= new Date();
  },

  isAuthenticated(): boolean {
    return !!this.getToken() && !this.isTokenExpired();
  },
};

/**
 * Create Axios instance with base configuration
 */
const createAxiosInstance = (): AxiosInstance => {
  const instance = axios.create({
    baseURL: `${API_BASE_URL}/api`,
    timeout: 30000,
    headers: {
      "Content-Type": "application/json",
    },
  });

  // Request interceptor: Attach authentication token
  instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      const token = tokenManager.getToken();

      if (token && !tokenManager.isTokenExpired()) {
        config.headers.Authorization = `Bearer ${token}`;
      }

      return config;
    },
    (error) => {
      return Promise.reject(error);
    },
  );

  // Response interceptor: Handle errors and token expiry
  instance.interceptors.response.use(
    (response) => {
      return response;
    },
    (error: AxiosError) => {
      // Handle 401 Unauthorized — only remove token and redirect if we
      // are NOT already on the login/register pages (to avoid redirect loops)
      if (error.response?.status === 401) {
        if (
          typeof window !== "undefined" &&
          !window.location.pathname.includes("/login") &&
          !window.location.pathname.includes("/register")
        ) {
          // Remove stale token and redirect to login
          tokenManager.removeToken();
          window.location.href = "/login";
        }
      }

      // Extract backend error message so callers get a human-readable message
      // instead of Axios's generic "Request failed with status code 400"
      if (error.response?.data) {
        const data = error.response.data as any;
        const backendMessage =
          data?.error?.message || data?.message || data?.detail;
        if (backendMessage) {
          const enrichedError = new Error(backendMessage);
          (enrichedError as any).response = error.response;
          (enrichedError as any).status = error.response.status;
          (enrichedError as any).code = data?.error?.code;
          return Promise.reject(enrichedError);
        }
      }

      // Handle network errors
      if (!error.response) {
        console.error("Network error:", error.message);
        return Promise.reject(
          new Error("Network error — please check your connection"),
        );
      }

      return Promise.reject(error);
    },
  );

  return instance;
};

// Create the API client instance
const apiClient = createAxiosInstance();

/**
 * API Client Methods
 */
export const api = {
  // Authentication
  auth: {
    async login(credentials: LoginRequest): Promise<AuthResponse> {
      const response = await apiClient.post<ApiResponse<any>>(
        "/auth/login",
        credentials,
      );

      if (response.data.success && response.data.data) {
        const authData = response.data.data;
        // Backend returns {token, user_id, username, email} without expires_at
        // Derive expiry from the JWT's exp claim
        const expiresAt =
          authData.expires_at || getExpiryFromToken(authData.token);
        tokenManager.setToken(authData.token, expiresAt);
        return authData;
      }

      throw new Error(response.data.error?.message || "Login failed");
    },

    async register(userData: RegisterRequest): Promise<AuthResponse> {
      const response = await apiClient.post<ApiResponse<any>>(
        "/auth/register",
        userData,
      );

      if (response.data.success && response.data.data) {
        const authData = response.data.data;
        const expiresAt =
          authData.expires_at || getExpiryFromToken(authData.token);
        tokenManager.setToken(authData.token, expiresAt);
        return authData;
      }

      throw new Error(response.data.error?.message || "Registration failed");
    },

    async logout(): Promise<void> {
      try {
        await apiClient.post("/auth/logout");
      } finally {
        tokenManager.removeToken();
      }
    },

    async refreshToken(): Promise<AuthResponse> {
      const response =
        await apiClient.post<ApiResponse<AuthResponse>>("/auth/refresh");

      if (response.data.success && response.data.data) {
        const authData = response.data.data;
        tokenManager.setToken(authData.token, authData.expires_at);
        return authData;
      }

      throw new Error("Token refresh failed");
    },
  },

  // VM Management
  vms: {
    async list(): Promise<VM[]> {
      const response = await apiClient.get<ApiResponse<VM[]>>("/vms");
      return response.data.data || [];
    },

    async get(vmId: number): Promise<VM> {
      const response = await apiClient.get<ApiResponse<VM>>(`/vms/${vmId}`);

      if (response.data.success && response.data.data) {
        return response.data.data;
      }

      throw new Error(response.data.error?.message || "Failed to fetch VM");
    },

    async getSpecs(vmId: number): Promise<any> {
      const response = await apiClient.get<ApiResponse<any>>(`/vms/${vmId}/specs`);
      if (response.data.success && response.data.data) {
        return response.data.data;
      }
      throw new Error(response.data.error?.message || "Failed to fetch VM specs");
    },

    async create(vmData: VMCreateRequest): Promise<VM> {
      const response = await apiClient.post<ApiResponse<VM>>("/vms", vmData);

      if (response.data.success && response.data.data) {
        return response.data.data;
      }

      throw new Error(response.data.error?.message || "Failed to create VM");
    },

    async update(vmId: number, vmData: VMUpdateRequest): Promise<VM> {
      const response = await apiClient.put<ApiResponse<VM>>(
        `/vms/${vmId}`,
        vmData,
      );

      if (response.data.success && response.data.data) {
        return response.data.data;
      }

      throw new Error(response.data.error?.message || "Failed to update VM");
    },

    async delete(vmId: number): Promise<void> {
      const response = await apiClient.delete<ApiResponse<void>>(
        `/vms/${vmId}`,
      );

      if (!response.data.success) {
        throw new Error(response.data.error?.message || "Failed to delete VM");
      }
    },

    async search(query: string): Promise<SearchResult[]> {
      const response = await apiClient.get<ApiResponse<any>>("/search", {
        params: { q: query },
      });
      // Backend returns { data: { results: [...], count, query } }
      // Each result is a flat VM object with rank and highlighted_notes mixed in
      const data = response.data.data;
      const rawResults = Array.isArray(data) ? data : data?.results || [];

      // Transform flat results into the { vm, rank, highlights } format the frontend expects
      return rawResults.map((item: any) => ({
        vm: {
          id: item.id,
          ip_address: item.ip_address,
          hostname: item.hostname,
          domain: item.domain,
          ssh_port: item.ssh_port,
          tags: item.tags || [],
          deployment_notes: item.deployment_notes,
          created_at: item.created_at,
          updated_at: item.updated_at,
          last_seen: item.last_seen,
          is_reachable: item.is_reachable,
        },
        rank: item.rank || 0,
        highlights: item.highlighted_notes
          ? [{ field: "deployment_notes", text: item.highlighted_notes }]
          : undefined,
      }));
    },
    async resolveHostname(ip: string): Promise<{ hostname: string }> {
      const response = await apiClient.get<ApiResponse<{ hostname: string }>>(`/vms/tools/resolve?ip=${encodeURIComponent(ip)}`);
      return response.data.data as { hostname: string };
    },
  },

  // Monitoring Data
  monitoring: {
    async getMetrics(vmId: number, limit: number = 100): Promise<Metric[]> {
      const response = await apiClient.get<ApiResponse<any>>(
        `/vms/${vmId}/metrics`,
        { params: { limit } },
      );
      // Backend returns { data: { metrics: [...], count, vm_id } }
      const data = response.data.data;
      return Array.isArray(data) ? data : data?.metrics || [];
    },

    async getPingHistory(
      vmId: number,
      limit: number = 100,
    ): Promise<PingResult[]> {
      const response = await apiClient.get<ApiResponse<any>>(
        `/vms/${vmId}/ping`,
        { params: { limit } },
      );
      // Backend returns { data: { ping_results: [...], count, vm_id } }
      const data = response.data.data;
      return Array.isArray(data) ? data : data?.ping_results || [];
    },

    async getStatus(
      vmId: number,
    ): Promise<{ is_reachable: boolean; last_seen?: string }> {
      const response = await apiClient.get<
        ApiResponse<{ is_reachable: boolean; last_seen?: string }>
      >(`/vms/${vmId}/status`);

      if (response.data.success && response.data.data) {
        return response.data.data;
      }

      throw new Error("Failed to fetch VM status");
    },
  },

  // Alert Configuration
  alerts: {
    async getConfig(vmId: number): Promise<AlertConfig> {
      const response = await apiClient.get<ApiResponse<AlertConfig>>(
        `/vms/${vmId}/alerts/config`,
      );

      if (response.data.success && response.data.data) {
        return response.data.data;
      }

      throw new Error("Failed to fetch alert config");
    },

    async updateConfig(
      vmId: number,
      config: AlertConfig,
    ): Promise<AlertConfig> {
      const response = await apiClient.put<ApiResponse<AlertConfig>>(
        `/vms/${vmId}/alerts/config`,
        config,
      );

      if (response.data.success && response.data.data) {
        return response.data.data;
      }

      throw new Error("Failed to update alert config");
    },

    async getHistory(vmId: number): Promise<Alert[]> {
      const response = await apiClient.get<ApiResponse<any>>(
        `/vms/${vmId}/alerts/history`,
      );
      const data = response.data.data;
      return Array.isArray(data) ? data : data?.alerts || data?.history || [];
    },

    async getGlobalHistory(): Promise<(Alert & { hostname?: string })[]> {
      const response = await apiClient.get<ApiResponse<any>>("/vms/alerts");
      const data = response.data.data;
      return Array.isArray(data) ? data : data?.alerts || data?.history || [];
    },
  },

  // Dashboard
  dashboard: {
    async getSummary(): Promise<VM[]> {
      const response = await apiClient.get<ApiResponse<any>>("/dashboard");
      const dashboardData = response.data.data;
      // Backend returns {vms: [...], total_vms, reachable_vms, unreachable_vms}
      // Each VM has nested latest_metrics and latest_ping — flatten them to match frontend VM type
      const vms = dashboardData?.vms || dashboardData || [];
      return vms.map((vm: any) => ({
        ...vm,
        latest_cpu: vm.latest_metrics?.cpu_usage_percent ?? vm.latest_cpu,
        latest_ram_used: vm.latest_metrics?.ram_used_mb ?? vm.latest_ram_used,
        latest_ram_total:
          vm.latest_metrics?.ram_total_mb ?? vm.latest_ram_total,
        latest_disk_percent:
          vm.latest_metrics?.disk_usage_percent ?? vm.latest_disk_percent,
        latest_disk_used_gb:
          vm.latest_metrics?.disk_used_gb ?? vm.latest_disk_used_gb,
        latest_disk_total_gb:
          vm.latest_metrics?.disk_total_gb ?? vm.latest_disk_total_gb,
        latest_response_time_ms:
          vm.latest_ping?.response_time_ms ?? vm.latest_response_time_ms,
        latest_metrics_timestamp:
          vm.latest_metrics?.timestamp ?? vm.latest_metrics_timestamp,
      }));
    },
  },

  // Triggers
  triggers: {
    async triggerPing(vmId: number): Promise<any> {
      const response = await apiClient.post<ApiResponse<any>>(`/vms/${vmId}/trigger/ping`);
      return response.data;
    },
    async triggerDnsCheck(vmId: number): Promise<any> {
      const response = await apiClient.post<ApiResponse<any>>(`/vms/${vmId}/trigger/dns-check`);
      return response.data;
    },
    async triggerCollectMetrics(vmId: number): Promise<any> {
      const response = await apiClient.post<ApiResponse<any>>(`/vms/${vmId}/trigger/collect-metrics`);
      return response.data;
    },
  },

  // Services
  services: {
    async list(vmId: number): Promise<ServiceWithStatus[]> {
      const response = await apiClient.get<ServiceWithStatus[]>(`/vms/${vmId}/services`);
      return response.data; // Note: We don't use ApiResponse wrapper in this endpoint as per backend implementation
    },
    async add(vmId: number, data: ServiceCreateRequest): Promise<ServiceWithStatus> {
      const response = await apiClient.post<ServiceWithStatus>(`/vms/${vmId}/services`, data);
      return response.data;
    },
    async remove(vmId: number, serviceId: number): Promise<void> {
      await apiClient.delete(`/vms/${vmId}/services/${serviceId}`);
    },
    async checkNow(vmId: number): Promise<void> {
      await apiClient.post(`/vms/${vmId}/services/check`);
    },
  },

  // LXC
  lxc: {
    async list(vmId: number): Promise<LxcResponse> {
      const response = await apiClient.get<LxcResponse>(`/vms/${vmId}/lxc`);
      return response.data;
    },
    async performLxcAction(vmId: number, lxcId: string, action: string): Promise<{ success: boolean; message: string }> {
      const response = await apiClient.post(`vms/${vmId}/lxc/${lxcId}/action`, { action });
      return response.data;
    },
    async getResources(vmId: number, lxcId: string): Promise<LxcResourcesResponse> {
      const response = await apiClient.get(`vms/${vmId}/lxc/${lxcId}/resources`);
      return response.data;
    },
    async updateResources(vmId: number, lxcId: string, data: UpdateLxcResourcesRequest): Promise<{ success: boolean; message: string }> {
      const response = await apiClient.put(`vms/${vmId}/lxc/${lxcId}/resources`, data);
      return response.data;
    }
  },

  // Uptime tracking
  uptime: {
    async getUptimeSummary(period: string = "30d"): Promise<BatchUptimeResponse[]> {
      const response = await apiClient.get(`vms/uptime/summary?period=${period}`);
      return response.data;
    },

    async getVmUptime(vmId: number, period: string = "30d"): Promise<UptimeStatsResponse> {
      const response = await apiClient.get(`vms/${vmId}/uptime?period=${period}`);
      return response.data;
    },
  },

  // Processes
  processes: {
    async list(vmId: number, lxcId: string, sort: string = "cpu", limit: number = 50): Promise<ProcessListResponse> {
      const response = await apiClient.get(`vms/${vmId}/lxc/${lxcId}/processes`, { params: { sort, limit } });
      return response.data;
    },
    async kill(vmId: number, lxcId: string, pid: number, signal: string = "TERM"): Promise<{success: boolean, message: string}> {
      const response = await apiClient.post(`vms/${vmId}/lxc/${lxcId}/processes/${pid}/kill`, { signal });
      return response.data;
    }
  },

  // Network
  network: {
    async getTopology(vmId: number): Promise<TopologyResponse> {
      const response = await apiClient.get(`/vms/${vmId}/network/topology`);
      return response.data;
    }
  }
};

export default apiClient;
