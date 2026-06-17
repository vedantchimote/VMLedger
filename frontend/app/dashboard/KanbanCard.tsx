import Link from "next/link";
import type { VM } from "@/types/api";

export function KanbanCard({ vm, router }: { vm: VM; router: any }) {
  const formatMetric = (value: number | undefined, suffix: string = ""): string => {
    if (value === undefined || value === null) return "N/A";
    return `${value}${suffix}`;
  };

  return (
    <div className="glass-card p-4 group border border-transparent hover:border-white/10 transition-colors">
      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="flex items-center gap-2 mb-3">
            <span className={`w-2 h-2 rounded-full ${vm.is_reachable === true ? "bg-brand-500 animate-pulse shadow-[0_0_8px_rgba(20,184,166,0.8)]" : vm.is_reachable === false ? "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]" : "bg-gray-500"}`}></span>
            <Link href={`/vms/${vm.id}`} className="text-sm font-bold text-white truncate tracking-tight hover:text-brand-300 transition-colors">
              {vm.hostname}
            </Link>
          </div>
          <span className="text-xs font-mono text-gray-500">{vm.ip_address}</span>
        </div>
      </div>
      <div className="space-y-2 mb-4 bg-surface-900/30 p-2 rounded-lg">
        <div className="flex justify-between items-center text-[10px]">
          <span className="text-gray-400 uppercase font-semibold tracking-wider">CPU</span>
          <span className="font-mono font-bold text-white">{formatMetric(vm.latest_cpu, "%")}</span>
        </div>
        <div className="flex justify-between items-center text-[10px]">
          <span className="text-gray-400 uppercase font-semibold tracking-wider">RAM</span>
          <span className="font-mono font-bold text-white">
            {vm.latest_ram_used !== undefined && vm.latest_ram_total !== undefined && vm.latest_ram_total > 0
              ? `${Math.round((vm.latest_ram_used / vm.latest_ram_total) * 100)}%`
              : "N/A"}
          </span>
        </div>
        <div className="flex justify-between items-center text-[10px]">
          <span className="text-gray-400 uppercase font-semibold tracking-wider">Disk</span>
          <span className="font-mono font-bold text-white">{formatMetric(vm.latest_disk_percent, "%")}</span>
        </div>
      </div>
      <div className="flex gap-2 mt-2">
        <Link
          href={`/vms/${vm.id}/terminal`}
          className="flex-1 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-white/5 flex items-center justify-center gap-1.5"
          title="Quick Connect (SSH)"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </Link>
        <Link
          href={`/vms/${vm.id}/edit`}
          className="flex-1 py-1.5 bg-surface-800 hover:bg-surface-700 text-gray-300 hover:text-white rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-white/5 flex items-center justify-center gap-1.5"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
          </svg>
        </Link>
        <button onClick={() => router.push(`/vms/${vm.id}`)} className="flex-[2] py-1.5 bg-brand-500/10 hover:bg-brand-500/20 text-brand-400 hover:text-brand-300 rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-brand-500/20 text-center">
          Metrics
        </button>
      </div>
    </div>
  );
}
