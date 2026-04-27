import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';

/**
 * Query Keys for Monitoring Data
 */
export const monitoringKeys = {
  all: ['monitoring'] as const,
  metrics: (vmId: number) => [...monitoringKeys.all, 'metrics', vmId] as const,
  ping: (vmId: number) => [...monitoringKeys.all, 'ping', vmId] as const,
  status: (vmId: number) => [...monitoringKeys.all, 'status', vmId] as const,
};

/**
 * Hook to fetch VM metrics
 */
export function useVMMetrics(vmId: number, limit: number = 100) {
  return useQuery({
    queryKey: monitoringKeys.metrics(vmId),
    queryFn: () => api.monitoring.getMetrics(vmId, limit),
    enabled: !!vmId,
    // Refetch every 30 seconds for real-time updates
    refetchInterval: 30 * 1000,
  });
}

/**
 * Hook to fetch VM ping history
 */
export function useVMPingHistory(vmId: number, limit: number = 100) {
  return useQuery({
    queryKey: monitoringKeys.ping(vmId),
    queryFn: () => api.monitoring.getPingHistory(vmId, limit),
    enabled: !!vmId,
    // Refetch every 30 seconds for real-time updates
    refetchInterval: 30 * 1000,
  });
}

/**
 * Hook to fetch VM status
 */
export function useVMStatus(vmId: number) {
  return useQuery({
    queryKey: monitoringKeys.status(vmId),
    queryFn: () => api.monitoring.getStatus(vmId),
    enabled: !!vmId,
    // Refetch every 30 seconds for real-time updates
    refetchInterval: 30 * 1000,
  });
}
