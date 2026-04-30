'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { formatDistanceToNow, format } from 'date-fns';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { useAuth } from '@/lib/hooks/use-auth';
import { useVM } from '@/lib/hooks/use-vms';
import { useVMMetrics, useVMPingHistory } from '@/lib/hooks/use-monitoring';
import { useAlertConfig, useAlertHistory, useUpdateAlertConfig } from '@/lib/hooks/use-alerts';
import type { Metric, PingResult, VM, Alert, AlertConfig } from '@/types/api';
import { isValidWebhookURL, isValidEmail, isValidCooldownPeriod } from '@/lib/validation';

type TabType = 'overview' | 'metrics' | 'ping' | 'notes' | 'alerts';

export default function VMDetailsPage() {
  const router = useRouter();
  const params = useParams();
  const vmId = parseInt(params.id as string, 10);
  const { isAuthenticated } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  // Fetch VM data
  const { data: vm, isLoading: vmLoading, isError: vmError } = useVM(vmId);
  const { data: metrics, isLoading: metricsLoading } = useVMMetrics(vmId, 100);
  const { data: pingHistory, isLoading: pingLoading } = useVMPingHistory(vmId, 100);
  const { data: alertConfig, isLoading: alertConfigLoading } = useAlertConfig(vmId);
  const { data: alertHistory, isLoading: alertHistoryLoading } = useAlertHistory(vmId);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) {
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
              The requested VM could not be found or you don&apos;t have permission to view it.
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
    if (isReachable === true) return 'bg-green-500';
    if (isReachable === false) return 'bg-red-500';
    return 'bg-gray-500';
  };

  const getStatusText = (isReachable: boolean | undefined): string => {
    if (isReachable === true) return 'Online';
    if (isReachable === false) return 'Offline';
    return 'Unknown';
  };

  const formatRelativeTime = (timestamp: string | undefined): string => {
    if (!timestamp) return 'Never';
    try {
      return formatDistanceToNow(new Date(timestamp), { addSuffix: true });
    } catch {
      return 'Unknown';
    }
  };

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-4">
              <Link
                href="/dashboard"
                className="text-gray-400 hover:text-white transition-colors"
                aria-label="Back to Dashboard"
              >
                <svg
                  className="w-6 h-6"
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
              <h1 className="text-2xl font-bold text-white">{vm.hostname}</h1>
              <div
                className={`w-3 h-3 rounded-full ${getStatusColor(vm.is_reachable)} shadow-lg`}
                title={getStatusText(vm.is_reachable)}
              ></div>
            </div>
            <div className="flex items-center gap-4">
              <Link
                href={`/vms/${vm.id}/edit`}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors duration-200 text-sm font-medium"
              >
                Edit VM
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* VM Metadata Section */}
        <div className="bg-gray-800 rounded-lg shadow-xl border border-gray-700 p-6 mb-6">
          <h2 className="text-xl font-bold text-white mb-4">VM Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-gray-400 mb-1">IP Address</p>
              <p className="text-white font-medium">{vm.ip_address}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400 mb-1">SSH Port</p>
              <p className="text-white font-medium">{vm.ssh_port}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400 mb-1">Domain</p>
              <p className="text-white font-medium">{vm.domain || 'N/A'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400 mb-1">Status</p>
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  vm.is_reachable === true
                    ? 'bg-green-900/50 text-green-200 border border-green-500/50'
                    : vm.is_reachable === false
                    ? 'bg-red-900/50 text-red-200 border border-red-500/50'
                    : 'bg-gray-700 text-gray-300 border border-gray-600'
                }`}
              >
                {getStatusText(vm.is_reachable)}
              </span>
            </div>
            <div>
              <p className="text-sm text-gray-400 mb-1">Last Seen</p>
              <p className="text-white font-medium">{formatRelativeTime(vm.last_seen)}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400 mb-1">Created</p>
              <p className="text-white font-medium">{formatRelativeTime(vm.created_at)}</p>
            </div>
          </div>
          {vm.tags && vm.tags.length > 0 && (
            <div className="mt-4">
              <p className="text-sm text-gray-400 mb-2">Tags</p>
              <div className="flex flex-wrap gap-2">
                {vm.tags.map((tag, index) => (
                  <span
                    key={index}
                    className="px-3 py-1 bg-blue-900/50 text-blue-200 border border-blue-500/50 rounded-full text-xs font-medium"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Tabbed Interface */}
        <div className="bg-gray-800 rounded-lg shadow-xl border border-gray-700">
          {/* Tab Headers */}
          <div className="border-b border-gray-700">
            <nav className="flex -mb-px">
              <button
                onClick={() => setActiveTab('overview')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'overview'
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-600'
                }`}
              >
                Overview
              </button>
              <button
                onClick={() => setActiveTab('metrics')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'metrics'
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-600'
                }`}
              >
                Metrics
              </button>
              <button
                onClick={() => setActiveTab('ping')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'ping'
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-600'
                }`}
              >
                Ping History
              </button>
              <button
                onClick={() => setActiveTab('notes')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'notes'
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-600'
                }`}
              >
                Deployment Notes
              </button>
              <button
                onClick={() => setActiveTab('alerts')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'alerts'
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-600'
                }`}
              >
                Alerts
              </button>
            </nav>
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {activeTab === 'overview' && (
              <OverviewTab vm={vm} metrics={metrics} pingHistory={pingHistory} />
            )}
            {activeTab === 'metrics' && (
              <MetricsTab metrics={metrics} isLoading={metricsLoading} />
            )}
            {activeTab === 'ping' && (
              <PingHistoryTab pingHistory={pingHistory} isLoading={pingLoading} />
            )}
            {activeTab === 'notes' && <DeploymentNotesTab notes={vm.deployment_notes} />}
            {activeTab === 'alerts' && (
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
    <div className="space-y-6">
      {/* Current Status Summary */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">Current Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-750 rounded-lg p-4 border border-gray-700">
            <p className="text-sm text-gray-400 mb-1">CPU Usage</p>
            <p className="text-2xl font-bold text-white">
              {latestMetric?.cpu_usage_percent !== undefined
                ? `${latestMetric.cpu_usage_percent.toFixed(1)}%`
                : 'N/A'}
            </p>
          </div>
          <div className="bg-gray-750 rounded-lg p-4 border border-gray-700">
            <p className="text-sm text-gray-400 mb-1">RAM Usage</p>
            <p className="text-2xl font-bold text-white">
              {latestMetric?.ram_used_mb !== undefined && latestMetric?.ram_total_mb !== undefined
                ? `${latestMetric.ram_used_mb} / ${latestMetric.ram_total_mb} MB`
                : 'N/A'}
            </p>
          </div>
          <div className="bg-gray-750 rounded-lg p-4 border border-gray-700">
            <p className="text-sm text-gray-400 mb-1">Disk Usage</p>
            <p className="text-2xl font-bold text-white">
              {latestMetric?.disk_usage_percent !== undefined
                ? `${latestMetric.disk_usage_percent.toFixed(1)}%`
                : 'N/A'}
            </p>
          </div>
        </div>
      </div>

      {/* Recent Ping Results */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">Recent Ping Results</h3>
        {recentPings.length > 0 ? (
          <div className="space-y-2">
            {recentPings.map((ping) => (
              <div
                key={ping.id}
                className={`flex items-center justify-between p-3 rounded-lg border ${
                  ping.success
                    ? 'bg-green-900/20 border-green-500/30'
                    : 'bg-red-900/20 border-red-500/30'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      ping.success ? 'bg-green-500' : 'bg-red-500'
                    }`}
                  ></div>
                  <span className="text-sm text-gray-300">
                    {format(new Date(ping.timestamp), 'PPpp')}
                  </span>
                </div>
                <div className="text-sm text-gray-400">
                  {ping.success
                    ? `${ping.response_time_ms?.toFixed(0)}ms`
                    : ping.error_type || 'Failed'}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-400 text-sm">No ping data available</p>
        )}
      </div>

      {/* Deployment Notes Preview */}
      {vm.deployment_notes && (
        <div>
          <h3 className="text-lg font-semibold text-white mb-4">Deployment Notes Preview</h3>
          <div className="bg-gray-750 rounded-lg p-4 border border-gray-700">
            <div className="text-gray-300 text-sm line-clamp-6">
              {vm.deployment_notes.substring(0, 300)}
              {vm.deployment_notes.length > 300 && '...'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Metrics Tab Component
function MetricsTab({ metrics, isLoading }: { metrics?: Metric[]; isLoading: boolean }) {
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
      timestamp: format(new Date(metric.timestamp), 'HH:mm'),
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
        <h3 className="text-lg font-semibold text-white mb-4">CPU Usage Over Time</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="timestamp" stroke="#9CA3AF" />
            <YAxis stroke="#9CA3AF" domain={[0, 100]} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1F2937',
                border: '1px solid #374151',
                borderRadius: '0.5rem',
              }}
              labelStyle={{ color: '#F3F4F6' }}
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
        <h3 className="text-lg font-semibold text-white mb-4">RAM Usage Over Time</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="timestamp" stroke="#9CA3AF" />
            <YAxis stroke="#9CA3AF" domain={[0, 100]} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1F2937',
                border: '1px solid #374151',
                borderRadius: '0.5rem',
              }}
              labelStyle={{ color: '#F3F4F6' }}
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
        <h3 className="text-lg font-semibold text-white mb-4">Disk Usage Over Time</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="timestamp" stroke="#9CA3AF" />
            <YAxis stroke="#9CA3AF" domain={[0, 100]} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1F2937',
                border: '1px solid #374151',
                borderRadius: '0.5rem',
              }}
              labelStyle={{ color: '#F3F4F6' }}
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
          <p className="text-gray-400 text-sm">Loading ping history...</p>
        </div>
      </div>
    );
  }

  if (!pingHistory || pingHistory.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">No ping history available</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left py-3 px-4 text-sm font-semibold text-gray-300">
              Timestamp
            </th>
            <th className="text-left py-3 px-4 text-sm font-semibold text-gray-300">Status</th>
            <th className="text-left py-3 px-4 text-sm font-semibold text-gray-300">
              Response Time
            </th>
            <th className="text-left py-3 px-4 text-sm font-semibold text-gray-300">
              Error Type
            </th>
          </tr>
        </thead>
        <tbody>
          {pingHistory.map((ping) => (
            <tr
              key={ping.id}
              className={`border-b border-gray-700/50 ${
                ping.success ? 'bg-green-900/10' : 'bg-red-900/10'
              }`}
            >
              <td className="py-3 px-4 text-sm text-gray-300">
                {format(new Date(ping.timestamp), 'PPpp')}
              </td>
              <td className="py-3 px-4">
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    ping.success
                      ? 'bg-green-900/50 text-green-200 border border-green-500/50'
                      : 'bg-red-900/50 text-red-200 border border-red-500/50'
                  }`}
                >
                  {ping.success ? 'Success' : 'Failed'}
                </span>
              </td>
              <td className="py-3 px-4 text-sm text-gray-300">
                {ping.response_time_ms !== undefined && ping.response_time_ms !== null
                  ? `${ping.response_time_ms.toFixed(0)} ms`
                  : 'N/A'}
              </td>
              <td className="py-3 px-4 text-sm text-gray-400">
                {ping.error_type || '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Deployment Notes Tab Component
function DeploymentNotesTab({ notes }: { notes?: string }) {
  if (!notes || notes.trim() === '') {
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
            <ul className="list-disc list-inside text-gray-300 mb-4 space-y-1" {...props} />
          ),
          ol: ({ ...props }) => (
            <ol className="list-decimal list-inside text-gray-300 mb-4 space-y-1" {...props} />
          ),
          li: ({ ...props }) => <li className="text-gray-300" {...props} />,
          code: (props) => {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const { inline, ...rest } = props as { inline?: boolean; [key: string]: any };
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
            <pre className="bg-gray-700 rounded-lg overflow-x-auto mb-4" {...props} />
          ),
          a: ({ ...props }) => (
            <a className="text-blue-400 hover:text-blue-300 underline" {...props} />
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
          em: ({ ...props }) => <em className="italic text-gray-300" {...props} />,
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
  alertConfig?: AlertConfig;
  alertHistory?: Alert[];
  isConfigLoading: boolean;
  isHistoryLoading: boolean;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<AlertConfig>({
    enabled: true,
    webhook_url: '',
    email_recipient: '',
    cooldown_minutes: 15,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [successMessage, setSuccessMessage] = useState('');

  const updateAlertConfig = useUpdateAlertConfig();

  // Initialize form data when alert config loads
  useEffect(() => {
    if (alertConfig) {
      setFormData({
        enabled: alertConfig.enabled ?? true,
        webhook_url: alertConfig.webhook_url || '',
        email_recipient: alertConfig.email_recipient || '',
        cooldown_minutes: alertConfig.cooldown_minutes ?? 15,
      });
    }
  }, [alertConfig]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    // At least one notification method must be provided
    if (!formData.webhook_url && !formData.email_recipient) {
      newErrors.general = 'At least one notification method (webhook or email) must be provided';
    }

    // Validate webhook URL if provided
    if (formData.webhook_url && !isValidWebhookURL(formData.webhook_url)) {
      newErrors.webhook_url = 'Invalid webhook URL. Must be a valid HTTP or HTTPS URL';
    }

    // Validate email if provided
    if (formData.email_recipient && !isValidEmail(formData.email_recipient)) {
      newErrors.email_recipient = 'Invalid email address format';
    }

    // Validate cooldown period
    if (!isValidCooldownPeriod(formData.cooldown_minutes || 15)) {
      newErrors.cooldown_minutes = 'Cooldown period must be between 1 and 1440 minutes';
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
      setSuccessMessage('Alert configuration saved successfully');
      setIsEditing(false);
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (error) {
      setErrors({
        general: error instanceof Error ? error.message : 'Failed to save alert configuration',
      });
    }
  };

  const handleCancel = () => {
    // Reset form to current config
    if (alertConfig) {
      setFormData({
        enabled: alertConfig.enabled ?? true,
        webhook_url: alertConfig.webhook_url || '',
        email_recipient: alertConfig.email_recipient || '',
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
          <p className="text-gray-400 text-sm">Loading alert configuration...</p>
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
          <h3 className="text-lg font-semibold text-white">Alert Configuration</h3>
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
              <label className="text-sm font-medium text-gray-300">Enable Alerts</label>
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
                formData.enabled ? 'bg-blue-600' : 'bg-gray-600'
              } ${!isEditing ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              aria-label="Toggle alerts"
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  formData.enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Webhook URL */}
          <div>
            <label htmlFor="webhook_url" className="block text-sm font-medium text-gray-300 mb-2">
              Webhook URL
            </label>
            <input
              type="url"
              id="webhook_url"
              value={formData.webhook_url || ''}
              onChange={(e) => {
                setFormData({ ...formData, webhook_url: e.target.value });
                if (errors.webhook_url) {
                  setErrors({ ...errors, webhook_url: '' });
                }
              }}
              disabled={!isEditing}
              placeholder="https://example.com/webhook"
              className={`w-full px-4 py-2 bg-gray-700 border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed ${
                errors.webhook_url ? 'border-red-500' : 'border-gray-600'
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
              value={formData.email_recipient || ''}
              onChange={(e) => {
                setFormData({ ...formData, email_recipient: e.target.value });
                if (errors.email_recipient) {
                  setErrors({ ...errors, email_recipient: '' });
                }
              }}
              disabled={!isEditing}
              placeholder="alerts@example.com"
              className={`w-full px-4 py-2 bg-gray-700 border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed ${
                errors.email_recipient ? 'border-red-500' : 'border-gray-600'
              }`}
              aria-label="Email Recipient"
            />
            {errors.email_recipient && (
              <p className="text-red-400 text-xs mt-1">{errors.email_recipient}</p>
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
                setFormData({ ...formData, cooldown_minutes: parseInt(e.target.value, 10) });
                if (errors.cooldown_minutes) {
                  setErrors({ ...errors, cooldown_minutes: '' });
                }
              }}
              disabled={!isEditing}
              min="1"
              max="1440"
              className={`w-full px-4 py-2 bg-gray-700 border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed ${
                errors.cooldown_minutes ? 'border-red-500' : 'border-gray-600'
              }`}
              aria-label="Cooldown Period"
            />
            {errors.cooldown_minutes && (
              <p className="text-red-400 text-xs mt-1">{errors.cooldown_minutes}</p>
            )}
            <p className="text-xs text-gray-400 mt-1">
              Minimum time between alerts for the same VM (1-1440 minutes, default: 15)
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
                {updateAlertConfig.isPending ? 'Saving...' : 'Save Configuration'}
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
            <p className="text-gray-400">No alerts have been sent for this VM</p>
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
                      {format(new Date(alert.sent_at), 'PPpp')}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          alert.alert_type === 'VM_RECOVERED'
                            ? 'bg-green-900/50 text-green-200 border border-green-500/50'
                            : 'bg-yellow-900/50 text-yellow-200 border border-yellow-500/50'
                        }`}
                      >
                        {alert.alert_type.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-300 capitalize">
                      {alert.notification_method}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          alert.success
                            ? 'bg-green-900/50 text-green-200 border border-green-500/50'
                            : 'bg-red-900/50 text-red-200 border border-red-500/50'
                        }`}
                      >
                        {alert.success ? 'Sent' : 'Failed'}
                      </span>
                      {!alert.success && alert.error_message && (
                        <p className="text-xs text-red-400 mt-1">{alert.error_message}</p>
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
