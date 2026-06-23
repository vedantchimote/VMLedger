import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { LxcResourcesResponse, UpdateLxcResourcesRequest } from '@/types/api';

interface ResourcePanelProps {
  vmId: number;
  lxcId: string;
}

export function ResourcePanel({ vmId, lxcId }: ResourcePanelProps) {
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<UpdateLxcResourcesRequest>({});
  
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['lxc-resources', vmId, lxcId],
    queryFn: () => api.lxc.getResources(vmId, lxcId),
    enabled: !!vmId && !!lxcId,
  });

  const updateMutation = useMutation({
    mutationFn: (updateData: UpdateLxcResourcesRequest) => 
      api.lxc.updateResources(vmId, lxcId, updateData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lxc-resources', vmId, lxcId] });
      setIsEditing(false);
    },
    onError: (err: any) => {
      alert(`Failed to update resources: ${err.message || err}`);
    }
  });

  if (isLoading) return (
    <div className="flex items-center justify-center gap-2 py-8 text-gray-500 text-sm">
      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      </svg>
      Loading resources...
    </div>
  );
  if (isError || !data) return (
    <div className="py-6 text-center">
      <p className="text-red-400 text-sm">Failed to load resources.</p>
      <p className="text-gray-500 text-xs mt-1">Ensure the VM is reachable and the container is running.</p>
    </div>
  );

  const { resources, provider } = data;
  const isReadOnly = provider === 'lxc-utils';

  const handleEditClick = () => {
    setFormData({
      cpu_cores: resources.cpu_cores ?? undefined,
      memory_mb: resources.memory_mb ?? undefined,
      swap_mb: resources.swap_mb ?? undefined,
      disk_gb: resources.disk_gb ?? undefined,
    });
    setIsEditing(true);
  };

  const handleSave = () => {
    if (window.confirm("Updating resources might require a container restart to take full effect. Continue?")) {
      updateMutation.mutate(formData);
    }
  };

  const MetricBox = ({ label, value, unit, sub }: { label: string, value: any, unit: string, sub?: string }) => (
    <div className="bg-surface-800/50 rounded-lg p-3 border border-white/5">
      <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-base font-bold text-white font-mono">
        {value != null ? <>{value} <span className="text-xs text-gray-400 font-normal">{unit}</span></> : <span className="text-gray-600">N/A</span>}
      </p>
      {sub && <p className="text-[10px] text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          <h4 className="text-sm font-semibold text-white">Resource Limits</h4>
          <span className="text-[10px] text-gray-500 bg-surface-800 px-1.5 py-0.5 rounded">{provider}</span>
        </div>
        <div className="flex items-center gap-2">
          {!isEditing ? (
            <>
              <button 
                onClick={() => refetch()} 
                disabled={isFetching}
                className="px-2 py-1 text-xs rounded bg-surface-800 hover:bg-surface-700 text-gray-300 border border-white/10 transition-colors disabled:opacity-50"
              >
                {isFetching ? '...' : 'Refresh'}
              </button>
              <button 
                onClick={handleEditClick}
                disabled={isReadOnly}
                title={isReadOnly ? "Editing limits not supported for pure LXC provider" : ""}
                className={`px-2 py-1 text-xs rounded border ${
                  isReadOnly 
                    ? 'bg-surface-800 text-gray-600 border-white/5 cursor-not-allowed'
                    : 'bg-brand-500/10 text-brand-400 border-brand-500/20 hover:bg-brand-500/20 transition-colors'
                }`}
              >
                Edit Limits
              </button>
            </>
          ) : (
            <>
              <button 
                onClick={() => setIsEditing(false)}
                className="px-2 py-1 text-xs rounded bg-surface-700 text-white border border-white/10 hover:bg-surface-600"
              >
                Cancel
              </button>
              <button 
                onClick={handleSave}
                disabled={updateMutation.isPending}
                className="px-2 py-1 text-xs rounded bg-brand-500 hover:bg-brand-600 text-white transition-colors disabled:opacity-50"
              >
                {updateMutation.isPending ? 'Saving...' : 'Save'}
              </button>
            </>
          )}
        </div>
      </div>

      {!isEditing ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricBox label="CPU Cores" value={resources.cpu_cores} unit="Cores" />
          <MetricBox 
            label="Memory" 
            value={resources.memory_mb != null ? (resources.memory_mb >= 1024 ? `${(resources.memory_mb / 1024).toFixed(1)}` : resources.memory_mb) : null} 
            unit={resources.memory_mb != null && resources.memory_mb >= 1024 ? "GB" : "MB"} 
          />
          <MetricBox 
            label="Swap" 
            value={resources.swap_mb} 
            unit="MB" 
            sub={resources.swap_mb === 0 ? "Disabled" : undefined}
          />
          <MetricBox 
            label="Disk Size" 
            value={resources.disk_gb} 
            unit="GB"
            sub={resources.disk_used_gb != null ? `Used: ${resources.disk_used_gb} GB` : undefined}
          />
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">CPU Cores</label>
            <input 
              type="number" 
              className="w-full bg-surface-800 border border-white/10 rounded px-3 py-2 text-sm text-white font-mono focus:border-brand-500 focus:outline-none"
              value={formData.cpu_cores || ''}
              onChange={e => setFormData({...formData, cpu_cores: e.target.value ? parseInt(e.target.value) : undefined})}
              min={1} max={128}
            />
          </div>
          <div>
            <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Memory (MB)</label>
            <input 
              type="number" 
              className="w-full bg-surface-800 border border-white/10 rounded px-3 py-2 text-sm text-white font-mono focus:border-brand-500 focus:outline-none"
              value={formData.memory_mb || ''}
              onChange={e => setFormData({...formData, memory_mb: e.target.value ? parseInt(e.target.value) : undefined})}
              min={64}
            />
          </div>
          <div>
            <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Swap (MB)</label>
            <input 
              type="number" 
              className="w-full bg-surface-800 border border-white/10 rounded px-3 py-2 text-sm text-white font-mono focus:border-brand-500 focus:outline-none"
              value={formData.swap_mb || ''}
              onChange={e => setFormData({...formData, swap_mb: e.target.value ? parseInt(e.target.value) : undefined})}
              min={0}
            />
            {provider === 'lxd' && <p className="text-[10px] text-yellow-500 mt-1">LXD may not support swap limits.</p>}
          </div>
          <div>
            <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Disk Size (GB)</label>
            <input 
              type="number" 
              className="w-full bg-surface-800 border border-white/10 rounded px-3 py-2 text-sm text-white font-mono focus:border-brand-500 focus:outline-none"
              value={formData.disk_gb || ''}
              onChange={e => setFormData({...formData, disk_gb: e.target.value ? parseFloat(e.target.value) : undefined})}
              min={1} step={0.1}
            />
            <p className="text-[10px] text-red-400 mt-1">Disks can usually only grow.</p>
          </div>
        </div>
      )}
    </div>
  );
}
