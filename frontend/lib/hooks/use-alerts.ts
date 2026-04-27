import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { AlertConfig } from '@/types/api';

/**
 * Query Keys for React Query
 */
export const alertKeys = {
  all: ['alerts'] as const,
  configs: () => [...alertKeys.all, 'config'] as const,
  config: (vmId: number) => [...alertKeys.configs(), vmId] as const,
  histories: () => [...alertKeys.all, 'history'] as const,
  history: (vmId: number) => [...alertKeys.histories(), vmId] as const,
};

/**
 * Hook to fetch alert configuration for a VM
 */
export function useAlertConfig(vmId: number) {
  return useQuery({
    queryKey: alertKeys.config(vmId),
    queryFn: () => api.alerts.getConfig(vmId),
    enabled: !!vmId,
  });
}

/**
 * Hook to fetch alert history for a VM
 */
export function useAlertHistory(vmId: number) {
  return useQuery({
    queryKey: alertKeys.history(vmId),
    queryFn: () => api.alerts.getHistory(vmId),
    enabled: !!vmId,
  });
}

/**
 * Hook to update alert configuration
 */
export function useUpdateAlertConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ vmId, config }: { vmId: number; config: AlertConfig }) =>
      api.alerts.updateConfig(vmId, config),
    onSuccess: (data, variables) => {
      // Invalidate alert config query
      queryClient.invalidateQueries({ queryKey: alertKeys.config(variables.vmId) });
    },
  });
}
