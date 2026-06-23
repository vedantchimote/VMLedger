import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';

/**
 * Query Keys for Monitoring Data
 */
export const monitoringKeys = {
  all: ['monitoring'] as const,
  metrics: (vmId: number, limit?: number) => [...monitoringKeys.all, 'metrics', vmId, limit] as const,
  ping: (vmId: number, limit?: number) => [...monitoringKeys.all, 'ping', vmId, limit] as const,
  status: (vmId: number) => [...monitoringKeys.all, 'status', vmId] as const,
  uptime: (vmId: number, period: string) => [...monitoringKeys.all, 'uptime', vmId, period] as const,
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

/**
 * Hook to fetch uptime SLA for a specific VM
 */
export function useVmUptime(vmId: number, period: string = "30d") {
  return useQuery({
    queryKey: monitoringKeys.uptime(vmId, period),
    queryFn: () => api.uptime.getVmUptime(vmId, period),
    enabled: !!vmId,
    refetchInterval: 5 * 60 * 1000, // Refresh every 5 mins
  });
}
