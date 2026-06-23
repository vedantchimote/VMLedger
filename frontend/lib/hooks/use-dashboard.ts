import { useQuery } from '@tanstack/react-query';
import { api, tokenManager } from '@/lib/api-client';

/**
 * Query Keys for Dashboard
 */
export const dashboardKeys = {
  all: ['dashboard'] as const,
  summary: () => [...dashboardKeys.all, 'summary'] as const,
  uptime: (period: string) => [...dashboardKeys.all, 'uptime', period] as const,
};

/**
 * Hook to fetch dashboard summary
 * Auto-refreshes every 30 seconds as per requirements
 */
export function useDashboard() {
  return useQuery({
    queryKey: dashboardKeys.summary(),
    queryFn: () => api.dashboard.getSummary(),
    // Only fetch when authenticated
    enabled: tokenManager.isAuthenticated(),
    // Auto-refresh every 30 seconds (Requirement 12.6)
    refetchInterval: 30 * 1000,
    // Keep previous data while refetching for smooth UX
    placeholderData: (previousData: any) => previousData,
    // Don't retry on 401
    retry: (failureCount, error: any) => {
      if (error?.response?.status === 401) return false;
      return failureCount < 3;
    },
  });
}

/**
 * Hook to fetch uptime summary for all VMs
 */
export function useUptimeSummary(period: string = "30d") {
  return useQuery({
    queryKey: dashboardKeys.uptime(period),
    queryFn: () => api.uptime.getUptimeSummary(period),
    enabled: tokenManager.isAuthenticated(),
    refetchInterval: 60 * 60 * 1000, // Refresh every hour
    placeholderData: (previousData: any) => previousData,
  });
}
