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
  
  const { data, isLoading, isError, refetch } = useQuery({
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
      alert('Resources updated successfully.');
    },
    onError: (err: any) => {
      alert(`Failed to update resources: ${err.message || err}`);
    }
  });

  if (isLoading) return <div className="p-4 text-center text-gray-400">Loading resources...</div>;
  if (isError || !data) return <div className="p-4 text-center text-red-400">Failed to load resources.</div>;

  const { resources, provider } = data;
  const isReadOnly = provider === 'lxc-utils';

  const handleEditClick = () => {
    setFormData({
      cpu_cores: resources.cpu_cores,
      memory_mb: resources.memory_mb,
      swap_mb: resources.swap_mb,
      disk_gb: resources.disk_gb,
    });
    setIsEditing(true);
  };

  const handleSave = () => {
    if (window.confirm("Updating resources might require a container restart to take full effect. Continue?")) {
      updateMutation.mutate(formData);
    }
  };

  const MetricBox = ({ label, value, unit }: { label: string, value: any, unit: string }) => (
    <div className="bg-surface-800/50 rounded-lg p-4 border border-white/5">
      <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-lg font-bold text-white font-mono">
        {value != null ? `${value} ${unit}` : 'N/A'}
      </p>
    </div>
  );

  return (
    <div className="mt-4 p-5 bg-surface-900/60 rounded-lg border border-white/10">
      <div className="flex justify-between items-center mb-6">
        <h4 className="text-lg font-semibold text-white">Resource Limits</h4>
        {!isEditing ? (
          <button 
            onClick={handleEditClick}
            disabled={isReadOnly}
            title={isReadOnly ? "Editing limits not supported for pure LXC provider" : ""}
            className={`px-3 py-1.5 text-sm rounded border ${
              isReadOnly 
                ? 'bg-surface-800 text-gray-500 border-white/5 cursor-not-allowed'
                : 'bg-brand-500/10 text-brand-400 border-brand-500/20 hover:bg-brand-500/20 transition-colors'
            }`}
          >
            Edit Limits
          </button>
        ) : (
          <div className="flex gap-2">
            <button 
              onClick={() => setIsEditing(false)}
              className="px-3 py-1.5 text-sm rounded bg-surface-700 text-white border border-white/10 hover:bg-surface-600"
            >
              Cancel
            </button>
            <button 
              onClick={handleSave}
              disabled={updateMutation.isPending}
              className="px-3 py-1.5 text-sm rounded bg-brand-500 hover:bg-brand-600 text-white transition-colors"
            >
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        )}
      </div>

      {!isEditing ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricBox label="CPU Cores" value={resources.cpu_cores} unit="Cores" />
          <MetricBox label="Memory" value={resources.memory_mb} unit="MB" />
          <MetricBox label="Swap" value={resources.swap_mb} unit="MB" />
          <MetricBox label="Disk Size" value={resources.disk_gb} unit="GB" />
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs text-gray-400 uppercase tracking-wider mb-2">CPU Cores</label>
            <input 
              type="number" 
              className="w-full bg-surface-800 border border-white/10 rounded px-3 py-2 text-white font-mono"
              value={formData.cpu_cores || ''}
              onChange={e => setFormData({...formData, cpu_cores: e.target.value ? parseInt(e.target.value) : undefined})}
              min={1} max={128}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 uppercase tracking-wider mb-2">Memory (MB)</label>
            <input 
              type="number" 
              className="w-full bg-surface-800 border border-white/10 rounded px-3 py-2 text-white font-mono"
              value={formData.memory_mb || ''}
              onChange={e => setFormData({...formData, memory_mb: e.target.value ? parseInt(e.target.value) : undefined})}
              min={64}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 uppercase tracking-wider mb-2">Swap (MB)</label>
            <input 
              type="number" 
              className="w-full bg-surface-800 border border-white/10 rounded px-3 py-2 text-white font-mono"
              value={formData.swap_mb || ''}
              onChange={e => setFormData({...formData, swap_mb: e.target.value ? parseInt(e.target.value) : undefined})}
              min={0}
            />
            {provider === 'lxd' && <p className="text-[10px] text-yellow-500 mt-1">LXD swap editing may not be supported directly.</p>}
          </div>
          <div>
            <label className="block text-xs text-gray-400 uppercase tracking-wider mb-2">Disk Size (GB)</label>
            <input 
              type="number" 
              className="w-full bg-surface-800 border border-white/10 rounded px-3 py-2 text-white font-mono"
              value={formData.disk_gb || ''}
              onChange={e => setFormData({...formData, disk_gb: e.target.value ? parseFloat(e.target.value) : undefined})}
              min={1} step={0.1}
            />
            <p className="text-[10px] text-red-400 mt-1">Warning: Disks can usually only be grown, not shrunk.</p>
          </div>
        </div>
      )}
    </div>
  );
}
