import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';

/**
 * Query Keys for Dashboard
 */
export const dashboardKeys = {
  all: ['dashboard'] as const,
  summary: () => [...dashboardKeys.all, 'summary'] as const,
};

/**
 * Hook to fetch dashboard summary
 * Auto-refreshes every 30 seconds as per requirements
 */
export function useDashboard() {
  return useQuery({
    queryKey: dashboardKeys.summary(),
    queryFn: () => api.dashboard.getSummary(),
    // Auto-refresh every 30 seconds (Requirement 12.6)
    refetchInterval: 30 * 1000,
    // Keep previous data while refetching for smooth UX
    placeholderData: (previousData) => previousData,
  });
}
