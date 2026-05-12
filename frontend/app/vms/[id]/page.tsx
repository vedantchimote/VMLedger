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
import { useVMMetrics, useVMPingHistory } from "@/lib/hooks/use-monitoring";
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

type TabType = "overview" | "specs" | "metrics" | "ping" | "notes" | "alerts";
type TriggerType = "ping" | "dns" | "metrics";

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
      <header className="sticky top-0 z-50 border-b border-white/5 bg-surface-950/60 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-20">
            <div className="flex items-center gap-6">
              <Link
                href="/dashboard"
                className="flex items-center justify-center w-10 h-10 rounded-xl bg-surface-800 border border-white/5 text-gray-400 hover:text-white hover:bg-surface-700 transition-all hover:scale-105"
                aria-label="Back to Dashboard"
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10 19l-7-7m0 0l7-7m-7 7h18"
                  />
                </svg>
              </Link>
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h1 className="text-2xl font-bold text-white tracking-tight">
                    {vm.hostname}
                  </h1>
                  <span
                    className={
                      vm.is_reachable === true
                        ? "status-badge-online"
                        : vm.is_reachable === false
                          ? "status-badge-offline"
                          : "status-badge-unknown"
                    }
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
                <div className="text-sm font-mono text-gray-400">
                  {vm.ip_address}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => handleTrigger("ping")}
                disabled={triggerLoading.ping}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-brand-500/10 text-brand-400 border border-brand-500/20 hover:bg-brand-500/20 hover:border-brand-500/30 transition-all text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                title="Run an immediate connectivity check"
              >
                {triggerLoading.ping ? (
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                )}
                Ping Now
              </button>
              <button
                onClick={() => handleTrigger("dns")}
                disabled={triggerLoading.dns}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20 hover:bg-purple-500/20 hover:border-purple-500/30 transition-all text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                title="Resolve hostname and compare with registered IP"
              >
                {triggerLoading.dns ? (
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" /></svg>
                )}
                DNS Check
              </button>
              <button
                onClick={() => handleTrigger("metrics")}
                disabled={triggerLoading.metrics}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 hover:bg-cyan-500/20 hover:border-cyan-500/30 transition-all text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                title="Collect CPU, RAM, and Disk usage via SSH"
              >
                {triggerLoading.metrics ? (
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                )}
                Collect Metrics
              </button>
              <div className="w-px h-8 bg-white/10"></div>
              <Link href={`/vms/${vm.id}/edit`} className="btn-secondary flex items-center gap-2">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
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
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 animate-fade-in">
        {/* VM Metadata Section */}
        <div className="glass-card p-8 mb-8">
          <h2 className="text-xl font-bold text-white tracking-tight mb-6 flex items-center">
            <svg
              className="w-5 h-5 mr-2 text-brand-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            System Information
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-8 gap-y-6">
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                Network Interface
              </p>
              <p className="text-white font-mono text-sm">{vm.ip_address}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                SSH Port
              </p>
              <p className="text-white font-mono text-sm">{vm.ssh_port}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                Domain Name
              </p>
              <p className="text-white text-sm">
                {vm.domain || (
                  <span className="text-gray-600 italic">Not configured</span>
                )}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                Last Seen
              </p>
              <p className="text-white text-sm">
                {formatRelativeTime(vm.last_seen)}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                Created
              </p>
              <p className="text-white text-sm">
                {formatRelativeTime(vm.created_at)}
              </p>
            </div>
          </div>
          {vm.tags && vm.tags.length > 0 && (
            <div className="mt-8 pt-6 border-t border-white/5">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Tags
                </span>
                <div className="h-4 w-px bg-white/10 mx-1"></div>
                {vm.tags.map((tag, index) => (
                  <span
                    key={index}
                    className="px-3 py-1 bg-brand-500/10 text-brand-300 border border-brand-500/20 rounded-lg text-xs font-semibold tracking-wider uppercase shadow-inner"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* DNS Resolution Status */}
        <div className="glass-card p-8 mb-8">
          <h2 className="text-xl font-bold text-white tracking-tight mb-6 flex items-center">
            <svg
              className="w-5 h-5 mr-2 text-brand-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"
              />
            </svg>
            DNS Resolution
            {vm.dns_mismatch && (
              <span className="ml-3 px-2.5 py-1 bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 rounded-lg text-[10px] font-bold uppercase tracking-wider animate-pulse">
                IP Mismatch Detected
              </span>
            )}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-surface-900/50 rounded-xl p-5 border border-white/5">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                Registered IP
              </p>
              <p className="text-white font-mono text-sm font-bold">{vm.ip_address}</p>
            </div>
            <div className={`rounded-xl p-5 border ${vm.dns_mismatch ? "bg-yellow-500/5 border-yellow-500/20" : "bg-surface-900/50 border-white/5"}`}>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                Resolved IP (from hostname)
              </p>
              {vm.resolved_ip ? (
                <p className={`font-mono text-sm font-bold ${vm.dns_mismatch ? "text-yellow-400" : "text-brand-400"}`}>
                  {vm.resolved_ip}
                  {vm.dns_mismatch && (
                    <span className="ml-2 text-yellow-500 text-[10px] font-semibold uppercase">
                      ≠ registered
                    </span>
                  )}
                  {!vm.dns_mismatch && vm.resolved_ip && (
                    <span className="ml-2 text-brand-500 text-[10px] font-semibold uppercase">
                      ✓ matches
                    </span>
                  )}
                </p>
              ) : (
                <p className="text-gray-600 italic text-sm">Not yet checked</p>
              )}
            </div>
            <div className="bg-surface-900/50 rounded-xl p-5 border border-white/5">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                Last DNS Check
              </p>
              <p className="text-white text-sm">
                {vm.dns_last_checked
                  ? formatRelativeTime(vm.dns_last_checked)
                  : <span className="text-gray-600 italic">Pending first check</span>
                }
              </p>
              <p className="text-[10px] text-gray-600 mt-1 uppercase tracking-wider">
                Checked every 6 hours
              </p>
            </div>
          </div>
          {vm.dns_mismatch && (
            <div className="mt-4 p-4 bg-yellow-500/5 border border-yellow-500/20 rounded-xl flex items-start gap-3">
              <svg className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <div>
                <p className="text-sm font-bold text-yellow-400 mb-1">DNS Drift Warning</p>
                <p className="text-xs text-yellow-400/80">
                  The hostname <span className="font-mono font-bold">{vm.hostname}</span> now resolves
                  to <span className="font-mono font-bold">{vm.resolved_ip}</span> instead
                  of the registered IP <span className="font-mono font-bold">{vm.ip_address}</span>.
                  Consider updating the VM&apos;s IP address if this change is intentional.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Tabbed Interface */}
        <div className="glass-card overflow-visible">
          {/* Tab Headers */}
          <div className="border-b border-white/5 bg-surface-900/50">
            <nav className="flex overflow-x-auto hide-scrollbar">
              {["overview", "specs", "metrics", "ping", "notes", "alerts"].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab as TabType)}
                  className={`px-8 py-5 text-sm font-bold uppercase tracking-wider border-b-2 transition-all whitespace-nowrap ${
                    activeTab === tab
                      ? "border-brand-400 text-brand-400 bg-brand-500/5"
                      : "border-transparent text-gray-400 hover:text-white hover:bg-white/5"
                  }`}
                >
                  {tab.replace("_", " ")}
                </button>
              ))}
            </nav>
          </div>

          {/* Tab Content */}
          <div className="p-8">
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

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Current Status Summary */}
      <div>
        <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4">
          Resource Utilization
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="glass-panel p-6 border-brand-500/10 hover:border-brand-500/30 transition-all">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
                <svg
                  className="w-5 h-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m14-6h2m-2 6h2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"
                  />
                </svg>
              </div>
              <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">
                CPU Usage
              </p>
            </div>
            <p className="text-3xl font-bold text-white font-mono">
              {latestMetric?.cpu_usage_percent !== undefined
                ? `${latestMetric.cpu_usage_percent.toFixed(1)}%`
                : "N/A"}
            </p>
          </div>
          <div className="glass-panel p-6 border-brand-500/10 hover:border-brand-500/30 transition-all">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
                <svg
                  className="w-5 h-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                  />
                </svg>
              </div>
              <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">
                RAM Usage
              </p>
            </div>
            <p className="text-3xl font-bold text-white font-mono">
              {latestMetric?.ram_used_mb !== undefined &&
              latestMetric?.ram_total_mb !== undefined
                ? `${Math.round((latestMetric.ram_used_mb / latestMetric.ram_total_mb) * 100)}%`
                : "N/A"}
            </p>
            <p className="text-xs text-gray-500 mt-1 font-mono">
              {latestMetric?.ram_used_mb !== undefined &&
              latestMetric?.ram_total_mb !== undefined
                ? `${latestMetric.ram_used_mb}MB / ${latestMetric.ram_total_mb}MB`
                : ""}
            </p>
          </div>
          <div className="glass-panel p-6 border-brand-500/10 hover:border-brand-500/30 transition-all">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400">
                <svg
                  className="w-5 h-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"
                  />
                </svg>
              </div>
              <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">
                Disk Usage
              </p>
            </div>
            <p className="text-3xl font-bold text-white font-mono">
              {latestMetric?.disk_usage_percent !== undefined
                ? `${latestMetric.disk_usage_percent.toFixed(1)}%`
                : "N/A"}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Recent Ping Results */}
        <div>
          <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4">
            Connectivity Log
          </h3>
          {recentPings.length > 0 ? (
            <div className="space-y-3">
              {recentPings.map((ping) => (
                <div
                  key={ping.id}
                  className={`flex items-center justify-between p-4 rounded-xl border backdrop-blur-sm transition-all ${
                    ping.success
                      ? "bg-brand-500/5 border-brand-500/20 hover:border-brand-500/40"
                      : "bg-red-500/5 border-red-500/20 hover:border-red-500/40"
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <div
                      className={`p-2 rounded-lg ${ping.success ? "bg-brand-500/10" : "bg-red-500/10"}`}
                    >
                      <svg
                        className={`w-4 h-4 ${ping.success ? "text-brand-400" : "text-red-400"}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        {ping.success ? (
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M5 13l4 4L19 7"
                          />
                        ) : (
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M6 18L18 6M6 6l12 12"
                          />
                        )}
                      </svg>
                    </div>
                    <div>
                      <span className="block text-sm font-medium text-gray-200">
                        {format(new Date(ping.timestamp), "MMM d, yyyy")}
                      </span>
                      <span className="block text-xs text-gray-500">
                        {format(new Date(ping.timestamp), "HH:mm:ss")}
                      </span>
                    </div>
                  </div>
                  <div
                    className={`text-sm font-mono font-bold ${ping.success ? "text-brand-300" : "text-red-400"}`}
                  >
                    {ping.success
                      ? `${ping.response_time_ms?.toFixed(0)}ms`
                      : ping.error_type || "Failed"}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="glass-panel p-8 text-center">
              <p className="text-gray-400 text-sm">
                No connectivity data logged yet.
              </p>
            </div>
          )}
        </div>

        {/* Deployment Notes Preview */}
        {vm.deployment_notes && (
          <div>
            <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4">
              Deployment Manifest
            </h3>
            <div className="glass-panel p-6 border-white/5 bg-surface-900/80">
              <div className="text-gray-300 text-sm leading-relaxed prose prose-invert prose-sm">
                {vm.deployment_notes.substring(0, 500)}
                {vm.deployment_notes.length > 500 && "..."}
              </div>
            </div>
          </div>
        )}
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
  if (isLoading) {
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
          <p className="text-gray-400 text-sm">Loading metrics...</p>
        </div>
      </div>
    );
  }

  if (!metrics || metrics.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">No metric data available</p>
      </div>
    );
  }

  // Prepare chart data (reverse to show oldest to newest)
  const chartData = [...metrics]
    .reverse()
    .filter((m) => m.collection_success)
    .map((metric) => ({
      timestamp: format(new Date(metric.timestamp), "HH:mm"),
      cpu: metric.cpu_usage_percent || 0,
      ram:
        metric.ram_used_mb && metric.ram_total_mb
          ? ((metric.ram_used_mb / metric.ram_total_mb) * 100).toFixed(1)
          : 0,
      disk: metric.disk_usage_percent || 0,
    }));

  return (
    <div className="space-y-8">
      {/* CPU Usage Chart */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">
          CPU Usage Over Time
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="timestamp" stroke="#9CA3AF" />
            <YAxis stroke="#9CA3AF" domain={[0, 100]} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1F2937",
                border: "1px solid #374151",
                borderRadius: "0.5rem",
              }}
              labelStyle={{ color: "#F3F4F6" }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="cpu"
              stroke="#3B82F6"
              strokeWidth={2}
              name="CPU %"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* RAM Usage Chart */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">
          RAM Usage Over Time
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="timestamp" stroke="#9CA3AF" />
            <YAxis stroke="#9CA3AF" domain={[0, 100]} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1F2937",
                border: "1px solid #374151",
                borderRadius: "0.5rem",
              }}
              labelStyle={{ color: "#F3F4F6" }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="ram"
              stroke="#10B981"
              strokeWidth={2}
              name="RAM %"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Disk Usage Chart */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">
          Disk Usage Over Time
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="timestamp" stroke="#9CA3AF" />
            <YAxis stroke="#9CA3AF" domain={[0, 100]} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1F2937",
                border: "1px solid #374151",
                borderRadius: "0.5rem",
              }}
              labelStyle={{ color: "#F3F4F6" }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="disk"
              stroke="#8B5CF6"
              strokeWidth={2}
              name="Disk %"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
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
