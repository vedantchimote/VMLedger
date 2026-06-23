import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { ProcessInfo } from '@/types/api';

interface ProcessPanelProps {
  vmId: number;
  lxcId: string;
}

export function ProcessPanel({ vmId, lxcId }: ProcessPanelProps) {
  const queryClient = useQueryClient();
  const [sort, setSort] = useState<string>("cpu");
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [autoRefresh, setAutoRefresh] = useState<boolean>(false);
  const [killingPid, setKillingPid] = useState<number | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['processes', vmId, lxcId, sort],
    queryFn: () => api.processes.list(vmId, lxcId, sort, 50),
    refetchInterval: autoRefresh ? 5000 : false,
    enabled: !!vmId && !!lxcId,
  });

  const killMutation = useMutation({
    mutationFn: ({ pid, signal }: { pid: number, signal: string }) => 
      api.processes.kill(vmId, lxcId, pid, signal),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['processes', vmId, lxcId] });
      setKillingPid(null);
    },
    onError: (err) => {
      alert(`Failed to kill process: ${err}`);
      setKillingPid(null);
    }
  });

  const handleKill = (pid: number) => {
    if (window.confirm(`Are you sure you want to terminate process ${pid}?`)) {
      setKillingPid(pid);
      killMutation.mutate({ pid, signal: "TERM" });
    }
  };

  const processes = data?.processes || [];
  const filteredProcesses = processes.filter(p => 
    p.command.toLowerCase().includes(searchTerm.toLowerCase()) || 
    p.user.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.pid.toString().includes(searchTerm)
  );

  return (
    <div className="mt-4 p-4 bg-surface-900/60 rounded-lg border border-white/10">
      <div className="flex justify-between items-center mb-4">
        <h4 className="text-lg font-semibold text-white">Process Monitor</h4>
        <div className="flex items-center gap-4">
          <input
            type="text"
            placeholder="Search processes..."
            className="px-3 py-1.5 bg-surface-800 border border-white/10 rounded-md text-sm text-white"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />
          <select 
            className="bg-surface-800 border border-white/10 text-white text-sm rounded-md px-2 py-1.5"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="cpu">Sort by CPU %</option>
            <option value="mem">Sort by RAM %</option>
            <option value="pid">Sort by PID</option>
          </select>
          <label className="flex items-center gap-2 text-sm text-gray-300">
            <input 
              type="checkbox" 
              checked={autoRefresh} 
              onChange={e => setAutoRefresh(e.target.checked)}
              className="rounded bg-surface-800 border-white/20 text-brand-500"
            />
            Auto-refresh (5s)
          </label>
          <button 
            onClick={() => refetch()} 
            className="px-3 py-1.5 bg-surface-800 hover:bg-surface-700 text-white rounded-md text-sm border border-white/10"
          >
            Refresh
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-gray-400">Loading processes...</div>
      ) : isError ? (
        <div className="text-center py-8 text-red-400">Failed to load processes. Ensure VM is reachable and container is running.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-gray-400 uppercase bg-surface-800/50">
              <tr>
                <th className="px-4 py-3 rounded-tl-lg">PID</th>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3 text-right">CPU %</th>
                <th className="px-4 py-3 text-right">MEM %</th>
                <th className="px-4 py-3">Command</th>
                <th className="px-4 py-3 rounded-tr-lg text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredProcesses.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                    No processes found
                  </td>
                </tr>
              ) : (
                filteredProcesses.map(p => (
                  <tr key={p.pid} className="border-b border-white/5 hover:bg-surface-800/30">
                    <td className="px-4 py-3 font-mono text-gray-300">{p.pid}</td>
                    <td className="px-4 py-3 text-gray-300">{p.user}</td>
                    <td className="px-4 py-3 text-right font-mono">
                      <span className={p.cpu_percent > 80 ? "text-red-400 font-bold" : p.cpu_percent > 20 ? "text-yellow-400" : "text-gray-300"}>
                        {p.cpu_percent.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-300">{p.mem_percent.toFixed(1)}</td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-400 truncate max-w-[300px]" title={p.command}>
                      {p.command}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {p.pid !== 1 ? (
                        <button
                          onClick={() => handleKill(p.pid)}
                          disabled={killingPid === p.pid}
                          className="px-2 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded border border-red-500/20 text-xs transition-colors"
                        >
                          {killingPid === p.pid ? "Killing..." : "Kill"}
                        </button>
                      ) : (
                        <span className="text-xs text-gray-500 italic">init</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
