import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
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
} from '@/types/api';

// Token storage keys
const TOKEN_KEY = 'vmledger_token';
const TOKEN_EXPIRY_KEY = 'vmledger_token_expiry';

// API Client Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

/**
 * Token Management Utilities
 */
export const tokenManager = {
  getToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(TOKEN_KEY);
  },

  setToken(token: string, expiresAt: string): void {
    if (typeof window === 'undefined') return;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(TOKEN_EXPIRY_KEY, expiresAt);
  },

  removeToken(): void {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
  },

  isTokenExpired(): boolean {
    if (typeof window === 'undefined') return true;
    const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
    if (!expiry) return true;
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
      'Content-Type': 'application/json',
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
    }
  );

  // Response interceptor: Handle errors and token expiry
  instance.interceptors.response.use(
    (response) => {
      return response;
    },
    (error: AxiosError) => {
      // Handle 401 Unauthorized - token expired or invalid
      if (error.response?.status === 401) {
        tokenManager.removeToken();
        
        // Redirect to login page if not already there
        if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
          window.location.href = '/login';
        }
      }

      // Handle network errors
      if (!error.response) {
        console.error('Network error:', error.message);
      }

      return Promise.reject(error);
    }
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
      const response = await apiClient.post<ApiResponse<AuthResponse>>(
        '/auth/login',
        credentials
      );
      
      if (response.data.success && response.data.data) {
        const authData = response.data.data;
        tokenManager.setToken(authData.token, authData.expires_at);
        return authData;
      }
      
      throw new Error(response.data.error?.message || 'Login failed');
    },

    async register(userData: RegisterRequest): Promise<AuthResponse> {
      const response = await apiClient.post<ApiResponse<AuthResponse>>(
        '/auth/register',
        userData
      );
      
      if (response.data.success && response.data.data) {
        const authData = response.data.data;
        tokenManager.setToken(authData.token, authData.expires_at);
        return authData;
      }
      
      throw new Error(response.data.error?.message || 'Registration failed');
    },

    async logout(): Promise<void> {
      try {
        await apiClient.post('/auth/logout');
      } finally {
        tokenManager.removeToken();
      }
    },

    async refreshToken(): Promise<AuthResponse> {
      const response = await apiClient.post<ApiResponse<AuthResponse>>('/auth/refresh');
      
      if (response.data.success && response.data.data) {
        const authData = response.data.data;
        tokenManager.setToken(authData.token, authData.expires_at);
        return authData;
      }
      
      throw new Error('Token refresh failed');
    },
  },

  // VM Management
  vms: {
    async list(): Promise<VM[]> {
      const response = await apiClient.get<ApiResponse<VM[]>>('/vms');
      return response.data.data || [];
    },

    async get(vmId: number): Promise<VM> {
      const response = await apiClient.get<ApiResponse<VM>>(`/vms/${vmId}`);
      
      if (response.data.success && response.data.data) {
        return response.data.data;
      }
      
      throw new Error(response.data.error?.message || 'Failed to fetch VM');
    },

    async create(vmData: VMCreateRequest): Promise<VM> {
      const response = await apiClient.post<ApiResponse<VM>>('/vms', vmData);
      
      if (response.data.success && response.data.data) {
        return response.data.data;
      }
      
      throw new Error(response.data.error?.message || 'Failed to create VM');
    },

    async update(vmId: number, vmData: VMUpdateRequest): Promise<VM> {
      const response = await apiClient.put<ApiResponse<VM>>(`/vms/${vmId}`, vmData);
      
      if (response.data.success && response.data.data) {
        return response.data.data;
      }
      
      throw new Error(response.data.error?.message || 'Failed to update VM');
    },

    async delete(vmId: number): Promise<void> {
      const response = await apiClient.delete<ApiResponse<void>>(`/vms/${vmId}`);
      
      if (!response.data.success) {
        throw new Error(response.data.error?.message || 'Failed to delete VM');
      }
    },

    async search(query: string): Promise<SearchResult[]> {
      const response = await apiClient.get<ApiResponse<SearchResult[]>>('/vms/search', {
        params: { q: query },
      });
      return response.data.data || [];
    },
  },

  // Monitoring Data
  monitoring: {
    async getMetrics(vmId: number, limit: number = 100): Promise<Metric[]> {
      const response = await apiClient.get<ApiResponse<Metric[]>>(
        `/vms/${vmId}/metrics`,
        { params: { limit } }
      );
      return response.data.data || [];
    },

    async getPingHistory(vmId: number, limit: number = 100): Promise<PingResult[]> {
      const response = await apiClient.get<ApiResponse<PingResult[]>>(
        `/vms/${vmId}/ping`,
        { params: { limit } }
      );
      return response.data.data || [];
    },

    async getStatus(vmId: number): Promise<{ is_reachable: boolean; last_seen?: string }> {
      const response = await apiClient.get<ApiResponse<{ is_reachable: boolean; last_seen?: string }>>(
        `/vms/${vmId}/status`
      );
      
      if (response.data.success && response.data.data) {
        return response.data.data;
      }
      
      throw new Error('Failed to fetch VM status');
    },
  },

  // Alert Configuration
  alerts: {
    async getConfig(vmId: number): Promise<AlertConfig> {
      const response = await apiClient.get<ApiResponse<AlertConfig>>(
        `/vms/${vmId}/alerts/config`
      );
      
      if (response.data.success && response.data.data) {
        return response.data.data;
      }
      
      throw new Error('Failed to fetch alert config');
    },

    async updateConfig(vmId: number, config: AlertConfig): Promise<AlertConfig> {
      const response = await apiClient.put<ApiResponse<AlertConfig>>(
        `/vms/${vmId}/alerts/config`,
        config
      );
      
      if (response.data.success && response.data.data) {
        return response.data.data;
      }
      
      throw new Error('Failed to update alert config');
    },

    async getHistory(vmId: number): Promise<Alert[]> {
      const response = await apiClient.get<ApiResponse<Alert[]>>(
        `/vms/${vmId}/alerts/history`
      );
      return response.data.data || [];
    },
  },

  // Dashboard
  dashboard: {
    async getSummary(): Promise<VM[]> {
      const response = await apiClient.get<ApiResponse<VM[]>>('/dashboard');
      return response.data.data || [];
    },
  },
};

export default apiClient;
