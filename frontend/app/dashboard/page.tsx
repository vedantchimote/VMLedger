'use client';

import { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { formatDistanceToNow } from 'date-fns';
import { useAuth, useLogout } from '@/lib/hooks/use-auth';
import { useDashboard } from '@/lib/hooks/use-dashboard';
import { useVMSearch } from '@/lib/hooks/use-vms';
import type { VM } from '@/types/api';

// Custom hook for debounced value
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

export default function DashboardPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const logoutMutation = useLogout();
  const { data: allVms, isLoading, isError, error, isFetching } = useDashboard();

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'online' | 'offline'>('all');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  // Debounce search query (300ms)
  const debouncedSearchQuery = useDebounce(searchQuery, 300);

  // Search query hook
  const {
    data: searchResults,
    isLoading: isSearching,
    isFetching: isSearchFetching,
  } = useVMSearch(debouncedSearchQuery);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  // Determine which VMs to display
  const displayVms = useMemo(() => {
    let vms: VM[] = [];

    // Use search results if searching, otherwise use all VMs
    if (debouncedSearchQuery.trim()) {
      vms = searchResults?.map((result) => result.vm) || [];
    } else {
      vms = allVms || [];
    }

    // Apply status filter
    if (statusFilter !== 'all') {
      vms = vms.filter((vm) => {
        if (statusFilter === 'online') return vm.is_reachable === true;
        if (statusFilter === 'offline') return vm.is_reachable === false;
        return true;
      });
    }

    // Apply tag filter
    if (selectedTags.length > 0) {
      vms = vms.filter((vm) =>
        selectedTags.some((tag) => vm.tags.includes(tag))
      );
    }

    return vms;
  }, [debouncedSearchQuery, searchResults, allVms, statusFilter, selectedTags]);

  // Extract all unique tags from all VMs
  const allTags = useMemo(() => {
    const tags = new Set<string>();
    (allVms || []).forEach((vm) => {
      vm.tags.forEach((tag) => tags.add(tag));
    });
    return Array.from(tags).sort();
  }, [allVms]);

  // Clear search and filters
  const clearSearch = () => {
    setSearchQuery('');
    setStatusFilter('all');
    setSelectedTags([]);
  };

  // Toggle tag filter
  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  const handleLogout = () => {
    logoutMutation.mutate();
  };

  const formatLastSeen = (lastSeen: string | undefined): string => {
    if (!lastSeen) return 'Never';
    try {
      return formatDistanceToNow(new Date(lastSeen), { addSuffix: true });
    } catch {
      return 'Unknown';
    }
  };

  const formatMetric = (value: number | undefined, suffix: string = ''): string => {
    if (value === undefined || value === null) return 'N/A';
    return `${value}${suffix}`;
  };

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

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-2xl font-bold text-white">VMLedger</h1>
              {isFetching && !isLoading && (
                <span className="ml-4 text-xs text-gray-400 flex items-center">
                  <svg
                    className="animate-spin h-4 w-4 mr-1"
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
                  Refreshing...
                </span>
              )}
            </div>
            <div className="flex items-center gap-4">
              <Link
                href="/vms/new"
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors duration-200 text-sm font-medium"
              >
                Register New VM
              </Link>
              <button
                onClick={handleLogout}
                disabled={logoutMutation.isPending}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors duration-200 text-sm font-medium"
              >
                {logoutMutation.isPending ? 'Logging out...' : 'Logout'}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Search and Filters Section */}
        <div className="mb-8 space-y-4">
          {/* Search Input */}
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <svg
                className="h-5 w-5 text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search VMs by IP, hostname, domain, tags, or notes..."
              className="w-full pl-12 pr-12 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
              aria-label="Search VMs"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute inset-y-0 right-0 pr-4 flex items-center text-gray-400 hover:text-white transition-colors duration-200"
                aria-label="Clear search"
              >
                <svg
                  className="h-5 w-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            )}
            {(isSearching || isSearchFetching) && debouncedSearchQuery && (
              <div className="absolute inset-y-0 right-12 pr-4 flex items-center">
                <svg
                  className="animate-spin h-5 w-5 text-blue-500"
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
              </div>
            )}
          </div>

          {/* Filters Row */}
          <div className="flex flex-wrap gap-4 items-center">
            {/* Status Filter */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Status:</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setStatusFilter('all')}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors duration-200 ${
                    statusFilter === 'all'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  All
                </button>
                <button
                  onClick={() => setStatusFilter('online')}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors duration-200 ${
                    statusFilter === 'online'
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  Online
                </button>
                <button
                  onClick={() => setStatusFilter('offline')}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors duration-200 ${
                    statusFilter === 'offline'
                      ? 'bg-red-600 text-white'
                      : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  Offline
                </button>
              </div>
            </div>

            {/* Tag Filter */}
            {allTags.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm text-gray-400">Tags:</span>
                <div className="flex gap-2 flex-wrap">
                  {allTags.map((tag) => (
                    <button
                      key={tag}
                      onClick={() => toggleTag(tag)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors duration-200 ${
                        selectedTags.includes(tag)
                          ? 'bg-purple-600 text-white'
                          : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                      }`}
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Clear Filters Button */}
            {(searchQuery || statusFilter !== 'all' || selectedTags.length > 0) && (
              <button
                onClick={clearSearch}
                className="ml-auto px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm font-medium transition-colors duration-200"
              >
                Clear All
              </button>
            )}
          </div>

          {/* Search Results Count */}
          {debouncedSearchQuery && (
            <div className="text-sm text-gray-400">
              Found {displayVms.length} VM{displayVms.length !== 1 ? 's' : ''} matching &quot;
              {debouncedSearchQuery}&quot;
            </div>
          )}
        </div>
        {/* Loading State */}
        {isLoading && (
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
              <p className="text-gray-400">Loading your VMs...</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {isError && !isLoading && (
          <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-6">
            <h3 className="text-red-200 font-semibold mb-2">Failed to load VMs</h3>
            <p className="text-red-300 text-sm mb-4">
              {error instanceof Error ? error.message : 'An unexpected error occurred'}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors duration-200 text-sm font-medium"
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !isError && displayVms && displayVms.length === 0 && (
          <div className="bg-gray-800 rounded-lg shadow-xl p-12 border border-gray-700 text-center">
            <div className="max-w-md mx-auto">
              {debouncedSearchQuery || statusFilter !== 'all' || selectedTags.length > 0 ? (
                <>
                  <svg
                    className="mx-auto h-16 w-16 text-gray-600 mb-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                    />
                  </svg>
                  <h3 className="text-2xl font-bold text-white mb-2">No results found</h3>
                  <p className="text-gray-400 mb-6">
                    No VMs match your search criteria. Try adjusting your filters or search query.
                  </p>
                  <button
                    onClick={clearSearch}
                    className="inline-block px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors duration-200 font-medium"
                  >
                    Clear Filters
                  </button>
                </>
              ) : (
                <>
                  <svg
                    className="mx-auto h-16 w-16 text-gray-600 mb-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"
                    />
                  </svg>
                  <h3 className="text-2xl font-bold text-white mb-2">No VMs registered yet</h3>
                  <p className="text-gray-400 mb-6">
                    Get started by registering your first virtual machine to begin monitoring your
                    infrastructure.
                  </p>
                  <Link
                    href="/vms/new"
                    className="inline-block px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors duration-200 font-medium"
                  >
                    Register Your First VM
                  </Link>
                </>
              )}
            </div>
          </div>
        )}

        {/* VM Grid */}
        {!isLoading && !isError && displayVms && displayVms.length > 0 && (
          <div>
            <div className="mb-6 flex justify-between items-center">
              <h2 className="text-2xl font-bold text-white">
                {debouncedSearchQuery
                  ? `Search Results (${displayVms.length})`
                  : `Your Virtual Machines (${displayVms.length})`}
              </h2>
              <p className="text-sm text-gray-400">Auto-refreshes every 30 seconds</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {displayVms.map((vm: VM) => (
                <div
                  key={vm.id}
                  className="bg-gray-800 rounded-lg shadow-xl border border-gray-700 hover:border-gray-600 transition-all duration-200 overflow-hidden group"
                >
                  {/* VM Card Header */}
                  <div className="p-6 border-b border-gray-700">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-xl font-bold text-white truncate mb-1">
                          {vm.hostname}
                        </h3>
                        <p className="text-sm text-gray-400 truncate">{vm.ip_address}</p>
                      </div>
                      <div className="flex items-center gap-2 ml-3">
                        <div
                          className={`w-3 h-3 rounded-full ${getStatusColor(vm.is_reachable)} shadow-lg`}
                          title={getStatusText(vm.is_reachable)}
                          aria-label={getStatusText(vm.is_reachable)}
                        ></div>
                      </div>
                    </div>

                    {/* Status Badge */}
                    <div className="flex items-center gap-2 flex-wrap">
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
                      {vm.domain && (
                        <span className="text-xs text-gray-500 truncate">{vm.domain}</span>
                      )}
                    </div>

                    {/* Tags */}
                    {vm.tags && vm.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {vm.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-900/50 text-purple-200 border border-purple-500/50"
                          >
                            {tag}
                          </span>
                        ))}
                        {vm.tags.length > 3 && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-700 text-gray-300">
                            +{vm.tags.length - 3} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* VM Metrics */}
                  <div className="p-6 space-y-4">
                    {/* CPU Usage */}
                    <div>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-sm text-gray-400">CPU Usage</span>
                        <span className="text-sm font-medium text-white">
                          {formatMetric(vm.latest_cpu, '%')}
                        </span>
                      </div>
                      {vm.latest_cpu !== undefined && vm.latest_cpu !== null && (
                        <div className="w-full bg-gray-700 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full transition-all duration-300 ${
                              vm.latest_cpu > 80
                                ? 'bg-red-500'
                                : vm.latest_cpu > 60
                                ? 'bg-yellow-500'
                                : 'bg-green-500'
                            }`}
                            style={{ width: `${Math.min(vm.latest_cpu, 100)}%` }}
                          ></div>
                        </div>
                      )}
                    </div>

                    {/* RAM Usage */}
                    <div>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-sm text-gray-400">RAM Usage</span>
                        <span className="text-sm font-medium text-white">
                          {vm.latest_ram_used !== undefined &&
                          vm.latest_ram_total !== undefined
                            ? `${vm.latest_ram_used} / ${vm.latest_ram_total} MB`
                            : 'N/A'}
                        </span>
                      </div>
                      {vm.latest_ram_used !== undefined &&
                        vm.latest_ram_total !== undefined &&
                        vm.latest_ram_total > 0 && (
                          <div className="w-full bg-gray-700 rounded-full h-2">
                            <div
                              className={`h-2 rounded-full transition-all duration-300 ${
                                (vm.latest_ram_used / vm.latest_ram_total) * 100 > 80
                                  ? 'bg-red-500'
                                  : (vm.latest_ram_used / vm.latest_ram_total) * 100 > 60
                                  ? 'bg-yellow-500'
                                  : 'bg-blue-500'
                              }`}
                              style={{
                                width: `${Math.min(
                                  (vm.latest_ram_used / vm.latest_ram_total) * 100,
                                  100
                                )}%`,
                              }}
                            ></div>
                          </div>
                        )}
                    </div>

                    {/* Disk Usage */}
                    <div>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-sm text-gray-400">Disk Usage</span>
                        <span className="text-sm font-medium text-white">
                          {formatMetric(vm.latest_disk_percent, '%')}
                        </span>
                      </div>
                      {vm.latest_disk_percent !== undefined &&
                        vm.latest_disk_percent !== null && (
                          <div className="w-full bg-gray-700 rounded-full h-2">
                            <div
                              className={`h-2 rounded-full transition-all duration-300 ${
                                vm.latest_disk_percent > 80
                                  ? 'bg-red-500'
                                  : vm.latest_disk_percent > 60
                                  ? 'bg-yellow-500'
                                  : 'bg-purple-500'
                              }`}
                              style={{
                                width: `${Math.min(vm.latest_disk_percent, 100)}%`,
                              }}
                            ></div>
                          </div>
                        )}
                    </div>

                    {/* Last Seen */}
                    <div className="pt-2 border-t border-gray-700">
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-gray-500">Last seen</span>
                        <span className="text-xs text-gray-400">
                          {formatLastSeen(vm.last_seen)}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* VM Card Actions */}
                  <div className="px-6 py-4 bg-gray-750 border-t border-gray-700 flex gap-2">
                    <Link
                      href={`/vms/${vm.id}/edit`}
                      className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-center rounded-lg transition-colors duration-200 text-sm font-medium"
                    >
                      Edit
                    </Link>
                    <button
                      onClick={() => router.push(`/vms/${vm.id}`)}
                      className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors duration-200 text-sm font-medium"
                    >
                      Details
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
