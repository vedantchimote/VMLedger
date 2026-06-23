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

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
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

  const totalCpu = filteredProcesses.reduce((sum, p) => sum + p.cpu_percent, 0);
  const totalMem = filteredProcesses.reduce((sum, p) => sum + p.mem_percent, 0);

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[180px] max-w-[260px]">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Filter by name, user, PID..."
            className="w-full pl-8 pr-3 py-1.5 bg-surface-900 border border-white/10 rounded-md text-xs text-white placeholder:text-gray-500 focus:border-brand-500 focus:outline-none"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />
        </div>
        <select 
          className="bg-surface-900 border border-white/10 text-gray-300 text-xs rounded-md px-2 py-1.5 focus:border-brand-500 focus:outline-none"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
        >
          <option value="cpu">Sort: CPU ↓</option>
          <option value="mem">Sort: MEM ↓</option>
          <option value="pid">Sort: PID ↑</option>
        </select>
        <label className="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer select-none">
          <input 
            type="checkbox" 
            checked={autoRefresh} 
            onChange={e => setAutoRefresh(e.target.checked)}
            className="rounded bg-surface-800 border-white/20 text-brand-500 w-3.5 h-3.5"
          />
          Auto 5s
        </label>
        <button 
          onClick={() => refetch()} 
          disabled={isFetching}
          className="px-2.5 py-1.5 bg-surface-800 hover:bg-surface-700 text-gray-300 hover:text-white rounded-md text-xs border border-white/10 transition-colors disabled:opacity-50 flex items-center gap-1.5"
        >
          <svg className={`w-3 h-3 ${isFetching ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {isFetching ? '' : 'Refresh'}
        </button>
      </div>

      {/* Summary strip */}
      {!isLoading && !isError && filteredProcesses.length > 0 && (
        <div className="flex items-center gap-4 text-[11px] text-gray-500 font-mono">
          <span>{filteredProcesses.length} processes</span>
          <span>CPU total: <span className={totalCpu > 50 ? "text-yellow-400" : "text-gray-300"}>{totalCpu.toFixed(1)}%</span></span>
          <span>MEM total: <span className={totalMem > 50 ? "text-yellow-400" : "text-gray-300"}>{totalMem.toFixed(1)}%</span></span>
        </div>
      )}

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center gap-2 py-8 text-gray-500 text-sm">
          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Loading processes...
        </div>
      ) : isError ? (
        <div className="py-6 text-center">
          <p className="text-red-400 text-sm">Failed to load processes.</p>
          <p className="text-gray-500 text-xs mt-1">Ensure the VM is reachable and the container is running.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-white/5">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-surface-800/80 text-[10px] text-gray-500 uppercase tracking-wider">
                <th className="px-3 py-2 w-[60px]">PID</th>
                <th className="px-3 py-2 w-[80px]">User</th>
                <th className="px-3 py-2 text-right w-[60px]">CPU%</th>
                <th className="px-3 py-2 text-right w-[60px]">MEM%</th>
                <th className="px-3 py-2 w-[70px]">RSS</th>
                <th className="px-3 py-2 w-[50px]">Stat</th>
                <th className="px-3 py-2">Command</th>
                <th className="px-3 py-2 text-right w-[50px]"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filteredProcesses.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-3 py-6 text-center text-gray-500 text-xs">
                    No processes match your filter.
                  </td>
                </tr>
              ) : (
                filteredProcesses.map(p => (
                  <tr key={p.pid} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-3 py-1.5 font-mono text-gray-400">{p.pid}</td>
                    <td className="px-3 py-1.5 text-gray-400">{p.user}</td>
                    <td className="px-3 py-1.5 text-right font-mono">
                      <span className={
                        p.cpu_percent > 80 ? "text-red-400 font-bold" : 
                        p.cpu_percent > 20 ? "text-yellow-400" : 
                        p.cpu_percent > 0 ? "text-brand-400" : "text-gray-500"
                      }>
                        {p.cpu_percent.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono">
                      <span className={
                        p.mem_percent > 50 ? "text-red-400 font-bold" : 
                        p.mem_percent > 20 ? "text-yellow-400" : 
                        p.mem_percent > 0 ? "text-blue-400" : "text-gray-500"
                      }>
                        {p.mem_percent.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 font-mono text-gray-500 text-[10px]">
                      {p.rss_kb > 1024 ? `${(p.rss_kb / 1024).toFixed(0)}M` : `${p.rss_kb}K`}
                    </td>
                    <td className="px-3 py-1.5 text-gray-500">{p.stat}</td>
                    <td className="px-3 py-1.5 font-mono text-gray-400 truncate max-w-[200px]" title={p.command}>
                      {p.command}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      {p.pid > 1 ? (
                        <button
                          onClick={() => handleKill(p.pid)}
                          disabled={killingPid === p.pid}
                          className="px-1.5 py-0.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded border border-red-500/20 text-[10px] font-medium transition-colors disabled:opacity-50"
                          title={`Kill PID ${p.pid}`}
                        >
                          {killingPid === p.pid ? "..." : "Kill"}
                        </button>
                      ) : (
                        <span className="text-[10px] text-gray-600">init</span>
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
