"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { formatDistanceToNow, format } from "date-fns";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api-client";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useAuth } from "@/lib/hooks/use-auth";
import { useVM, useVMSpecs } from "@/lib/hooks/use-vms";
import { useVMMetrics, useVMPingHistory, useVmUptime } from "@/lib/hooks/use-monitoring";
import { UptimeBadge } from "@/components/UptimeBadge";
import { ProcessPanel } from "@/components/ProcessPanel";
import { ResourcePanel } from "@/components/ResourcePanel";
import { NetworkTopology } from "@/components/NetworkTopology";
import {
  useAlertConfig,
  useAlertHistory,
  useUpdateAlertConfig,
} from "@/lib/hooks/use-alerts";
import type { Metric, PingResult, VM, Alert, AlertConfig } from "@/types/api";
import {
  isValidWebhookURL,
  isValidEmail,
  isValidCooldownPeriod,
} from "@/lib/validation";
import GlobalNotificationBell from "@/components/GlobalNotificationBell";

type TabType = "overview" | "specs" | "metrics" | "ping" | "notes" | "alerts" | "services" | "containers" | "network";
type TriggerType = "ping" | "dns" | "metrics" | "services";

export default function VMDetailsPage() {
  const router = useRouter();
  const params = useParams();
  const vmId = parseInt(params.id as string, 10);
  const { isAuthenticated, isMounted } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>("overview");

  // Manual trigger states
  const [triggerLoading, setTriggerLoading] = useState<Record<TriggerType, boolean>>({
    ping: false,
    dns: false,
    metrics: false,
  });
  const [triggerFeedback, setTriggerFeedback] = useState<{ type: TriggerType; message: string; success: boolean } | null>(null);

  // Fetch VM data
  const { data: vm, isLoading: vmLoading, isError: vmError, refetch: refetchVM } = useVM(vmId);
  const { data: metrics, isLoading: metricsLoading, refetch: refetchMetrics } = useVMMetrics(vmId, 100);
  const { data: pingHistory, isLoading: pingLoading, refetch: refetchPing } = useVMPingHistory(
    vmId,
    100,
  );
  const [pingingAnimation, setPingingAnimation] = useState<TriggerType | null>(null);
  const { data: alertConfig, isLoading: alertConfigLoading } =
    useAlertConfig(vmId);
  const { data: alertHistory, isLoading: alertHistoryLoading } =
    useAlertHistory(vmId);
  const { data: uptimeData } = useVmUptime(vmId, "30d");

  useEffect(() => {
    if (isMounted && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isMounted, router]);

  // Clear trigger feedback after 4 seconds
  useEffect(() => {
    if (triggerFeedback) {
      const timer = setTimeout(() => setTriggerFeedback(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [triggerFeedback]);

  const handleTrigger = useCallback(async (type: TriggerType) => {
    setTriggerLoading((prev) => ({ ...prev, [type]: true }));
    setTriggerFeedback(null);
    try {
      let result;
      switch (type) {
        case "ping":
          result = await api.triggers.triggerPing(vmId);
          break;
        case "dns":
          result = await api.triggers.triggerDnsCheck(vmId);
          break;
        case "metrics":
          result = await api.triggers.triggerCollectMetrics(vmId);
          break;
      }
      const labels: Record<TriggerType, string> = {
        ping: "Ping check",
        dns: "DNS resolution",
        metrics: "Metrics collection",
      };
      setTriggerFeedback({
        type,
        message: `${labels[type]} dispatched — refreshing data...`,
        success: true,
      });
      // Show pinging animation while waiting for backend to process
      setPingingAnimation(type);
      // Silently refetch data after a delay instead of full page reload
      setTimeout(async () => {
        try {
          if (type === 'ping') await refetchPing();
          if (type === 'metrics') await refetchMetrics();
          await refetchVM();
        } finally {
          setPingingAnimation(null);
        }
      }, 5000);
    } catch (err: any) {
      setTriggerFeedback({
        type,
        message: err?.message || "Failed to trigger task",
        success: false,
      });
    } finally {
      setTriggerLoading((prev) => ({ ...prev, [type]: false }));
    }
  }, [vmId, refetchPing, refetchMetrics, refetchVM]);

  if (!isMounted || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  if (vmLoading) {
    return (
      <div className="min-h-screen bg-gray-900">
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <svg
              className="animate-spin h-12 w-12 text-blue-500 mx-auto mb-4"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              ></circle>
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
            <p className="text-gray-400">Loading VM details...</p>
          </div>
        </div>
      </div>
    );
  }

  if (vmError || !vm) {
    return (
      <div className="min-h-screen bg-gray-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-6">
            <h3 className="text-red-200 font-semibold mb-2">VM Not Found</h3>
            <p className="text-red-300 text-sm mb-4">
              The requested VM could not be found or you don&apos;t have
              permission to view it.
            </p>
            <Link
              href="/dashboard"
              className="inline-block px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors duration-200 text-sm font-medium"
            >
              Back to Dashboard
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const getStatusColor = (isReachable: boolean | undefined): string => {
    if (isReachable === true) return "bg-green-500";
    if (isReachable === false) return "bg-red-500";
    return "bg-gray-500";
  };

  const getStatusText = (isReachable: boolean | undefined): string => {
    if (isReachable === true) return "Online";
    if (isReachable === false) return "Offline";
    return "Unknown";
  };

  const formatRelativeTime = (timestamp: string | undefined): string => {
    if (!timestamp) return "Never";
    try {
      return formatDistanceToNow(new Date(timestamp), { addSuffix: true });
    } catch {
      return "Unknown";
    }
  };

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-surface-950/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-4 min-w-0">
              <Link
                href="/dashboard"
                className="flex items-center justify-center w-9 h-9 rounded-lg bg-surface-800 border border-white/5 text-gray-400 hover:text-white hover:bg-surface-700 transition-all flex-shrink-0"
                aria-label="Back to Dashboard"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
              </Link>
              <div className="min-w-0">
                <div className="flex items-center gap-2.5">
                  <h1 className="text-lg font-bold text-white tracking-tight truncate">
                    {vm.hostname}
                  </h1>
                  <span
                    className={`flex-shrink-0 ${
                      vm.is_reachable === true
                        ? "status-badge-online"
                        : vm.is_reachable === false
                          ? "status-badge-offline"
                          : "status-badge-unknown"
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        vm.is_reachable === true
                          ? "bg-brand-500 animate-pulse"
                          : vm.is_reachable === false
                            ? "bg-red-500"
                            : "bg-gray-500"
                      }`}
                    ></span>
                    {getStatusText(vm.is_reachable)}
                  </span>
                </div>
                <div className="text-xs font-mono text-gray-500">{vm.ip_address}</div>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {/* Trigger Buttons - compact pill group */}
              <div className="hidden md:flex items-center gap-1.5 bg-surface-900/50 rounded-xl px-1.5 py-1 border border-white/5">
                <button
                  onClick={() => handleTrigger("ping")}
                  disabled={triggerLoading.ping}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-brand-400 hover:bg-brand-500/15 transition-all text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
                  title="Run an immediate connectivity check"
                >
                  {triggerLoading.ping ? (
                    <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                  ) : (
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                  )}
                  Ping
                </button>
                <div className="w-px h-4 bg-white/10"></div>
                <button
                  onClick={() => handleTrigger("dns")}
                  disabled={triggerLoading.dns}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-purple-400 hover:bg-purple-500/15 transition-all text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
                  title="Resolve hostname and compare with registered IP"
                >
                  {triggerLoading.dns ? (
                    <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                  ) : (
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" /></svg>
                  )}
                  DNS
                </button>
                <div className="w-px h-4 bg-white/10"></div>
                <button
                  onClick={() => handleTrigger("metrics")}
                  disabled={triggerLoading.metrics}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-cyan-400 hover:bg-cyan-500/15 transition-all text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
                  title="Collect CPU, RAM, and Disk usage via SSH"
                >
                  {triggerLoading.metrics ? (
                    <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                  ) : (
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                  )}
                  Metrics
                </button>
              </div>
              <div className="w-px h-6 bg-white/10 hidden md:block"></div>
              <GlobalNotificationBell />
              <Link href={`/vms/${vm.id}/terminal`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface-800 border border-white/5 text-gray-300 hover:text-white hover:bg-surface-700 transition-all text-xs font-semibold" title="Open SSH Terminal">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                Terminal
              </Link>
              <Link href={`/vms/${vm.id}/logs`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface-800 border border-white/5 text-gray-300 hover:text-white hover:bg-surface-700 transition-all text-xs font-semibold" title="View Live Logs">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>
                Logs
              </Link>
              <Link href={`/vms/${vm.id}/edit`} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface-800 border border-white/5 text-gray-300 hover:text-white hover:bg-surface-700 transition-all text-xs font-semibold" title="Edit VM Configuration">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
                Edit
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Pinging Animation Overlay */}
      {pingingAnimation && (
        <div className="fixed top-24 right-6 z-50 max-w-xs animate-fade-in">
          <div className="glass-card px-5 py-4 border border-brand-500/30 shadow-2xl shadow-brand-500/10">
            <div className="flex items-center gap-4">
              <div className="relative flex items-center justify-center w-10 h-10">
                <span className="absolute inline-flex w-full h-full rounded-full bg-brand-400/30 animate-ping" />
                <span className="absolute inline-flex w-6 h-6 rounded-full bg-brand-400/50 animate-ping" style={{ animationDelay: '0.3s' }} />
                <span className="relative inline-flex w-3 h-3 rounded-full bg-brand-400" />
              </div>
              <div>
                <p className="text-sm font-bold text-white">
                  {pingingAnimation === 'ping' ? 'Pinging...' : pingingAnimation === 'dns' ? 'Resolving DNS...' : 'Collecting Metrics...'}
                </p>
                <p className="text-[10px] text-gray-400 mt-0.5">Waiting for results — data will update automatically</p>
              </div>
            </div>
            <div className="mt-3 w-full bg-surface-800 rounded-full h-1 overflow-hidden">
              <div className="h-full bg-brand-500 rounded-full animate-progress-bar" style={{ animation: 'progressBar 5s linear forwards' }} />
            </div>
          </div>
        </div>
      )}

      {/* Trigger Feedback Toast */}
      {triggerFeedback && !pingingAnimation && (
        <div className={`fixed top-24 right-6 z-50 max-w-sm animate-fade-in px-5 py-4 rounded-xl border shadow-2xl backdrop-blur-xl ${
          triggerFeedback.success
            ? "bg-brand-500/10 border-brand-500/20 text-brand-400"
            : "bg-red-500/10 border-red-500/20 text-red-400"
        }`}>
          <div className="flex items-center gap-3">
            {triggerFeedback.success ? (
              <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            ) : (
              <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            )}
            <p className="text-sm font-medium">{triggerFeedback.message}</p>
            <button onClick={() => setTriggerFeedback(null)} className="ml-auto text-current opacity-60 hover:opacity-100">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 animate-fade-in">
        {/* VM Metadata Section */}
        <div className="glass-card p-5 mb-5">
          <h2 className="text-sm font-bold text-white tracking-tight mb-4 flex items-center uppercase">
            <svg className="w-4 h-4 mr-2 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            System Information
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-x-6 gap-y-4">
            <div>
              <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider mb-0.5">IP Address</p>
              <p className="text-white font-mono text-sm">{vm.ip_address}</p>
            </div>
            <div>
              <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider mb-0.5">SSH Port</p>
              <p className="text-white font-mono text-sm">{vm.ssh_port}</p>
            </div>
            <div>
              <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider mb-0.5">Domain</p>
              <p className="text-white text-sm">
                {vm.domain || <span className="text-gray-600 italic">—</span>}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider mb-0.5">Last Seen</p>
              <p className="text-white text-sm">{formatRelativeTime(vm.last_seen)}</p>
            </div>
            <div>
              <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider mb-0.5">Created</p>
              <p className="text-white text-sm">{formatRelativeTime(vm.created_at)}</p>
            </div>
          </div>
          {vm.tags && vm.tags.length > 0 && (
            <div className="mt-4 pt-4 border-t border-white/5">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[10px] font-medium text-gray-500 uppercase tracking-wider">Tags</span>
                <div className="h-3 w-px bg-white/10"></div>
                {vm.tags.map((tag, index) => (
                  <span key={index} className="px-2.5 py-0.5 bg-brand-500/10 text-brand-300 border border-brand-500/20 rounded-md text-[10px] font-semibold tracking-wider uppercase">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Uptime & DNS - Compact Two-Column */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
          {/* Uptime & SLA */}
          {uptimeData && (
            <div className="glass-card p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-bold text-white tracking-tight flex items-center uppercase">
                  <svg className="w-4 h-4 mr-2 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Uptime & SLA <span className="ml-1.5 text-[10px] text-gray-500 font-normal normal-case">({uptimeData.period})</span>
                </h2>
                <UptimeBadge uptimePercent={uptimeData.uptime_percent} slaTier={uptimeData.sla_tier} />
              </div>
              <div className="grid grid-cols-4 gap-3 mb-4">
                <div className="bg-surface-900/50 rounded-lg p-3 border border-white/5">
                  <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider mb-1">Checks</p>
                  <p className="text-white font-mono text-base font-bold">{uptimeData.total_checks.toLocaleString()}</p>
                </div>
                <div className="bg-surface-900/50 rounded-lg p-3 border border-white/5">
                  <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider mb-1">Failed</p>
                  <p className={`font-mono text-base font-bold ${uptimeData.failed_checks > 0 ? "text-red-400" : "text-emerald-400"}`}>
                    {uptimeData.failed_checks.toLocaleString()}
                  </p>
                </div>
                <div className="bg-surface-900/50 rounded-lg p-3 border border-white/5">
                  <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider mb-1">Avg Latency</p>
                  <p className="text-white font-mono text-base font-bold">
                    {uptimeData.avg_latency_ms !== null ? `${uptimeData.avg_latency_ms.toFixed(1)}ms` : "N/A"}
                  </p>
                </div>
                <div className="bg-surface-900/50 rounded-lg p-3 border border-white/5">
                  <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider mb-1">Max Latency</p>
                  <p className="text-white font-mono text-base font-bold">
                    {uptimeData.max_latency_ms !== null ? `${uptimeData.max_latency_ms.toFixed(1)}ms` : "N/A"}
                  </p>
                </div>
              </div>
              {uptimeData.daily_breakdown.length > 0 && (
                <div className="h-32">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={uptimeData.daily_breakdown}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                      <XAxis dataKey="date" stroke="#9CA3AF" tick={{fill: '#9CA3AF', fontSize: 10}} tickFormatter={(val) => format(new Date(val), 'MMM dd')} />
                      <YAxis domain={[90, 100]} stroke="#9CA3AF" tick={{fill: '#9CA3AF', fontSize: 10}} width={30} />
                      <Tooltip contentStyle={{ backgroundColor: '#1F2937', borderColor: '#374151', color: '#F3F4F6', fontSize: '12px' }} labelFormatter={(val) => format(new Date(val), 'MMM dd, yyyy')} formatter={(val: number) => [`${val.toFixed(2)}%`, 'Uptime']} />
                      <Line type="monotone" dataKey="uptime_percent" stroke="#10b981" strokeWidth={2} dot={{ r: 2, fill: '#10b981', strokeWidth: 0 }} activeDot={{ r: 4, fill: '#10b981', strokeWidth: 0 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )}

          {/* DNS Resolution */}
          <div className="glass-card p-5">
            <h2 className="text-sm font-bold text-white tracking-tight mb-4 flex items-center uppercase">
              <svg className="w-4 h-4 mr-2 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
              </svg>
              DNS Resolution
              {vm.dns_mismatch && (
                <span className="ml-2 px-2 py-0.5 bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 rounded text-[10px] font-bold uppercase tracking-wider animate-pulse">
                  Mismatch
                </span>
              )}
            </h2>
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-surface-900/50 rounded-lg p-3 border border-white/5">
                <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider mb-1">Registered IP</p>
                <p className="text-white font-mono text-sm font-bold">{vm.ip_address}</p>
              </div>
              <div className={`rounded-lg p-3 border ${vm.dns_mismatch ? "bg-yellow-500/5 border-yellow-500/20" : "bg-surface-900/50 border-white/5"}`}>
                <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider mb-1">Resolved IP</p>
                {vm.resolved_ip ? (
                  <p className={`font-mono text-sm font-bold ${vm.dns_mismatch ? "text-yellow-400" : "text-brand-400"}`}>
                    {vm.resolved_ip}
                    {vm.dns_mismatch && <span className="ml-1 text-yellow-500 text-[9px]">≠</span>}
                    {!vm.dns_mismatch && <span className="ml-1 text-brand-500 text-[9px]">✓</span>}
                  </p>
                ) : (
                  <p className="text-gray-600 italic text-sm">Not checked</p>
                )}
              </div>
              <div className="bg-surface-900/50 rounded-lg p-3 border border-white/5">
                <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider mb-1">Last Check</p>
                <p className="text-white text-sm">
                  {vm.dns_last_checked ? formatRelativeTime(vm.dns_last_checked) : <span className="text-gray-600 italic">Pending</span>}
                </p>
                <p className="text-[9px] text-gray-600 mt-0.5 uppercase tracking-wider">Every {vm.dns_interval_hours || 6}h</p>
              </div>
            </div>
            {vm.dns_mismatch && (
              <div className="mt-3 p-3 bg-yellow-500/5 border border-yellow-500/20 rounded-lg flex items-start gap-2">
                <svg className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
                <p className="text-xs text-yellow-400/80">
                  <span className="font-mono font-bold">{vm.hostname}</span> resolves to <span className="font-mono font-bold">{vm.resolved_ip}</span> instead of <span className="font-mono font-bold">{vm.ip_address}</span>.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Tabbed Interface */}
        <div className="glass-card overflow-visible">
          {/* Tab Headers */}
          <div className="border-b border-white/5 bg-surface-900/50 rounded-t-2xl">
            <nav className="flex overflow-x-auto hide-scrollbar">
              {["overview", "specs", "metrics", "ping", "notes", "alerts", "services", "containers", "network"].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab as TabType)}
                  className={`px-5 py-3.5 text-xs font-bold uppercase tracking-wider border-b-2 transition-all whitespace-nowrap ${
                    activeTab === tab
                      ? "border-brand-400 text-brand-400 bg-brand-500/5"
                      : "border-transparent text-gray-500 hover:text-white hover:bg-white/5"
                  }`}
                >
                  {tab.replace("_", " ")}
                </button>
              ))}
            </nav>
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {activeTab === "overview" && (
              <OverviewTab
                vm={vm}
                metrics={metrics}
                pingHistory={pingHistory}
              />
            )}
            {activeTab === "specs" && (
              <SpecsTab vmId={vmId} />
            )}
            {activeTab === "metrics" && (
              <MetricsTab metrics={metrics} isLoading={metricsLoading} />
            )}
            {activeTab === "ping" && (
              <PingHistoryTab
                pingHistory={pingHistory}
                isLoading={pingLoading}
              />
            )}
            {activeTab === "notes" && (
              <DeploymentNotesTab notes={vm.deployment_notes} />
            )}
            {activeTab === "alerts" && (
              <AlertsTab
                vmId={vmId}
                alertConfig={alertConfig}
                alertHistory={alertHistory}
                isConfigLoading={alertConfigLoading}
                isHistoryLoading={alertHistoryLoading}
              />
            )}
            {activeTab === "services" && (
              <ServicesTab vmId={vmId} />
            )}
            {activeTab === "containers" && (
              <ContainersTab vmId={vmId} />
            )}
            {activeTab === "network" && (
              <NetworkTab vmId={vmId} vm={vm} />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

// Overview Tab Component
function OverviewTab({
  vm,
  metrics,
  pingHistory,
}: {
  vm: VM;
  metrics?: Metric[];
  pingHistory?: PingResult[];
}) {
  const latestMetric = metrics && metrics.length > 0 ? metrics[0] : null;
  const recentPings = pingHistory ? pingHistory.slice(0, 10) : [];
  const cpuPct = latestMetric?.cpu_usage_percent ?? null;
  const ramPct = latestMetric?.ram_used_mb && latestMetric?.ram_total_mb && latestMetric.ram_total_mb > 0
    ? (latestMetric.ram_used_mb / latestMetric.ram_total_mb) * 100 : null;
  const diskPct = latestMetric?.disk_usage_percent ?? null;

  // Uptime calculation
  const totalPings = pingHistory?.length || 0;
  const successPings = pingHistory?.filter(p => p.success).length || 0;
  const uptimePct = totalPings > 0 ? ((successPings / totalPings) * 100) : null;
  const avgLatency = recentPings.filter(p => p.success && p.response_time_ms != null).length > 0
    ? recentPings.filter(p => p.success && p.response_time_ms != null).reduce((a, p) => a + (p.response_time_ms || 0), 0) / recentPings.filter(p => p.success && p.response_time_ms != null).length : null;

  const getRingColor = (pct: number) => pct >= 90 ? '#ef4444' : pct >= 75 ? '#f59e0b' : pct >= 50 ? '#3b82f6' : '#10b981';
  const getRingBg = (pct: number) => pct >= 90 ? 'rgba(239,68,68,0.1)' : pct >= 75 ? 'rgba(245,158,11,0.1)' : pct >= 50 ? 'rgba(59,130,246,0.1)' : 'rgba(16,185,129,0.1)';
  const getRingTextClass = (pct: number) => pct >= 90 ? 'text-red-400' : pct >= 75 ? 'text-amber-400' : pct >= 50 ? 'text-blue-400' : 'text-emerald-400';

  const RingGauge = ({ value, label, subtitle }: { value: number | null; label: string; subtitle?: string }) => {
    const pct = value ?? 0;
    const radius = 54;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (Math.min(pct, 100) / 100) * circumference;
    return (
      <div className="glass-card p-6 flex flex-col items-center border border-white/5 hover:border-white/10 transition-all group">
        <div className="relative w-32 h-32 mb-4">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
            {value != null && (
              <circle cx="60" cy="60" r={radius} fill="none" stroke={getRingColor(pct)} strokeWidth="8"
                strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset}
                style={{ transition: 'stroke-dashoffset 1s ease-out, stroke 0.5s ease' }} />
            )}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-2xl font-black font-mono ${value != null ? getRingTextClass(pct) : 'text-gray-500'}`}>
              {value != null ? `${Math.round(pct)}%` : 'N/A'}
            </span>
          </div>
        </div>
        <p className="text-xs font-bold text-gray-300 uppercase tracking-wider">{label}</p>
        {subtitle && <p className="text-[10px] text-gray-500 font-mono mt-1">{subtitle}</p>}
      </div>
    );
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Resource Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <RingGauge value={cpuPct} label="CPU Usage" subtitle={cpuPct != null ? `${cpuPct.toFixed(1)}%` : undefined} />
        <RingGauge value={ramPct} label="Memory Usage"
          subtitle={latestMetric?.ram_used_mb != null && latestMetric?.ram_total_mb != null
            ? `${latestMetric.ram_used_mb.toLocaleString()} / ${latestMetric.ram_total_mb.toLocaleString()} MB`
            : undefined}
        />
        <RingGauge value={diskPct} label="Disk Usage"
          subtitle={latestMetric?.disk_used_gb != null && latestMetric?.disk_total_gb != null
            ? `${latestMetric.disk_used_gb.toFixed(1)} / ${latestMetric.disk_total_gb.toFixed(1)} GB`
            : undefined}
        />
      </div>

      {/* Health Summary Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="glass-card p-4 border border-white/5">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">Uptime</p>
          <p className={`text-xl font-black font-mono ${uptimePct != null && uptimePct >= 99 ? 'text-emerald-400' : uptimePct != null && uptimePct >= 95 ? 'text-amber-400' : uptimePct != null ? 'text-red-400' : 'text-gray-500'}`}>
            {uptimePct != null ? `${uptimePct.toFixed(1)}%` : 'N/A'}
          </p>
          <p className="text-[10px] text-gray-500 mt-0.5">{totalPings} checks</p>
        </div>
        <div className="glass-card p-4 border border-white/5">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">Avg Latency</p>
          <p className="text-xl font-black font-mono text-white">
            {avgLatency != null ? `${avgLatency.toFixed(1)}` : 'N/A'}<span className="text-sm text-gray-500 ml-0.5">ms</span>
          </p>
          <p className="text-[10px] text-gray-500 mt-0.5">last {recentPings.length} pings</p>
        </div>
        <div className="glass-card p-4 border border-white/5">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">Status</p>
          <div className="flex items-center gap-2 mt-1">
            <span className={`w-2.5 h-2.5 rounded-full ${vm.is_reachable === true ? 'bg-emerald-400 shadow-lg shadow-emerald-400/30' : vm.is_reachable === false ? 'bg-red-400 shadow-lg shadow-red-400/30' : 'bg-gray-500'}`} />
            <span className={`text-sm font-bold ${vm.is_reachable === true ? 'text-emerald-400' : vm.is_reachable === false ? 'text-red-400' : 'text-gray-500'}`}>
              {vm.is_reachable === true ? 'Online' : vm.is_reachable === false ? 'Offline' : 'Unknown'}
            </span>
          </div>
          <p className="text-[10px] text-gray-500 mt-1">{vm.last_seen ? `seen ${formatDistanceToNow(new Date(vm.last_seen), { addSuffix: true })}` : 'never seen'}</p>
        </div>
        <div className="glass-card p-4 border border-white/5">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">Last Metric</p>
          <p className="text-sm font-bold text-white">
            {latestMetric?.timestamp ? formatDistanceToNow(new Date(latestMetric.timestamp), { addSuffix: true }) : 'N/A'}
          </p>
          <p className="text-[10px] text-gray-500 mt-1">{latestMetric?.timestamp ? format(new Date(latestMetric.timestamp), 'HH:mm:ss') : 'no data'}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Connectivity Log */}
        <div className="glass-card border border-white/5 overflow-hidden">
          <div className="px-5 py-3 border-b border-white/5 flex items-center justify-between">
            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-2">
              <svg className="w-3.5 h-3.5 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
              Connectivity Log
            </h3>
            <span className="text-[10px] text-gray-500">{recentPings.length} recent</span>
          </div>
          {recentPings.length > 0 ? (
            <div className="divide-y divide-white/[0.03]">
              {recentPings.map((ping) => (
                <div key={ping.id} className="flex items-center px-5 py-2.5 hover:bg-white/[0.02] transition-colors">
                  <span className={`w-1.5 h-1.5 rounded-full mr-3 flex-shrink-0 ${ping.success ? 'bg-emerald-400' : 'bg-red-400'}`} />
                  <span className="text-xs text-gray-400 w-20 flex-shrink-0 font-mono">
                    {format(new Date(ping.timestamp), "HH:mm:ss")}
                  </span>
                  <span className="text-[10px] text-gray-500 flex-1 truncate">
                    {format(new Date(ping.timestamp), "MMM d, yyyy")}
                  </span>
                  <span className={`text-xs font-mono font-bold min-w-[50px] text-right ${ping.success ? 'text-emerald-400' : 'text-red-400'}`}>
                    {ping.success ? `${ping.response_time_ms?.toFixed(0)}ms` : ping.error_type || 'FAIL'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center">
              <p className="text-gray-500 text-xs">No connectivity data logged yet.</p>
            </div>
          )}
        </div>

        {/* Deployment Notes */}
        <div className="glass-card border border-white/5 overflow-hidden">
          <div className="px-5 py-3 border-b border-white/5">
            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-2">
              <svg className="w-3.5 h-3.5 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
              Deployment Manifest
            </h3>
          </div>
          <div className="p-5">
            {vm.deployment_notes ? (
              <div className="text-sm text-gray-300 leading-relaxed prose prose-invert prose-sm max-w-none prose-headings:text-gray-200 prose-p:text-gray-300 prose-strong:text-white prose-code:text-brand-300 prose-code:bg-surface-800 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {vm.deployment_notes}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="text-center py-6">
                <svg className="w-8 h-8 text-gray-600 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                <p className="text-xs text-gray-500">No deployment notes added.</p>
                <p className="text-[10px] text-gray-600 mt-1">Edit this VM to add notes (Markdown supported)</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Metrics Tab Component
function MetricsTab({
  metrics,
  isLoading,
}: {
  metrics?: Metric[];
  isLoading: boolean;
}) {
  const [timeRange, setTimeRange] = useState<'1h' | '6h' | '24h' | '7d' | 'all'>('all');
  const [chartMode, setChartMode] = useState<'individual' | 'combined'>('individual');
  const [visibleMetrics, setVisibleMetrics] = useState({ cpu: true, ram: true, disk: true });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="relative w-12 h-12">
          <div className="absolute inset-0 rounded-full border-t-2 border-brand-500 animate-spin" />
        </div>
      </div>
    );
  }

  if (!metrics || metrics.length === 0) {
    return (
      <div className="glass-card p-16 text-center border border-white/5">
        <svg className="w-10 h-10 text-gray-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
        <p className="text-gray-400 text-sm">No metric data available</p>
        <p className="text-gray-600 text-xs mt-1">Trigger a metrics collection to start tracking</p>
      </div>
    );
  }

  // Time range filtering
  const now = new Date();
  const rangeMs: Record<string, number> = {
    '1h': 3600000,
    '6h': 21600000,
    '24h': 86400000,
    '7d': 604800000,
    'all': Infinity,
  };
  const cutoff = timeRange === 'all' ? 0 : now.getTime() - rangeMs[timeRange];
  const filtered = [...metrics]
    .filter(m => m.collection_success && new Date(m.timestamp).getTime() >= cutoff)
    .reverse();

  const chartData = filtered.map((m) => ({
    timestamp: format(new Date(m.timestamp), filtered.length > 48 ? "MMM d HH:mm" : "HH:mm"),
    fullTime: format(new Date(m.timestamp), "MMM d, yyyy HH:mm:ss"),
    cpu: parseFloat((m.cpu_usage_percent || 0).toFixed(1)),
    ram: m.ram_used_mb && m.ram_total_mb ? parseFloat(((m.ram_used_mb / m.ram_total_mb) * 100).toFixed(1)) : 0,
    disk: parseFloat((m.disk_usage_percent || 0).toFixed(1)),
    ram_used_mb: m.ram_used_mb || 0,
    ram_total_mb: m.ram_total_mb || 0,
    disk_used_gb: m.disk_used_gb || 0,
    disk_total_gb: m.disk_total_gb || 0,
  }));

  // Stats calculation
  const calcStats = (key: 'cpu' | 'ram' | 'disk') => {
    const vals = chartData.map(d => d[key]).filter(v => v > 0);
    if (vals.length === 0) return { current: 0, min: 0, max: 0, avg: 0 };
    return {
      current: vals[vals.length - 1],
      min: Math.min(...vals),
      max: Math.max(...vals),
      avg: parseFloat((vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1)),
    };
  };
  const cpuStats = calcStats('cpu');
  const ramStats = calcStats('ram');
  const diskStats = calcStats('disk');

  const tooltipStyle = {
    backgroundColor: 'rgba(17,24,39,0.95)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '0.75rem',
    backdropFilter: 'blur(12px)',
    padding: '12px 16px',
  };

  const chartConfigs = [
    { key: 'cpu' as const, label: 'CPU', color: '#3b82f6', bgColor: 'blue', stats: cpuStats, unit: '%' },
    { key: 'ram' as const, label: 'Memory', color: '#10b981', bgColor: 'emerald', stats: ramStats, unit: '%' },
    { key: 'disk' as const, label: 'Disk', color: '#8b5cf6', bgColor: 'violet', stats: diskStats, unit: '%' },
  ];

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    const data = payload[0]?.payload;
    return (
      <div style={tooltipStyle} className="shadow-2xl">
        <p className="text-[10px] text-gray-400 font-mono mb-2">{data?.fullTime || label}</p>
        {payload.map((p: any, i: number) => (
          <div key={i} className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
            <span className="text-xs text-gray-300">{p.name}:</span>
            <span className="text-xs font-bold font-mono text-white">{p.value}%</span>
          </div>
        ))}
        {data?.ram_used_mb > 0 && payload.some((p: any) => p.dataKey === 'ram') && (
          <p className="text-[10px] text-gray-500 mt-1 border-t border-white/5 pt-1">{data.ram_used_mb.toLocaleString()} / {data.ram_total_mb.toLocaleString()} MB</p>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Controls Bar */}
      <div className="glass-card p-4 border border-white/5 flex flex-wrap items-center justify-between gap-4">
        {/* Time Range */}
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-gray-500 uppercase tracking-wider font-bold mr-2">Range</span>
          {(['1h', '6h', '24h', '7d', 'all'] as const).map(r => (
            <button key={r} onClick={() => setTimeRange(r)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${timeRange === r ? 'bg-brand-500/20 text-brand-400 border border-brand-500/30' : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'}`}>
              {r === 'all' ? 'All' : r.toUpperCase()}
            </button>
          ))}
        </div>
        {/* Chart Mode */}
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-gray-500 uppercase tracking-wider font-bold mr-2">View</span>
          <button onClick={() => setChartMode('individual')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${chartMode === 'individual' ? 'bg-brand-500/20 text-brand-400 border border-brand-500/30' : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'}`}>
            Individual
          </button>
          <button onClick={() => setChartMode('combined')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${chartMode === 'combined' ? 'bg-brand-500/20 text-brand-400 border border-brand-500/30' : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'}`}>
            Combined
          </button>
        </div>
        {/* Data points */}
        <span className="text-[10px] text-gray-600 font-mono">{chartData.length} data points</span>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-3 gap-4">
        {chartConfigs.map(cfg => (
          <div key={cfg.key} className="glass-card p-4 border border-white/5">
            <div className="flex items-center justify-between mb-3">
              <span className={`text-[10px] font-bold text-${cfg.bgColor}-400 uppercase tracking-wider`}>{cfg.label}</span>
              <span className={`text-lg font-black font-mono text-${cfg.bgColor}-400`}>{cfg.stats.current}%</span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <p className="text-[9px] text-gray-600 uppercase">Min</p>
                <p className="text-xs font-mono font-bold text-gray-400">{cfg.stats.min}%</p>
              </div>
              <div>
                <p className="text-[9px] text-gray-600 uppercase">Avg</p>
                <p className="text-xs font-mono font-bold text-white">{cfg.stats.avg}%</p>
              </div>
              <div>
                <p className="text-[9px] text-gray-600 uppercase">Max</p>
                <p className={`text-xs font-mono font-bold ${cfg.stats.max >= 90 ? 'text-red-400' : 'text-gray-400'}`}>{cfg.stats.max}%</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Charts */}
      {chartMode === 'combined' ? (
        <div className="glass-card p-6 border border-white/5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">All Resources</h3>
            <div className="flex gap-3">
              {chartConfigs.map(cfg => (
                <button key={cfg.key} onClick={() => setVisibleMetrics(prev => ({ ...prev, [cfg.key]: !prev[cfg.key] }))}
                  className={`flex items-center gap-1.5 text-[10px] font-bold transition-all ${visibleMetrics[cfg.key] ? `text-${cfg.bgColor}-400` : 'text-gray-600 line-through'}`}>
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: visibleMetrics[cfg.key] ? cfg.color : '#4b5563' }} />
                  {cfg.label}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={chartData} margin={{ top: 5, right: 5, left: -10, bottom: 5 }}>
              <defs>
                {chartConfigs.map(cfg => (
                  <linearGradient key={cfg.key} id={`grad-${cfg.key}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={cfg.color} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={cfg.color} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis dataKey="timestamp" stroke="#4b5563" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis stroke="#4b5563" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} domain={[0, 100]} tickFormatter={v => `${v}%`} />
              <Tooltip content={<CustomTooltip />} />
              {chartConfigs.map(cfg => visibleMetrics[cfg.key] && (
                <Line key={cfg.key} type="monotone" dataKey={cfg.key} stroke={cfg.color} strokeWidth={2} name={cfg.label} dot={false} activeDot={{ r: 4, stroke: cfg.color, strokeWidth: 2, fill: '#111827' }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="space-y-4">
          {chartConfigs.map(cfg => (
            <div key={cfg.key} className="glass-card border border-white/5 overflow-hidden">
              <div className="px-5 py-3 border-b border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: cfg.color }} />
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider">{cfg.label} Usage</h3>
                </div>
                <span className={`text-sm font-black font-mono text-${cfg.bgColor}-400`}>{cfg.stats.current}%</span>
              </div>
              <div className="p-4">
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={chartData} margin={{ top: 5, right: 5, left: -10, bottom: 5 }}>
                    <defs>
                      <linearGradient id={`area-${cfg.key}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={cfg.color} stopOpacity={0.15} />
                        <stop offset="100%" stopColor={cfg.color} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="timestamp" stroke="#4b5563" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                    <YAxis stroke="#4b5563" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} domain={[0, 100]} tickFormatter={v => `${v}%`} width={40} />
                    <Tooltip content={<CustomTooltip />} />
                    <Line type="monotone" dataKey={cfg.key} stroke={cfg.color} strokeWidth={2} name={cfg.label} dot={false}
                      activeDot={{ r: 4, stroke: cfg.color, strokeWidth: 2, fill: '#111827' }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Ping History Tab Component
function PingHistoryTab({
  pingHistory,
  isLoading,
}: {
  pingHistory?: PingResult[];
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="relative w-12 h-12">
          <div className="absolute inset-0 rounded-full border-t-2 border-brand-500 animate-spin"></div>
        </div>
      </div>
    );
  }

  if (!pingHistory || pingHistory.length === 0) {
    return (
      <div className="glass-panel p-16 text-center">
        <p className="text-gray-400">No connectivity history available.</p>
      </div>
    );
  }

  return (
    <div className="glass-panel overflow-hidden border-white/5 animate-fade-in">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-surface-900/80 border-b border-white/5 text-xs uppercase tracking-wider text-gray-500 font-semibold">
              <th className="py-4 px-6">Timestamp</th>
              <th className="py-4 px-6">Status</th>
              <th className="py-4 px-6">Response Time</th>
              <th className="py-4 px-6">Error Type</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {pingHistory.slice(0, 10).map((ping) => (
              <tr
                key={ping.id}
                className="hover:bg-white/[0.02] transition-colors"
              >
                <td className="py-4 px-6 text-sm text-gray-300">
                  {format(new Date(ping.timestamp), "PPpp")}
                </td>
                <td className="py-4 px-6">
                  <span
                    className={`inline-flex items-center px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider ${
                      ping.success
                        ? "bg-brand-500/10 text-brand-400 border border-brand-500/20"
                        : "bg-red-500/10 text-red-400 border border-red-500/20"
                    }`}
                  >
                    {ping.success ? "Success" : "Failed"}
                  </span>
                </td>
                <td className="py-4 px-6 text-sm font-mono text-gray-300">
                  {ping.response_time_ms !== undefined &&
                  ping.response_time_ms !== null
                    ? `${ping.response_time_ms.toFixed(0)} ms`
                    : "-"}
                </td>
                <td className="py-4 px-6 text-sm text-gray-500">
                  {ping.error_type || "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Deployment Notes Tab Component
function DeploymentNotesTab({ notes }: { notes?: string }) {
  if (!notes || notes.trim() === "") {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">No deployment notes available</p>
      </div>
    );
  }

  return (
    <div className="prose prose-invert prose-sm max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ ...props }) => (
            <h1 className="text-2xl font-bold text-white mb-4" {...props} />
          ),
          h2: ({ ...props }) => (
            <h2 className="text-xl font-bold text-white mb-3 mt-6" {...props} />
          ),
          h3: ({ ...props }) => (
            <h3 className="text-lg font-bold text-white mb-2 mt-4" {...props} />
          ),
          p: ({ ...props }) => <p className="text-gray-300 mb-4" {...props} />,
          ul: ({ ...props }) => (
            <ul
              className="list-disc list-inside text-gray-300 mb-4 space-y-1"
              {...props}
            />
          ),
          ol: ({ ...props }) => (
            <ol
              className="list-decimal list-inside text-gray-300 mb-4 space-y-1"
              {...props}
            />
          ),
          li: ({ ...props }) => <li className="text-gray-300" {...props} />,
          code: (props) => {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const { inline, ...rest } = props as {
              inline?: boolean;
              [key: string]: any;
            };
            return inline ? (
              <code
                className="bg-gray-700 text-blue-300 px-1.5 py-0.5 rounded text-sm"
                {...rest}
              />
            ) : (
              <code
                className="block bg-gray-700 text-gray-200 p-4 rounded-lg overflow-x-auto text-sm"
                {...rest}
              />
            );
          },
          pre: ({ ...props }) => (
            <pre
              className="bg-gray-700 rounded-lg overflow-x-auto mb-4"
              {...props}
            />
          ),
          a: ({ ...props }) => (
            <a
              className="text-blue-400 hover:text-blue-300 underline"
              {...props}
            />
          ),
          blockquote: ({ ...props }) => (
            <blockquote
              className="border-l-4 border-gray-600 pl-4 italic text-gray-400 mb-4"
              {...props}
            />
          ),
          strong: ({ ...props }) => (
            <strong className="font-bold text-white" {...props} />
          ),
          em: ({ ...props }) => (
            <em className="italic text-gray-300" {...props} />
          ),
        }}
      >
        {notes}
      </ReactMarkdown>
    </div>
  );
}

// Alerts Tab Component
function AlertsTab({
  vmId,
  alertConfig,
  alertHistory,
  isConfigLoading,
  isHistoryLoading,
}: {
  vmId: number;
  alertConfig?: AlertConfig | null;
  alertHistory?: Alert[];
  isConfigLoading: boolean;
  isHistoryLoading: boolean;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<AlertConfig>({
    enabled: true,
    webhook_url: "",
    email_recipient: "",
    cooldown_minutes: 15,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [successMessage, setSuccessMessage] = useState("");

  const updateAlertConfig = useUpdateAlertConfig();

  // Initialize form data when alert config loads
  useEffect(() => {
    if (alertConfig) {
      setFormData({
        enabled: alertConfig.enabled ?? true,
        webhook_url: alertConfig.webhook_url || "",
        email_recipient: alertConfig.email_recipient || "",
        cooldown_minutes: alertConfig.cooldown_minutes ?? 15,
      });
    }
  }, [alertConfig]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    // At least one notification method must be provided
    if (!formData.webhook_url && !formData.email_recipient) {
      newErrors.general =
        "At least one notification method (webhook or email) must be provided";
    }

    // Validate webhook URL if provided
    if (formData.webhook_url && !isValidWebhookURL(formData.webhook_url)) {
      newErrors.webhook_url =
        "Invalid webhook URL. Must be a valid HTTP or HTTPS URL";
    }

    // Validate email if provided
    if (formData.email_recipient && !isValidEmail(formData.email_recipient)) {
      newErrors.email_recipient = "Invalid email address format";
    }

    // Validate cooldown period
    if (!isValidCooldownPeriod(formData.cooldown_minutes || 15)) {
      newErrors.cooldown_minutes =
        "Cooldown period must be between 1 and 1440 minutes";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validateForm()) {
      return;
    }

    try {
      await updateAlertConfig.mutateAsync({ vmId, config: formData });
      setSuccessMessage("Alert configuration saved successfully");
      setIsEditing(false);
      setTimeout(() => setSuccessMessage(""), 3000);
    } catch (error) {
      setErrors({
        general:
          error instanceof Error
            ? error.message
            : "Failed to save alert configuration",
      });
    }
  };

  const handleCancel = () => {
    // Reset form to current config
    if (alertConfig) {
      setFormData({
        enabled: alertConfig.enabled ?? true,
        webhook_url: alertConfig.webhook_url || "",
        email_recipient: alertConfig.email_recipient || "",
        cooldown_minutes: alertConfig.cooldown_minutes ?? 15,
      });
    }
    setErrors({});
    setIsEditing(false);
  };

  if (isConfigLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <svg
            className="animate-spin h-8 w-8 text-blue-500 mx-auto mb-2"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            ></circle>
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
          <p className="text-gray-400 text-sm">
            Loading alert configuration...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Success Message */}
      {successMessage && (
        <div className="bg-green-900/30 border border-green-500/50 rounded-lg p-4">
          <p className="text-green-200 text-sm">{successMessage}</p>
        </div>
      )}

      {/* General Error Message */}
      {errors.general && (
        <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-4">
          <p className="text-red-200 text-sm">{errors.general}</p>
        </div>
      )}

      {/* Alert Configuration Form */}
      <div className="bg-gray-750 rounded-lg p-6 border border-gray-700">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-lg font-semibold text-white">
            Alert Configuration
          </h3>
          {!isEditing && (
            <button
              onClick={() => setIsEditing(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors duration-200 text-sm font-medium"
            >
              Edit Configuration
            </button>
          )}
        </div>

        <div className="space-y-4">
          {/* Enable/Disable Toggle */}
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium text-gray-300">
                Enable Alerts
              </label>
              <p className="text-xs text-gray-400 mt-1">
                Receive notifications when this VM becomes unreachable
              </p>
            </div>
            <button
              onClick={() => {
                if (isEditing) {
                  setFormData({ ...formData, enabled: !formData.enabled });
                }
              }}
              disabled={!isEditing}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                formData.enabled ? "bg-blue-600" : "bg-gray-600"
              } ${!isEditing ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
              aria-label="Toggle alerts"
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  formData.enabled ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          {/* Webhook URL */}
          <div>
            <label
              htmlFor="webhook_url"
              className="block text-sm font-medium text-gray-300 mb-2"
            >
              Webhook URL
            </label>
            <input
              type="url"
              id="webhook_url"
              value={formData.webhook_url || ""}
              onChange={(e) => {
                setFormData({ ...formData, webhook_url: e.target.value });
                if (errors.webhook_url) {
                  setErrors({ ...errors, webhook_url: "" });
                }
              }}
              disabled={!isEditing}
              placeholder="https://example.com/webhook"
              className={`w-full px-4 py-2 bg-gray-700 border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed ${
                errors.webhook_url ? "border-red-500" : "border-gray-600"
              }`}
              aria-label="Webhook URL"
            />
            {errors.webhook_url && (
              <p className="text-red-400 text-xs mt-1">{errors.webhook_url}</p>
            )}
            <p className="text-xs text-gray-400 mt-1">
              Optional: HTTP/HTTPS endpoint to receive alert notifications
            </p>
          </div>

          {/* Email Recipient */}
          <div>
            <label
              htmlFor="email_recipient"
              className="block text-sm font-medium text-gray-300 mb-2"
            >
              Email Recipient
            </label>
            <input
              type="email"
              id="email_recipient"
              value={formData.email_recipient || ""}
              onChange={(e) => {
                setFormData({ ...formData, email_recipient: e.target.value });
                if (errors.email_recipient) {
                  setErrors({ ...errors, email_recipient: "" });
                }
              }}
              disabled={!isEditing}
              placeholder="alerts@example.com"
              className={`w-full px-4 py-2 bg-gray-700 border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed ${
                errors.email_recipient ? "border-red-500" : "border-gray-600"
              }`}
              aria-label="Email Recipient"
            />
            {errors.email_recipient && (
              <p className="text-red-400 text-xs mt-1">
                {errors.email_recipient}
              </p>
            )}
            <p className="text-xs text-gray-400 mt-1">
              Optional: Email address to receive alert notifications
            </p>
          </div>

          {/* Cooldown Period */}
          <div>
            <label
              htmlFor="cooldown_minutes"
              className="block text-sm font-medium text-gray-300 mb-2"
            >
              Cooldown Period (minutes)
            </label>
            <input
              type="number"
              id="cooldown_minutes"
              value={formData.cooldown_minutes || 15}
              onChange={(e) => {
                setFormData({
                  ...formData,
                  cooldown_minutes: parseInt(e.target.value, 10),
                });
                if (errors.cooldown_minutes) {
                  setErrors({ ...errors, cooldown_minutes: "" });
                }
              }}
              disabled={!isEditing}
              min="1"
              max="1440"
              className={`w-full px-4 py-2 bg-gray-700 border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed ${
                errors.cooldown_minutes ? "border-red-500" : "border-gray-600"
              }`}
              aria-label="Cooldown Period"
            />
            {errors.cooldown_minutes && (
              <p className="text-red-400 text-xs mt-1">
                {errors.cooldown_minutes}
              </p>
            )}
            <p className="text-xs text-gray-400 mt-1">
              Minimum time between alerts for the same VM (1-1440 minutes,
              default: 15)
            </p>
          </div>

          {/* Action Buttons */}
          {isEditing && (
            <div className="flex gap-3 pt-4">
              <button
                onClick={handleSave}
                disabled={updateAlertConfig.isPending}
                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors duration-200 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {updateAlertConfig.isPending
                  ? "Saving..."
                  : "Save Configuration"}
              </button>
              <button
                onClick={handleCancel}
                disabled={updateAlertConfig.isPending}
                className="px-6 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors duration-200 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Alert History */}
      <div className="bg-gray-750 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">Alert History</h3>
        {isHistoryLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="text-center">
              <svg
                className="animate-spin h-8 w-8 text-blue-500 mx-auto mb-2"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                ></circle>
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
              <p className="text-gray-400 text-sm">Loading alert history...</p>
            </div>
          </div>
        ) : !alertHistory || alertHistory.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-400">
              No alerts have been sent for this VM
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-300">
                    Timestamp
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-300">
                    Alert Type
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-300">
                    Method
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-300">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {alertHistory.slice(0, 50).map((alert) => (
                  <tr key={alert.id} className="border-b border-gray-700/50">
                    <td className="py-3 px-4 text-sm text-gray-300">
                      {format(new Date(alert.sent_at), "PPpp")}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          alert.alert_type === "VM_RECOVERED"
                            ? "bg-green-900/50 text-green-200 border border-green-500/50"
                            : "bg-yellow-900/50 text-yellow-200 border border-yellow-500/50"
                        }`}
                      >
                        {alert.alert_type.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-300 capitalize">
                      {alert.notification_method}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          alert.success
                            ? "bg-green-900/50 text-green-200 border border-green-500/50"
                            : "bg-red-900/50 text-red-200 border border-red-500/50"
                        }`}
                      >
                        {alert.success ? "Sent" : "Failed"}
                      </span>
                      {!alert.success && alert.error_message && (
                        <p className="text-xs text-red-400 mt-1">
                          {alert.error_message}
                        </p>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// Specs Tab Component
function SpecsTab({ vmId }: { vmId: number }) {
  const { data: specs, isLoading, isError, error, refetch } = useVMSpecs(vmId);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-400">
        <svg className="animate-spin w-10 h-10 mb-4 text-brand-500" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
        <p className="text-sm font-semibold tracking-wide">Fetching live specs via SSH...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-xl">
        <div className="flex items-center gap-3 text-red-400 mb-2">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          <h3 className="font-bold">Failed to load specs</h3>
        </div>
        <p className="text-sm text-red-300 ml-8 mb-4">{error instanceof Error ? error.message : "Unknown error occurred"}</p>
        <button onClick={() => refetch()} className="ml-8 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-200 rounded-lg transition-colors text-sm font-semibold">Retry</button>
      </div>
    );
  }

  if (!specs) return null;

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-surface-900/50 rounded-xl p-5 border border-white/5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">OS</p>
          <p className="text-white font-bold">{specs.os_name}</p>
          <p className="text-xs text-gray-400 mt-1 font-mono">{specs.kernel}</p>
        </div>
        <div className="bg-surface-900/50 rounded-xl p-5 border border-white/5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">CPU</p>
          <p className="text-white font-bold">{specs.cpu_cores} Cores</p>
          <p className="text-xs text-gray-400 mt-1 font-mono">{specs.cpu_model}</p>
        </div>
        <div className="bg-surface-900/50 rounded-xl p-5 border border-white/5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Total RAM</p>
          <p className="text-white font-bold">{specs.ram_total_gb} GB</p>
        </div>
        <div className="bg-surface-900/50 rounded-xl p-5 border border-white/5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">System Type</p>
          <p className="text-white font-bold">{specs.os_type}</p>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4">Storage Partitions</h3>
        {specs.partitions && specs.partitions.length > 0 ? (
          <div className="overflow-x-auto rounded-xl border border-white/5">
            <table className="w-full text-left text-sm text-gray-300">
              <thead className="text-[10px] uppercase tracking-wider bg-surface-800 text-gray-400 border-b border-white/5">
                <tr>
                  <th className="px-6 py-4 font-bold">Filesystem</th>
                  <th className="px-6 py-4 font-bold">Mounted On</th>
                  <th className="px-6 py-4 font-bold text-right">Size</th>
                  <th className="px-6 py-4 font-bold text-right">Used</th>
                  <th className="px-6 py-4 font-bold text-right">Avail</th>
                  <th className="px-6 py-4 font-bold text-right">Usage</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 bg-surface-900/30">
                {specs.partitions.map((part: any, idx: number) => (
                  <tr key={idx} className="hover:bg-white/5 transition-colors">
                    <td className="px-6 py-4 font-mono text-xs">{part.filesystem}</td>
                    <td className="px-6 py-4 font-mono text-xs text-brand-300">{part.mounted_on}</td>
                    <td className="px-6 py-4 text-right">{part.size}</td>
                    <td className="px-6 py-4 text-right text-gray-400">{part.used}</td>
                    <td className="px-6 py-4 text-right text-gray-400">{part.avail}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-3">
                        <span className="text-xs font-mono">{part.use_percent}</span>
                        <div className="w-16 bg-surface-800 rounded-full h-1.5 overflow-hidden">
                          <div 
                            className={`h-full rounded-full transition-all duration-700 ease-out ${parseInt(part.use_percent) > 85 ? "bg-red-500" : parseInt(part.use_percent) > 65 ? "bg-yellow-500" : "bg-brand-500"}`} 
                            style={{ width: part.use_percent }}
                          ></div>
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center bg-surface-900/30 rounded-xl border border-white/5">
            <p className="text-gray-500 text-sm">No partition data available.</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ==========================================
// NEW TAB COMPONENT: Services
// ==========================================

function ServicesTab({ vmId }: { vmId: number }) {
  const [services, setServices] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isChecking, setIsChecking] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newService, setNewService] = useState({ name: "", displayName: "", command: "" });

  const fetchServices = useCallback(async () => {
    try {
      const data = await api.services.list(vmId);
      setServices(data || []);
    } catch (err) {
      console.error("Failed to fetch services:", err);
    } finally {
      setIsLoading(false);
    }
  }, [vmId]);

  useEffect(() => {
    fetchServices();
  }, [fetchServices]);

  const handleCheckNow = async () => {
    setIsChecking(true);
    try {
      await api.services.checkNow(vmId);
      // Usually takes a few seconds to run, so we wait before polling
      setTimeout(() => fetchServices(), 3000);
    } catch (err) {
      console.error(err);
    } finally {
      setIsChecking(false);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newService.name) return;
    
    try {
      await api.services.add(vmId, {
        service_name: newService.name,
        display_name: newService.displayName,
        check_command: newService.command,
      });
      setShowAddModal(false);
      setNewService({ name: "", displayName: "", command: "" });
      fetchServices();
    } catch (err) {
      console.error("Failed to add service", err);
    }
  };

  const handleRemove = async (serviceId: number) => {
    if (!confirm("Remove this service from monitoring?")) return;
    try {
      await api.services.remove(vmId, serviceId);
      fetchServices();
    } catch (err) {
      console.error(err);
    }
  };

  const getStatusColor = (status: string | null) => {
    if (status === "active") return "bg-green-500/20 text-green-400 border-green-500/30";
    if (status === "inactive") return "bg-gray-500/20 text-gray-400 border-gray-500/30";
    if (status === "failed") return "bg-red-500/20 text-red-400 border-red-500/30";
    return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
  };

  if (isLoading) {
    return <div className="text-gray-400 animate-pulse">Loading services...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">Service Health</h2>
          <p className="text-gray-400">Monitor specific systemd services running inside the VM.</p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={handleCheckNow}
            disabled={isChecking}
            className="px-4 py-2 bg-surface-700 hover:bg-surface-600 text-white rounded-lg transition border border-white/10"
          >
            {isChecking ? "Checking..." : "Check Now"}
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg transition"
          >
            Add Service
          </button>
        </div>
      </div>

      {services.length === 0 ? (
        <div className="p-8 text-center bg-surface-800/30 border border-white/5 rounded-xl">
          <p className="text-gray-400 mb-4">No services are currently being monitored.</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="text-brand-400 hover:text-brand-300 font-medium"
          >
            + Add your first service
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {services.map((svc) => (
            <div key={svc.id} className="p-5 bg-surface-800/50 border border-white/10 rounded-xl relative group">
              <button
                onClick={() => handleRemove(svc.id)}
                className="absolute top-4 right-4 text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition"
                title="Remove service"
              >
                ✕
              </button>
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold text-lg text-white">
                  {svc.display_name || svc.service_name}
                </h3>
                <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${getStatusColor(svc.status)}`}>
                  {(svc.status || "UNKNOWN").toUpperCase()}
                </span>
              </div>
              <div className="text-sm text-gray-500 font-mono">
                {svc.service_name}
              </div>
            </div>
          ))}
        </div>
      )}

      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-surface-900 border border-white/10 rounded-2xl w-full max-w-md overflow-hidden">
            <div className="p-6 border-b border-white/5">
              <h3 className="text-xl font-bold text-white">Add Service to Monitor</h3>
            </div>
            <form onSubmit={handleAdd} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Service Name (e.g., nginx)</label>
                <input
                  required
                  type="text"
                  value={newService.name}
                  onChange={(e) => setNewService({ ...newService, name: e.target.value })}
                  className="w-full bg-surface-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:border-brand-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Display Name (Optional)</label>
                <input
                  type="text"
                  value={newService.displayName}
                  onChange={(e) => setNewService({ ...newService, displayName: e.target.value })}
                  className="w-full bg-surface-800 border border-white/10 rounded-lg px-4 py-2 text-white focus:border-brand-500 outline-none"
                  placeholder="e.g., Web Server"
                />
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-gray-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg"
                >
                  Add Service
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// ==========================================
// NEW TAB COMPONENT: Containers (LXC)
// ==========================================

function ContainersTab({ vmId }: { vmId: number }) {
  const [lxcData, setLxcData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [expandedContainer, setExpandedContainer] = useState<{id: string, view: 'processes' | 'resources'} | null>(null);

  const fetchContainers = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.lxc.list(vmId);
      setLxcData(data);
    } catch (err) {
      console.error("Failed to fetch LXC containers:", err);
      // Fallback
      setLxcData({ is_proxmox: false, containers: [] });
    } finally {
      setIsLoading(false);
    }
  }, [vmId]);

  useEffect(() => {
    fetchContainers();
  }, [fetchContainers]);

  const handleAction = async (lxcId: string, action: 'start' | 'stop' | 'restart') => {
    if (action === 'stop' && !confirm(`Are you sure you want to stop container ${lxcId}?`)) return;
    if (action === 'restart' && !confirm(`Are you sure you want to restart container ${lxcId}?`)) return;
    
    setActionLoading(`${lxcId}-${action}`);
    try {
      await api.lxc.action(vmId, lxcId, action);
      // Wait a moment for Proxmox to process before refreshing
      setTimeout(() => fetchContainers(), 2000);
    } catch (err) {
      console.error(err);
      alert(`Failed to ${action} container ${lxcId}`);
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusColor = (status: string) => {
    if (status === "running") return "bg-green-500/20 text-green-400 border-green-500/30";
    if (status === "stopped") return "bg-gray-500/20 text-gray-400 border-gray-500/30";
    return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-gray-400 space-y-4">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
        <p>Connecting via SSH to detect LXC containers...</p>
      </div>
    );
  }

  if (!lxcData?.is_proxmox) {
    return (
      <div className="p-8 text-center bg-surface-800/30 border border-white/5 rounded-xl">
        <h3 className="text-xl font-bold text-white mb-2">No LXC Provider Found</h3>
        <p className="text-gray-400">
          This VM does not appear to have an LXC provider installed (neither <code className="bg-black/50 px-1 py-0.5 rounded text-brand-300">pct</code>, <code className="bg-black/50 px-1 py-0.5 rounded text-brand-300">lxc</code>, nor <code className="bg-black/50 px-1 py-0.5 rounded text-brand-300">lxc-ls</code> were found). 
          Container management is only available for VMs that act as LXC hosts.
        </p>
      </div>
    );
  }

  const containers = lxcData.containers || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">LXC Containers</h2>
          <p className="text-gray-400">Manage LXC containers running on this host (Provider: <span className="font-mono text-brand-300">{lxcData.provider}</span>).</p>
        </div>
        <button
          onClick={fetchContainers}
          className="px-4 py-2 bg-surface-700 hover:bg-surface-600 text-white rounded-lg transition border border-white/10"
        >
          Refresh List
        </button>
      </div>

      {containers.length === 0 ? (
        <div className="p-8 text-center bg-surface-800/30 border border-white/5 rounded-xl">
          <p className="text-gray-400">No LXC containers found on this host.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {containers.map((c: any) => (
            <div key={c.vmid} className={`p-5 bg-surface-800/50 border border-white/10 rounded-xl flex flex-col justify-between transition-all ${
              (expandedContainer?.id === c.vmid) ? 'col-span-full' : ''
            }`}>
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-bold text-lg text-white truncate pr-2" title={c.name}>
                    {c.name}
                  </h3>
                  <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${getStatusColor(c.status)}`}>
                    {c.status.toUpperCase()}
                  </span>
                </div>
                <div className="text-sm text-gray-500 font-mono mb-6">
                  VMID: {c.vmid}
                </div>
              </div>
              
              <div className="flex items-center space-x-2 pt-4 border-t border-white/5">
                <button
                  onClick={() => handleAction(c.vmid, 'start')}
                  disabled={c.status === 'running' || actionLoading !== null}
                  className={`flex-1 py-2 text-sm font-medium rounded transition ${
                    c.status === 'running'
                      ? 'bg-surface-700 text-gray-500 cursor-not-allowed'
                      : actionLoading === `${c.vmid}-start`
                      ? 'bg-green-500/20 text-green-400 animate-pulse'
                      : 'bg-green-500/10 hover:bg-green-500/20 text-green-400 border border-green-500/20'
                  }`}
                >
                  Start
                </button>
                <button
                  onClick={() => handleAction(c.vmid, 'restart')}
                  disabled={c.status !== 'running' || actionLoading !== null}
                  className={`flex-1 py-2 text-sm font-medium rounded transition ${
                    c.status !== 'running'
                      ? 'bg-surface-700 text-gray-500 cursor-not-allowed'
                      : actionLoading === `${c.vmid}-restart`
                      ? 'bg-yellow-500/20 text-yellow-400 animate-pulse'
                      : 'bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-400 border border-yellow-500/20'
                  }`}
                >
                  Restart
                </button>
                <button
                  onClick={() => handleAction(c.vmid, 'stop')}
                  disabled={c.status !== 'running' || actionLoading !== null}
                  className={`flex-1 py-2 text-sm font-medium rounded transition ${
                    c.status !== 'running'
                      ? 'bg-surface-700 text-gray-500 cursor-not-allowed'
                      : actionLoading === `${c.vmid}-stop`
                      ? 'bg-red-500/20 text-red-400 animate-pulse'
                      : 'bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20'
                  }`}
                >
                  Stop
                </button>
                <button
                  onClick={() => setExpandedContainer(expandedContainer?.id === c.vmid && expandedContainer.view === 'processes' ? null : {id: c.vmid, view: 'processes'})}
                  className={`flex-1 py-2 text-sm font-medium rounded transition ${
                    expandedContainer?.id === c.vmid && expandedContainer.view === 'processes'
                      ? 'bg-brand-500/20 text-brand-400 border border-brand-500/20'
                      : 'bg-surface-700 hover:bg-surface-600 text-gray-300 border border-white/5'
                  }`}
                >
                  Processes
                </button>
                <button
                  onClick={() => setExpandedContainer(expandedContainer?.id === c.vmid && expandedContainer.view === 'resources' ? null : {id: c.vmid, view: 'resources'})}
                  className={`flex-1 py-2 text-sm font-medium rounded transition ${
                    expandedContainer?.id === c.vmid && expandedContainer.view === 'resources'
                      ? 'bg-blue-500/20 text-blue-400 border border-blue-500/20'
                      : 'bg-surface-700 hover:bg-surface-600 text-gray-300 border border-white/5'
                  }`}
                >
                  Resources
                </button>
              </div>

              {/* Expandable Process Panel */}
              {expandedContainer?.id === c.vmid && expandedContainer.view === 'processes' && c.status === 'running' && (
                <div className="mt-4 pt-4 border-t border-white/5">
                  <ProcessPanel vmId={vmId} lxcId={c.vmid} />
                </div>
              )}
              {expandedContainer?.id === c.vmid && expandedContainer.view === 'processes' && c.status !== 'running' && (
                <div className="mt-4 pt-4 border-t border-white/5 text-center text-gray-500 text-sm py-4">
                  Container must be running to view processes.
                </div>
              )}

              {/* Expandable Resource Panel */}
              {expandedContainer?.id === c.vmid && expandedContainer.view === 'resources' && (
                <div className="mt-4 pt-4 border-t border-white/5">
                  <ResourcePanel vmId={vmId} lxcId={c.vmid} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ==========================================
// Network Tab
// ==========================================

function NetworkTab({ vmId, vm }: { vmId: number, vm: VM }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">Network Topology</h2>
          <p className="text-gray-400">Visual mapping of the host, bridges, and LXC containers.</p>
        </div>
      </div>
      
      <div className="relative">
        <NetworkTopology vmId={vmId} />
      </div>
    </div>
  );
}
