import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { VMCreateRequest, VMUpdateRequest } from '@/types/api';

/**
 * Query Keys for React Query
 */
export const vmKeys = {
  all: ['vms'] as const,
  lists: () => [...vmKeys.all, 'list'] as const,
  list: (filters?: Record<string, unknown>) => [...vmKeys.lists(), filters] as const,
  details: () => [...vmKeys.all, 'detail'] as const,
  detail: (id: number) => [...vmKeys.details(), id] as const,
  search: (query: string) => [...vmKeys.all, 'search', query] as const,
};

/**
 * Hook to fetch all VMs
 */
export function useVMs() {
  return useQuery({
    queryKey: vmKeys.lists(),
    queryFn: () => api.vms.list(),
  });
}

/**
 * Hook to fetch a single VM by ID
 */
export function useVM(vmId: number) {
  return useQuery({
    queryKey: vmKeys.detail(vmId),
    queryFn: () => api.vms.get(vmId),
    enabled: !!vmId,
  });
}

/**
 * Hook to fetch VM Specs
 */
export function useVMSpecs(vmId: number) {
  return useQuery({
    queryKey: [...vmKeys.detail(vmId), 'specs'],
    queryFn: () => api.vms.getSpecs(vmId),
    enabled: !!vmId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to search VMs
 */
export function useVMSearch(query: string) {
  return useQuery({
    queryKey: vmKeys.search(query),
    queryFn: () => api.vms.search(query),
    enabled: query.length > 0,
    // Debounce search queries
    staleTime: 300,
  });
}

/**
 * Hook to create a new VM
 */
export function useCreateVM() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (vmData: VMCreateRequest) => api.vms.create(vmData),
    onSuccess: () => {
      // Invalidate and refetch VM list
      queryClient.invalidateQueries({ queryKey: vmKeys.lists() });
    },
  });
}

/**
 * Hook to update a VM
 */
export function useUpdateVM() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ vmId, vmData }: { vmId: number; vmData: VMUpdateRequest }) =>
      api.vms.update(vmId, vmData),
    onSuccess: (data, variables) => {
      // Invalidate specific VM and list
      queryClient.invalidateQueries({ queryKey: vmKeys.detail(variables.vmId) });
      queryClient.invalidateQueries({ queryKey: vmKeys.lists() });
    },
  });
}

/**
 * Hook to delete a VM
 */
export function useDeleteVM() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (vmId: number) => api.vms.delete(vmId),
    onSuccess: () => {
      // Invalidate VM list
      queryClient.invalidateQueries({ queryKey: vmKeys.lists() });
    },
  });
}
