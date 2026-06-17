"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { useAuth, useLogout } from "@/lib/hooks/use-auth";
import { useDashboard } from "@/lib/hooks/use-dashboard";
import { useVMSearch, useDeleteVM } from "@/lib/hooks/use-vms";
import type { VM } from "@/types/api";
import { KanbanCard } from "./KanbanCard";
import GlobalNotificationBell from "@/components/GlobalNotificationBell";

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
  const { isAuthenticated, isMounted } = useAuth();
  const logoutMutation = useLogout();
  const deleteMutation = useDeleteVM();
  const [isDeleting, setIsDeleting] = useState(false);
  
  // Selection state
  const [selectedVms, setSelectedVms] = useState<number[]>([]);

  const handleBulkDelete = async () => {
    if (!window.confirm(`Are you sure you want to delete ${selectedVms.length} selected VM(s)? This action cannot be undone.`)) return;
    setIsDeleting(true);
    try {
      await Promise.all(selectedVms.map(id => deleteMutation.mutateAsync(id)));
      setSelectedVms([]);
    } catch (err) {
      alert("Failed to delete some VMs. Please try again.");
    } finally {
      setIsDeleting(false);
    }
  };

  const toggleSelection = (id: number) => {
    setSelectedVms(prev => prev.includes(id) ? prev.filter(v => v !== id) : [...prev, id]);
  };

  const toggleSelectAll = (ids: number[]) => {
    if (selectedVms.length === ids.length) {
      setSelectedVms([]);
    } else {
      setSelectedVms(ids);
    }
  };

  const {
    data: allVms,
    isLoading,
    isError,
    error,
    isFetching,
  } = useDashboard();

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<
    "all" | "online" | "offline"
  >("all");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [viewMode, setViewMode] = useState<
    "grid" | "list" | "table" | "kanban" | "minimal" | "analytics"
  >("grid");

  // Debounce search query (300ms)
  const debouncedSearchQuery = useDebounce(searchQuery, 300);

  // Search query hook
  const {
    data: searchResults,
    isLoading: isSearching,
    isFetching: isSearchFetching,
  } = useVMSearch(debouncedSearchQuery);

  useEffect(() => {
    // Only redirect after we've checked localStorage
    if (isMounted && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isMounted, router]);

  // Determine which VMs to display
  const displayVms = useMemo(() => {
    let vms: VM[] = [];

    // Use search results if searching, otherwise use all VMs
    if (debouncedSearchQuery && searchResults) {
      // Search API returns VMs without metrics — enrich from dashboard data
      const dashboardMap = new Map((allVms || []).map(vm => [vm.id, vm]));
      vms = searchResults.map((result) => {
        const dashVm = dashboardMap.get(result.vm.id);
        return dashVm ? { ...dashVm, ...result.vm, latest_cpu: dashVm.latest_cpu, latest_ram_used: dashVm.latest_ram_used, latest_ram_total: dashVm.latest_ram_total, latest_disk_percent: dashVm.latest_disk_percent, latest_disk_used_gb: dashVm.latest_disk_used_gb, latest_disk_total_gb: dashVm.latest_disk_total_gb, latest_response_time_ms: dashVm.latest_response_time_ms } : result.vm;
      });
    } else {
      vms = allVms || [];
    }

    // Apply status filter
    if (statusFilter !== "all") {
      vms = vms.filter((vm) => {
        if (statusFilter === "online") return vm.is_reachable === true;
        if (statusFilter === "offline") return vm.is_reachable === false;
        return true;
      });
    }

    // Apply tag filter
    if (selectedTags.length > 0) {
      vms = vms.filter((vm) =>
        selectedTags.every((tag) => vm.tags?.includes(tag)),
      );
    }

    return vms;
  }, [allVms, searchResults, debouncedSearchQuery, statusFilter, selectedTags]);

  // Collect unique tags from all VMs
  const availableTags = useMemo(() => {
    const tags = new Set<string>();
    (allVms || []).forEach((vm) => {
      vm.tags?.forEach((tag) => tags.add(tag));
    });
    return Array.from(tags).sort();
  }, [allVms]);

  // Clear search and filters
  const clearSearch = () => {
    setSearchQuery("");
    setStatusFilter("all");
    setSelectedTags([]);
  };

  // Toggle tag filter
  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
    );
  };

  // Redirect to login if not authenticated after mount
  useEffect(() => {
    if (isMounted && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isMounted, isAuthenticated, router]);

  // Show loading while checking auth state
  if (!isMounted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-white/20 border-t-white rounded-full animate-spin" />
          <div className="text-white/60 text-sm">Loading...</div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-white/60 text-sm">Redirecting to login...</div>
      </div>
    );
  }

  const handleLogout = () => {
    logoutMutation.mutate();
  };

  const formatLastSeen = (lastSeen: string | undefined): string => {
    if (!lastSeen) return "Never";
    try {
      return formatDistanceToNow(new Date(lastSeen), { addSuffix: true });
    } catch {
      return "Unknown";
    }
  };

  const formatMetric = (
    value: number | undefined,
    suffix: string = "",
  ): string => {
    if (value === undefined || value === null) return "N/A";
    return `${value}${suffix}`;
  };

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

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-surface-950/60 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-20">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 shadow-lg shadow-brand-500/20">
                <svg
                  className="w-6 h-6 text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"
                  />
                </svg>
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-white">
                VM<span className="text-brand-400">Ledger</span>
              </h1>
              {isFetching && !isLoading && (
                <span className="ml-4 text-xs font-medium text-brand-400 flex items-center animate-pulse-slow">
                  <span className="relative flex h-2 w-2 mr-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-500"></span>
                  </span>
                  Syncing
                </span>
              )}
            </div>
            <div className="flex items-center gap-4">
              <GlobalNotificationBell />
              {selectedVms.length > 0 && (
                <button
                  onClick={handleBulkDelete}
                  disabled={isDeleting}
                  className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 rounded-xl transition-all font-semibold flex items-center gap-2 border border-red-500/20 shadow-lg shadow-red-500/5"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                  {isDeleting ? "Deleting..." : `Remove (${selectedVms.length})`}
                </button>
              )}
              <Link href="/vms/new" className="btn-primary">
                <svg
                  className="w-4 h-4 mr-2"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                Register VM
              </Link>
              <button
                onClick={handleLogout}
                disabled={logoutMutation.isPending}
                className="btn-secondary"
              >
                {logoutMutation.isPending ? "Signing out..." : "Sign out"}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 animate-fade-in">
        {/* Search and Filters Section */}
        <div className="mb-10 space-y-6">
          <div className="flex flex-col md:flex-row gap-4 justify-between items-start md:items-center">
            <div>
              <h2 className="text-3xl font-bold text-white tracking-tight mb-1">
                {debouncedSearchQuery
                  ? `Search Results (${displayVms.length})`
                  : `Infrastructure (${displayVms.length})`}
              </h2>
              <p className="text-sm text-gray-400">
                Manage and monitor your virtual machines in real-time.
              </p>
            </div>
          </div>

          <div className="glass-panel p-2 flex flex-col md:flex-row gap-4 items-center">
            {/* Search Input */}
            <div className="relative w-full md:w-96">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <svg
                  className="h-5 w-5 text-gray-500"
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
                placeholder="Search instances, tags, IPs..."
                className="input-premium pl-11 py-2.5 text-sm"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute inset-y-0 right-0 pr-4 flex items-center text-gray-500 hover:text-white transition-colors"
                >
                  <svg
                    className="h-4 w-4"
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
            </div>

            {/* Status Filters */}
            <div className="flex items-center gap-1.5 p-1 bg-surface-900/50 rounded-xl border border-white/5">
              {(["all", "online", "offline"] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
                    statusFilter === status
                      ? "bg-surface-700 text-white shadow-sm border border-white/10"
                      : "text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent"
                  }`}
                >
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                </button>
              ))}
            </div>

            {/* View Mode Toggle */}
            <div className="flex items-center gap-1.5 p-1 bg-surface-900/50 rounded-xl border border-white/5">
              <button
                onClick={() => setViewMode("grid")}
                className={`p-1.5 rounded-lg transition-all ${viewMode === "grid" ? "bg-surface-700 text-white shadow-sm border border-white/10" : "text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent"}`}
                title="Grid View"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                </svg>
              </button>
              <button
                onClick={() => setViewMode("list")}
                className={`p-1.5 rounded-lg transition-all ${viewMode === "list" ? "bg-surface-700 text-white shadow-sm border border-white/10" : "text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent"}`}
                title="List View"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <button
                onClick={() => setViewMode("table")}
                className={`p-1.5 rounded-lg transition-all ${viewMode === "table" ? "bg-surface-700 text-white shadow-sm border border-white/10" : "text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent"}`}
                title="Table View"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
              <button
                onClick={() => setViewMode("kanban")}
                className={`p-1.5 rounded-lg transition-all ${viewMode === "kanban" ? "bg-surface-700 text-white shadow-sm border border-white/10" : "text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent"}`}
                title="Status Board"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
                </svg>
              </button>
              <button
                onClick={() => setViewMode("minimal")}
                className={`p-1.5 rounded-lg transition-all ${viewMode === "minimal" ? "bg-surface-700 text-white shadow-sm border border-white/10" : "text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent"}`}
                title="Minimal View"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                </svg>
              </button>
              <button
                onClick={() => setViewMode("analytics")}
                className={`p-1.5 rounded-lg transition-all ${viewMode === "analytics" ? "bg-surface-700 text-white shadow-sm border border-white/10" : "text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent"}`}
                title="Analytics Summary"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </button>
            </div>

            {/* Tag Filters */}
            {availableTags.length > 0 && (
              <div className="flex items-center gap-2 overflow-x-auto pb-2 md:pb-0 hide-scrollbar flex-1">
                <div className="h-6 w-px bg-white/10 mx-2 hidden md:block"></div>
                {availableTags.map((tag) => (
                  <button
                    key={tag}
                    onClick={() => toggleTag(tag)}
                    className={`whitespace-nowrap px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${
                      selectedTags.includes(tag)
                        ? "bg-brand-500/20 border-brand-500/50 text-brand-300 shadow-inner"
                        : "bg-transparent border-white/10 text-gray-400 hover:border-white/20 hover:text-gray-300 hover:bg-white/5"
                    }`}
                  >
                    #{tag}
                  </button>
                ))}
              </div>
            )}

            {(searchQuery ||
              statusFilter !== "all" ||
              selectedTags.length > 0) && (
              <button
                onClick={clearSearch}
                className="px-4 py-1.5 text-sm text-gray-400 hover:text-white transition-colors ml-auto whitespace-nowrap"
              >
                Clear All
              </button>
            )}
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <div className="relative w-16 h-16 mx-auto mb-6">
                <div className="absolute inset-0 rounded-full border-t-2 border-brand-500 animate-spin"></div>
                <div
                  className="absolute inset-2 rounded-full border-r-2 border-brand-300 animate-spin"
                  style={{
                    animationDirection: "reverse",
                    animationDuration: "1.5s",
                  }}
                ></div>
              </div>
              <p className="text-gray-400 text-sm tracking-wide uppercase">
                Initializing Workspace...
              </p>
            </div>
          </div>
        )}

        {/* Error State */}
        {isError && !isLoading && (
          <div className="glass-card p-8 border-red-500/20 bg-red-500/5 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 mb-4">
              <svg
                className="w-8 h-8 text-red-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h3 className="text-xl font-bold text-white mb-2">
              Connection Interrupted
            </h3>
            <p className="text-red-200/70 mb-6 max-w-md mx-auto">
              {error instanceof Error
                ? error.message
                : "Unable to connect to the infrastructure ledger."}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="btn-secondary"
            >
              Retry Connection
            </button>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !isError && displayVms && displayVms.length === 0 && (
          <div className="glass-card p-16 text-center">
            <div className="max-w-md mx-auto">
              {debouncedSearchQuery ||
              statusFilter !== "all" ||
              selectedTags.length > 0 ? (
                <>
                  <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-surface-800 border border-white/5 mb-6">
                    <svg
                      className="h-10 w-10 text-gray-500"
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
                  </div>
                  <h3 className="text-2xl font-bold text-white mb-2 tracking-tight">
                    No Instances Found
                  </h3>
                  <p className="text-gray-400 mb-8 leading-relaxed">
                    We couldn&apos;t find any virtual machines matching your
                    current filter criteria.
                  </p>
                  <button onClick={clearSearch} className="btn-secondary">
                    Clear Filters
                  </button>
                </>
              ) : (
                <>
                  <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-gradient-to-br from-brand-500/20 to-brand-700/20 border border-brand-500/20 mb-8 shadow-inner shadow-brand-500/10">
                    <svg
                      className="h-12 w-12 text-brand-400"
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
                  </div>
                  <h3 className="text-3xl font-bold text-white mb-3 tracking-tight">
                    Empty Ledger
                  </h3>
                  <p className="text-gray-400 mb-8 leading-relaxed">
                    You haven&apos;t added any instances to your ledger yet.
                    Deploy your first virtual machine to start monitoring.
                  </p>
                  <Link
                    href="/vms/new"
                    className="btn-primary px-8 py-3.5 text-base"
                  >
                    Register First VM
                  </Link>
                </>
              )}
            </div>
          </div>
        )}

        {/* Render Views */}
        {!isLoading && !isError && displayVms && displayVms.length > 0 && (
          <>
            {viewMode === "grid" && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {displayVms.map((vm: VM, idx) => (
                  <div
                    key={vm.id}
                    className="glass-card group flex flex-col h-full"
                    style={{ animationDelay: `${idx * 50}ms` }}
                  >
                    {/* VM Card Header */}
                    <div className="p-6 pb-5 flex-grow relative">
                      <div className="flex items-start justify-between mb-4 gap-4">
                        <div className="flex-1 min-w-0 flex items-start gap-3">
                          <input 
                            type="checkbox" 
                            checked={selectedVms.includes(vm.id)}
                            onChange={() => toggleSelection(vm.id)}
                            className="mt-1.5 w-4 h-4 rounded border-white/20 bg-surface-800/50 text-brand-500 focus:ring-brand-500/50 focus:ring-offset-0 transition-colors cursor-pointer"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-3 mb-1">
                              <Link href={`/vms/${vm.id}`} className="text-lg font-bold text-white truncate tracking-tight hover:text-brand-300 transition-colors">
                                {vm.hostname}
                              </Link>
                            </div>
                            <div className="flex items-center gap-2 text-sm text-gray-400">
                              <svg className="w-4 h-4 opacity-70" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                              </svg>
                              <span className="truncate font-mono text-xs">{vm.ip_address}</span>
                            </div>
                          </div>
                        </div>
                        <span className={vm.is_reachable === true ? "status-badge-online" : vm.is_reachable === false ? "status-badge-offline" : "status-badge-unknown"}>
                          <span className={`w-1.5 h-1.5 rounded-full ${vm.is_reachable === true ? "bg-brand-500 animate-pulse" : vm.is_reachable === false ? "bg-red-500" : "bg-gray-500"}`}></span>
                          {getStatusText(vm.is_reachable)}
                        </span>
                        {vm.dns_mismatch && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 rounded-md text-[9px] font-bold uppercase tracking-wider" title={`DNS resolves to ${vm.resolved_ip}`}>
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01" /></svg>
                            DNS Drift
                          </span>
                        )}
                      </div>
                      {/* Tags */}
                      {vm.tags && vm.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-4">
                          {vm.tags.slice(0, 3).map((tag) => (
                            <span key={tag} className="px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase bg-surface-800 text-gray-300 border border-white/5">{tag}</span>
                          ))}
                          {vm.tags.length > 3 && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-surface-800 text-gray-400 border border-white/5">+{vm.tags.length - 3}</span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* VM Metrics */}
                    <div className="px-6 py-5 bg-surface-900/30 border-y border-white/5 space-y-4 flex-grow">
                      <div>
                        <div className="flex justify-between items-center mb-1.5">
                          <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">CPU</span>
                          <span className="text-xs font-bold text-white font-mono">{formatMetric(vm.latest_cpu, "%")}</span>
                        </div>
                        {vm.latest_cpu !== undefined && vm.latest_cpu !== null ? (
                          <div className="w-full bg-surface-800 rounded-full h-1.5 overflow-hidden">
                            <div className={`h-full rounded-full transition-all duration-700 ease-out ${vm.latest_cpu > 85 ? "bg-gradient-to-r from-red-500 to-rose-500" : vm.latest_cpu > 65 ? "bg-gradient-to-r from-yellow-500 to-amber-500" : "bg-gradient-to-r from-brand-500 to-teal-400"}`} style={{ width: `${Math.min(vm.latest_cpu, 100)}%` }}></div>
                          </div>
                        ) : (
                          <div className="w-full bg-surface-800 rounded-full h-1.5"></div>
                        )}
                      </div>
                      <div>
                        <div className="flex justify-between items-center mb-1.5">
                          <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Memory</span>
                          <span className="text-xs font-bold text-white font-mono">{vm.latest_ram_used !== undefined && vm.latest_ram_total !== undefined && vm.latest_ram_total > 0 ? `${Math.round((vm.latest_ram_used / vm.latest_ram_total) * 100)}%` : "N/A"}</span>
                        </div>
                        {vm.latest_ram_used !== undefined && vm.latest_ram_total !== undefined && vm.latest_ram_total > 0 ? (
                          <div className="w-full bg-surface-800 rounded-full h-1.5 overflow-hidden">
                            <div className={`h-full rounded-full transition-all duration-700 ease-out ${(vm.latest_ram_used / vm.latest_ram_total) * 100 > 85 ? "bg-gradient-to-r from-red-500 to-rose-500" : (vm.latest_ram_used / vm.latest_ram_total) * 100 > 65 ? "bg-gradient-to-r from-yellow-500 to-amber-500" : "bg-gradient-to-r from-blue-500 to-indigo-400"}`} style={{ width: `${Math.min((vm.latest_ram_used / vm.latest_ram_total) * 100, 100)}%` }}></div>
                          </div>
                        ) : (
                          <div className="w-full bg-surface-800 rounded-full h-1.5"></div>
                        )}
                      </div>
                      <div>
                        <div className="flex justify-between items-center mb-1.5">
                          <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Disk</span>
                          <span className="text-xs font-bold text-white font-mono">{formatMetric(vm.latest_disk_percent, "%")}</span>
                        </div>
                        {vm.latest_disk_percent !== undefined && vm.latest_disk_percent !== null ? (
                          <div className="w-full bg-surface-800 rounded-full h-1.5 overflow-hidden">
                            <div className={`h-full rounded-full transition-all duration-700 ease-out ${vm.latest_disk_percent > 85 ? "bg-gradient-to-r from-red-500 to-rose-500" : vm.latest_disk_percent > 65 ? "bg-gradient-to-r from-yellow-500 to-amber-500" : "bg-gradient-to-r from-emerald-500 to-teal-400"}`} style={{ width: `${Math.min(vm.latest_disk_percent, 100)}%` }}></div>
                          </div>
                        ) : (
                          <div className="w-full bg-surface-800 rounded-full h-1.5"></div>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="px-6 py-4 flex items-center justify-between">
                      <div className="text-[11px] font-medium text-gray-500 uppercase tracking-wider">
                        {vm.is_reachable ? "Active " : "Seen "} {formatLastSeen(vm.last_seen)}
                      </div>
                      <div className="flex gap-2">
                        <Link href={`/vms/${vm.id}/terminal`} className="px-4 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-white/5 flex items-center gap-1.5" title="Quick Connect (SSH)">
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                        </Link>
                        <Link href={`/vms/${vm.id}/edit`} className="px-4 py-1.5 bg-surface-800 hover:bg-surface-700 text-gray-300 hover:text-white rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-white/5 flex items-center gap-1.5">
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                          Edit
                        </Link>
                        <button onClick={() => router.push(`/vms/${vm.id}`)} className="px-4 py-1.5 bg-brand-500/10 hover:bg-brand-500/20 text-brand-400 hover:text-brand-300 rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-brand-500/20">Metrics</button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {viewMode === "list" && (
              <div className="flex flex-col gap-4">
                {displayVms.map((vm: VM, idx) => (
                  <div key={vm.id} className="glass-card group flex flex-col md:flex-row items-center p-4 gap-6" style={{ animationDelay: `${idx * 50}ms` }}>
                    <div className="flex-1 min-w-0 flex items-center gap-4">
                      <input 
                        type="checkbox" 
                        checked={selectedVms.includes(vm.id)}
                        onChange={() => toggleSelection(vm.id)}
                        className="w-4 h-4 rounded border-white/20 bg-surface-800/50 text-brand-500 focus:ring-brand-500/50 focus:ring-offset-0 transition-colors cursor-pointer"
                      />
                      <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${vm.is_reachable === true ? "bg-brand-500 shadow-[0_0_8px_rgba(20,184,166,0.6)] animate-pulse" : vm.is_reachable === false ? "bg-red-500" : "bg-gray-500"}`}></span>
                      <div>
                        <Link href={`/vms/${vm.id}`} className="text-base font-bold text-white truncate tracking-tight hover:text-brand-300 transition-colors block">
                          {vm.hostname}
                        </Link>
                        <div className="flex items-center gap-2 text-xs text-gray-400"><span className="font-mono">{vm.ip_address}</span></div>
                      </div>
                    </div>
                    <div className="flex-1 flex items-center gap-6 hidden md:flex">
                      <div className="flex-1">
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">CPU</span>
                          <span className="text-[10px] font-bold text-white font-mono">{formatMetric(vm.latest_cpu, "%")}</span>
                        </div>
                        <div className="w-full bg-surface-800 rounded-full h-1 overflow-hidden">
                          <div className={`h-full rounded-full transition-all duration-700 ease-out ${vm.latest_cpu !== undefined && vm.latest_cpu > 85 ? "bg-red-500" : vm.latest_cpu !== undefined && vm.latest_cpu > 65 ? "bg-yellow-500" : "bg-brand-500"}`} style={{ width: `${Math.min(vm.latest_cpu || 0, 100)}%` }}></div>
                        </div>
                      </div>
                      <div className="flex-1">
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">RAM</span>
                          <span className="text-[10px] font-bold text-white font-mono">{vm.latest_ram_used !== undefined && vm.latest_ram_total !== undefined && vm.latest_ram_total > 0 ? `${Math.round((vm.latest_ram_used / vm.latest_ram_total) * 100)}%` : "N/A"}</span>
                        </div>
                        <div className="w-full bg-surface-800 rounded-full h-1 overflow-hidden">
                          <div className={`h-full rounded-full transition-all duration-700 ease-out ${vm.latest_ram_used && vm.latest_ram_total && (vm.latest_ram_used / vm.latest_ram_total) * 100 > 85 ? "bg-red-500" : vm.latest_ram_used && vm.latest_ram_total && (vm.latest_ram_used / vm.latest_ram_total) * 100 > 65 ? "bg-yellow-500" : "bg-blue-500"}`} style={{ width: `${Math.min(((vm.latest_ram_used || 0) / (vm.latest_ram_total || 1)) * 100, 100)}%` }}></div>
                        </div>
                      </div>
                      <div className="flex-1">
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">Disk</span>
                          <span className="text-[10px] font-bold text-white font-mono">{formatMetric(vm.latest_disk_percent, "%")}</span>
                        </div>
                        <div className="w-full bg-surface-800 rounded-full h-1 overflow-hidden">
                          <div className={`h-full rounded-full transition-all duration-700 ease-out ${vm.latest_disk_percent !== undefined && vm.latest_disk_percent > 85 ? "bg-red-500" : vm.latest_disk_percent !== undefined && vm.latest_disk_percent > 65 ? "bg-yellow-500" : "bg-emerald-500"}`} style={{ width: `${Math.min(vm.latest_disk_percent || 0, 100)}%` }}></div>
                        </div>
                      </div>
                    </div>
                    <div className="hidden lg:flex w-48 flex-wrap gap-1">
                      {vm.tags?.slice(0, 2).map((tag) => (
                        <span key={tag} className="px-1.5 py-0.5 rounded text-[9px] font-semibold tracking-wider uppercase bg-surface-800 text-gray-300 border border-white/5">{tag}</span>
                      ))}
                      {vm.tags && vm.tags.length > 2 && (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-surface-800 text-gray-400 border border-white/5">+{vm.tags.length - 2}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Link href={`/vms/${vm.id}/terminal`} className="px-3 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-white/5 flex items-center gap-1" title="Quick Connect (SSH)">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                      </Link>
                      <Link href={`/vms/${vm.id}/edit`} className="px-3 py-1 bg-surface-800 hover:bg-surface-700 text-gray-300 hover:text-white rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-white/5 flex items-center gap-1">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                        Edit
                      </Link>
                      <button onClick={() => router.push(`/vms/${vm.id}`)} className="px-3 py-1 bg-brand-500/10 hover:bg-brand-500/20 text-brand-400 hover:text-brand-300 rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-brand-500/20">Metrics</button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {viewMode === "table" && (
              <div className="overflow-x-auto w-full glass-panel p-0 rounded-xl border border-white/5">
                <table className="w-full text-left text-sm text-gray-300">
                  <thead className="text-[10px] uppercase tracking-wider bg-surface-800 text-gray-400 border-b border-white/5">
                    <tr>
                      <th className="px-6 py-4 w-4">
                        <input 
                          type="checkbox" 
                          checked={displayVms.length > 0 && selectedVms.length === displayVms.length}
                          onChange={() => toggleSelectAll(displayVms.map(v => v.id))}
                          className="w-4 h-4 rounded border-white/20 bg-surface-800/50 text-brand-500 focus:ring-brand-500/50 focus:ring-offset-0 transition-colors cursor-pointer"
                        />
                      </th>
                      <th className="px-6 py-4 font-bold">Status</th>
                      <th className="px-6 py-4 font-bold">Hostname</th>
                      <th className="px-6 py-4 font-bold">IP Address</th>
                      <th className="px-6 py-4 font-bold">CPU</th>
                      <th className="px-6 py-4 font-bold">Memory</th>
                      <th className="px-6 py-4 font-bold">Disk</th>
                      <th className="px-6 py-4 font-bold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayVms.map((vm, idx) => (
                      <tr key={vm.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                        <td className="px-6 py-4">
                          <input 
                            type="checkbox" 
                            checked={selectedVms.includes(vm.id)}
                            onChange={() => toggleSelection(vm.id)}
                            className="w-4 h-4 rounded border-white/20 bg-surface-800/50 text-brand-500 focus:ring-brand-500/50 focus:ring-offset-0 transition-colors cursor-pointer"
                          />
                        </td>
                        <td className="px-6 py-4">
                          <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider ${vm.is_reachable === true ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : vm.is_reachable === false ? "bg-red-500/10 text-red-400 border border-red-500/20" : "bg-gray-500/10 text-gray-400 border border-gray-500/20"}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${vm.is_reachable === true ? "bg-brand-500 animate-pulse" : vm.is_reachable === false ? "bg-red-500" : "bg-gray-500"}`}></span>
                            {getStatusText(vm.is_reachable)}
                          </span>
                        </td>
                        <td className="px-6 py-4 font-bold text-white">
                          <Link href={`/vms/${vm.id}`} className="hover:text-brand-300 transition-colors">
                            {vm.hostname}
                          </Link>
                        </td>
                        <td className="px-6 py-4 font-mono text-xs">{vm.ip_address}</td>
                        <td className="px-6 py-4 font-mono text-xs text-brand-400 font-semibold">{formatMetric(vm.latest_cpu, "%")}</td>
                        <td className="px-6 py-4 font-mono text-xs text-blue-400 font-semibold">
                          {vm.latest_ram_used !== undefined && vm.latest_ram_total !== undefined && vm.latest_ram_total > 0 ? `${Math.round((vm.latest_ram_used / vm.latest_ram_total) * 100)}%` : "N/A"}
                        </td>
                        <td className="px-6 py-4 font-mono text-xs text-emerald-400 font-semibold">{formatMetric(vm.latest_disk_percent, "%")}</td>
                        <td className="px-6 py-4 flex justify-end gap-2">
                          <Link href={`/vms/${vm.id}/terminal`} className="px-3 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-white/5 flex items-center gap-1" title="Quick Connect (SSH)">
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                          </Link>
                          <Link href={`/vms/${vm.id}/edit`} className="px-3 py-1 bg-surface-800 hover:bg-surface-700 text-gray-300 hover:text-white rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-white/5 flex items-center gap-1">
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                            Edit
                          </Link>
                          <button onClick={() => router.push(`/vms/${vm.id}`)} className="px-3 py-1 bg-brand-500/10 hover:bg-brand-500/20 text-brand-400 hover:text-brand-300 rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-brand-500/20">Metrics</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {viewMode === "kanban" && (
              <div className="flex gap-6 overflow-x-auto pb-4 items-start w-full">
                {/* Online Column */}
                <div className="w-80 flex-shrink-0 flex flex-col gap-4 bg-surface-900/30 p-4 rounded-2xl border border-white/5">
                  <div className="flex items-center gap-2 mb-2 pb-2 border-b border-white/5">
                    <span className="w-2.5 h-2.5 rounded-full bg-brand-500 animate-pulse shadow-[0_0_8px_rgba(20,184,166,0.6)]"></span>
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">Online</h3>
                    <span className="ml-auto bg-surface-800 text-gray-400 font-mono text-xs px-2.5 py-0.5 rounded-full border border-white/5">{displayVms.filter(v => v.is_reachable === true).length}</span>
                  </div>
                  {displayVms.filter(v => v.is_reachable === true).map(vm => (
                    <KanbanCard key={vm.id} vm={vm} router={router} />
                  ))}
                </div>
                {/* Offline Column */}
                <div className="w-80 flex-shrink-0 flex flex-col gap-4 bg-surface-900/30 p-4 rounded-2xl border border-white/5">
                  <div className="flex items-center gap-2 mb-2 pb-2 border-b border-white/5">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-500"></span>
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">Offline</h3>
                    <span className="ml-auto bg-surface-800 text-gray-400 font-mono text-xs px-2.5 py-0.5 rounded-full border border-white/5">{displayVms.filter(v => v.is_reachable === false).length}</span>
                  </div>
                  {displayVms.filter(v => v.is_reachable === false).map(vm => (
                    <KanbanCard key={vm.id} vm={vm} router={router} />
                  ))}
                </div>
                {/* Unknown Column */}
                <div className="w-80 flex-shrink-0 flex flex-col gap-4 bg-surface-900/30 p-4 rounded-2xl border border-white/5">
                  <div className="flex items-center gap-2 mb-2 pb-2 border-b border-white/5">
                    <span className="w-2.5 h-2.5 rounded-full bg-gray-500"></span>
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">Unknown</h3>
                    <span className="ml-auto bg-surface-800 text-gray-400 font-mono text-xs px-2.5 py-0.5 rounded-full border border-white/5">{displayVms.filter(v => v.is_reachable !== true && v.is_reachable !== false).length}</span>
                  </div>
                  {displayVms.filter(v => v.is_reachable !== true && v.is_reachable !== false).map(vm => (
                    <KanbanCard key={vm.id} vm={vm} router={router} />
                  ))}
                </div>
              </div>
            )}

            {viewMode === "minimal" && (
              <div className="flex flex-col gap-2">
                {displayVms.map((vm) => (
                  <div key={vm.id} className="flex items-center justify-between p-3 px-4 glass-panel rounded-xl hover:bg-white/5 transition-colors border border-transparent hover:border-white/10 group">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-3">
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${vm.is_reachable === true ? "bg-brand-500 animate-pulse shadow-[0_0_8px_rgba(20,184,166,0.8)]" : vm.is_reachable === false ? "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]" : "bg-gray-500"}`}></span>
                        <Link href={`/vms/${vm.id}`} className="text-sm font-bold text-white w-64 truncate group-hover:text-brand-300 transition-colors">
                          {vm.hostname}
                        </Link>
                      </div>
                      <span className="font-mono text-xs text-gray-500 hidden sm:inline-block w-40">{vm.ip_address}</span>
                    </div>
                    <div className="flex items-center gap-3 opacity-50 group-hover:opacity-100 transition-opacity">
                      <button onClick={(e) => { e.stopPropagation(); router.push(`/vms/${vm.id}/terminal`); }} className="px-3 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-white/5 flex items-center gap-1" title="Quick Connect (SSH)">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                      </button>
                      <button onClick={(e) => { e.stopPropagation(); router.push(`/vms/${vm.id}/edit`); }} className="px-3 py-1 bg-surface-800 hover:bg-surface-700 text-gray-300 hover:text-white rounded-lg transition-colors text-[10px] font-bold uppercase tracking-wider border border-white/5 flex items-center gap-1">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                        Edit
                      </button>
                      <button className="text-[10px] font-bold uppercase tracking-wider text-brand-400 hover:text-brand-300">View Metrics</button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {viewMode === "analytics" && (() => {
              const onlineVms = displayVms.filter(v => v.is_reachable === true);
              const offlineVms = displayVms.filter(v => v.is_reachable === false);
              const vmsWithCpu = displayVms.filter(v => v.latest_cpu != null);
              const vmsWithRam = displayVms.filter(v => v.latest_ram_used != null && v.latest_ram_total != null && v.latest_ram_total > 0);
              const vmsWithDisk = displayVms.filter(v => v.latest_disk_percent != null);
              const vmsWithPing = displayVms.filter(v => v.latest_response_time_ms != null);
              const avgCpu = vmsWithCpu.length > 0 ? Math.round(vmsWithCpu.reduce((a, v) => a + (v.latest_cpu || 0), 0) / vmsWithCpu.length) : null;
              const avgRam = vmsWithRam.length > 0 ? Math.round(vmsWithRam.reduce((a, v) => a + ((v.latest_ram_used || 0) / (v.latest_ram_total || 1)) * 100, 0) / vmsWithRam.length) : null;
              const avgDisk = vmsWithDisk.length > 0 ? Math.round(vmsWithDisk.reduce((a, v) => a + (v.latest_disk_percent || 0), 0) / vmsWithDisk.length) : null;
              const avgPing = vmsWithPing.length > 0 ? Math.round(vmsWithPing.reduce((a, v) => a + (v.latest_response_time_ms || 0), 0) / vmsWithPing.length * 10) / 10 : null;
              const totalRamMB = displayVms.reduce((a, v) => a + (v.latest_ram_total || 0), 0);
              const usedRamMB = displayVms.reduce((a, v) => a + (v.latest_ram_used || 0), 0);
              const totalDiskGB = displayVms.reduce((a, v) => a + (v.latest_disk_total_gb || 0), 0);
              const usedDiskGB = displayVms.reduce((a, v) => a + (v.latest_disk_used_gb || 0), 0);
              const dnsIssues = displayVms.filter(v => v.dns_mismatch === true);
              const uniqueTags = new Map<string, number>();
              displayVms.forEach(v => v.tags?.forEach(t => uniqueTags.set(t, (uniqueTags.get(t) || 0) + 1)));
              const getBarColor = (pct: number) => pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-amber-500" : pct >= 50 ? "bg-blue-500" : "bg-emerald-500";

              return (
              <div className="space-y-6">
                {/* Row 1: 6 summary cards */}
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                  <div className="glass-card p-5 border-t-2 border-brand-500">
                    <p className="text-gray-400 text-[10px] font-bold uppercase tracking-wider mb-1">Total VMs</p>
                    <p className="text-4xl font-black text-white">{displayVms.length}</p>
                  </div>
                  <div className="glass-card p-5 border-t-2 border-emerald-500">
                    <p className="text-gray-400 text-[10px] font-bold uppercase tracking-wider mb-1">Online</p>
                    <p className="text-4xl font-black text-emerald-400">{onlineVms.length}<span className="text-lg text-gray-500 ml-1">/ {displayVms.length}</span></p>
                  </div>
                  <div className="glass-card p-5 border-t-2 border-blue-500">
                    <p className="text-gray-400 text-[10px] font-bold uppercase tracking-wider mb-1">Avg CPU</p>
                    <p className="text-4xl font-black text-white font-mono">{avgCpu != null ? `${avgCpu}%` : "N/A"}</p>
                  </div>
                  <div className="glass-card p-5 border-t-2 border-violet-500">
                    <p className="text-gray-400 text-[10px] font-bold uppercase tracking-wider mb-1">Avg Memory</p>
                    <p className="text-4xl font-black text-white font-mono">{avgRam != null ? `${avgRam}%` : "N/A"}</p>
                  </div>
                  <div className="glass-card p-5 border-t-2 border-amber-500">
                    <p className="text-gray-400 text-[10px] font-bold uppercase tracking-wider mb-1">Avg Disk</p>
                    <p className="text-4xl font-black text-white font-mono">{avgDisk != null ? `${avgDisk}%` : "N/A"}</p>
                  </div>
                  <div className="glass-card p-5 border-t-2 border-cyan-500">
                    <p className="text-gray-400 text-[10px] font-bold uppercase tracking-wider mb-1">Avg Latency</p>
                    <p className="text-4xl font-black text-white font-mono">{avgPing != null ? `${avgPing}` : "N/A"}<span className="text-sm text-gray-500 ml-1">ms</span></p>
                  </div>
                </div>

                {/* Row 2: Fleet resource totals */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="glass-card p-5 border border-white/5">
                    <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-3">Fleet RAM Pool</h3>
                    <div className="flex items-baseline gap-2 mb-2">
                      <span className="text-2xl font-black text-white font-mono">{totalRamMB >= 1024 ? `${(usedRamMB / 1024).toFixed(1)}` : usedRamMB}</span>
                      <span className="text-sm text-gray-500">/ {totalRamMB >= 1024 ? `${(totalRamMB / 1024).toFixed(1)} GB` : `${totalRamMB} MB`} used</span>
                    </div>
                    <div className="w-full bg-surface-800 rounded-full h-2 overflow-hidden">
                      <div className={`h-full rounded-full transition-all ${getBarColor(totalRamMB > 0 ? (usedRamMB / totalRamMB) * 100 : 0)}`} style={{ width: `${totalRamMB > 0 ? Math.min((usedRamMB / totalRamMB) * 100, 100) : 0}%` }} />
                    </div>
                  </div>
                  <div className="glass-card p-5 border border-white/5">
                    <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-3">Fleet Disk Pool</h3>
                    <div className="flex items-baseline gap-2 mb-2">
                      <span className="text-2xl font-black text-white font-mono">{usedDiskGB.toFixed(1)}</span>
                      <span className="text-sm text-gray-500">/ {totalDiskGB.toFixed(1)} GB used</span>
                    </div>
                    <div className="w-full bg-surface-800 rounded-full h-2 overflow-hidden">
                      <div className={`h-full rounded-full transition-all ${getBarColor(totalDiskGB > 0 ? (usedDiskGB / totalDiskGB) * 100 : 0)}`} style={{ width: `${totalDiskGB > 0 ? Math.min((usedDiskGB / totalDiskGB) * 100, 100) : 0}%` }} />
                    </div>
                  </div>
                </div>

                {/* Row 3: Top consumers (CPU, Memory, Disk) */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {[
                    { title: "Top CPU Consumers", color: "brand", icon: "M13 10V3L4 14h7v7l9-11h-7z", getVal: (v: VM) => v.latest_cpu || 0, fmt: (v: VM) => formatMetric(v.latest_cpu, "%") },
                    { title: "Top Memory Consumers", color: "blue", icon: "M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4", getVal: (v: VM) => v.latest_ram_total && v.latest_ram_total > 0 ? ((v.latest_ram_used || 0) / v.latest_ram_total) * 100 : 0, fmt: (v: VM) => v.latest_ram_total && v.latest_ram_total > 0 ? `${Math.round(((v.latest_ram_used || 0) / v.latest_ram_total) * 100)}%` : "N/A" },
                    { title: "Top Disk Consumers", color: "amber", icon: "M4 7v10c0 2 3.6 4 8 4s8-2 8-4V7M4 7c0 2 3.6 4 8 4s8-2 8-4M4 7c0-2 3.6-4 8-4s8 2 8 4", getVal: (v: VM) => v.latest_disk_percent || 0, fmt: (v: VM) => formatMetric(v.latest_disk_percent, "%") },
                  ].map(panel => (
                    <div key={panel.title} className="glass-card p-5 border border-white/5">
                      <h3 className="text-[10px] font-bold text-white mb-5 uppercase tracking-wider flex items-center gap-2">
                        <svg className={`w-3.5 h-3.5 text-${panel.color}-400`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={panel.icon} /></svg>
                        {panel.title}
                      </h3>
                      <div className="space-y-3">
                        {[...displayVms].sort((a, b) => panel.getVal(b) - panel.getVal(a)).slice(0, 5).map(vm => (
                          <div key={vm.id} className="group">
                            <div className="flex justify-between items-center mb-1">
                              <span className="text-xs text-gray-300 font-semibold truncate w-32 group-hover:text-white transition-colors">{vm.hostname}</span>
                              <span className={`text-[11px] font-mono font-bold text-${panel.color}-400`}>{panel.fmt(vm)}</span>
                            </div>
                            <div className="w-full bg-surface-800 rounded-full h-1 overflow-hidden">
                              <div className={`h-full bg-${panel.color}-500 rounded-full`} style={{ width: `${Math.min(panel.getVal(vm), 100)}%` }} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Row 4: Latency ranking + DNS Health + Tag Distribution */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="glass-card p-5 border border-white/5">
                    <h3 className="text-[10px] font-bold text-white mb-5 uppercase tracking-wider flex items-center gap-2">
                      <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      Ping Latency Ranking
                    </h3>
                    <div className="space-y-2.5">
                      {[...displayVms].filter(v => v.latest_response_time_ms != null).sort((a, b) => (a.latest_response_time_ms || 0) - (b.latest_response_time_ms || 0)).slice(0, 5).map((vm, i) => (
                        <div key={vm.id} className="flex items-center gap-3">
                          <span className={`text-[10px] font-bold w-5 h-5 flex items-center justify-center rounded-full ${i === 0 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-surface-700 text-gray-400'}`}>{i + 1}</span>
                          <span className="text-xs text-gray-300 truncate flex-1">{vm.hostname}</span>
                          <span className="text-[11px] font-mono font-bold text-cyan-400">{vm.latest_response_time_ms?.toFixed(1)} ms</span>
                        </div>
                      ))}
                      {vmsWithPing.length === 0 && <p className="text-xs text-gray-500 italic">No ping data available</p>}
                    </div>
                  </div>

                  <div className="glass-card p-5 border border-white/5">
                    <h3 className="text-[10px] font-bold text-white mb-5 uppercase tracking-wider flex items-center gap-2">
                      <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                      DNS Health
                    </h3>
                    <div className="space-y-3">
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-gray-400">Healthy</span>
                        <span className="text-sm font-bold text-emerald-400">{displayVms.filter(v => v.dns_mismatch === false).length}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-gray-400">Mismatched</span>
                        <span className={`text-sm font-bold ${dnsIssues.length > 0 ? 'text-red-400' : 'text-gray-500'}`}>{dnsIssues.length}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-gray-400">Unchecked</span>
                        <span className="text-sm font-bold text-gray-500">{displayVms.filter(v => v.dns_mismatch == null).length}</span>
                      </div>
                      {dnsIssues.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-white/5">
                          <p className="text-[10px] text-red-400 font-bold uppercase tracking-wider mb-2">Mismatched Hosts</p>
                          {dnsIssues.map(vm => (
                            <p key={vm.id} className="text-xs text-gray-300 truncate">• {vm.hostname}</p>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="glass-card p-5 border border-white/5">
                    <h3 className="text-[10px] font-bold text-white mb-5 uppercase tracking-wider flex items-center gap-2">
                      <svg className="w-3.5 h-3.5 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z" /></svg>
                      Tag Distribution
                    </h3>
                    <div className="space-y-2">
                      {Array.from(uniqueTags.entries()).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([tag, count]) => (
                        <div key={tag} className="flex items-center gap-2">
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/20 truncate max-w-[120px]">{tag}</span>
                          <div className="flex-1 bg-surface-800 rounded-full h-1 overflow-hidden">
                            <div className="h-full bg-violet-500/50 rounded-full" style={{ width: `${(count / displayVms.length) * 100}%` }} />
                          </div>
                          <span className="text-[10px] font-mono text-gray-500">{count}</span>
                        </div>
                      ))}
                      {uniqueTags.size === 0 && <p className="text-xs text-gray-500 italic">No tags assigned</p>}
                    </div>
                  </div>
                </div>

                {/* Row 5: Per-VM resource table */}
                <div className="glass-card p-5 border border-white/5 overflow-x-auto">
                  <h3 className="text-[10px] font-bold text-white mb-4 uppercase tracking-wider">Per-Instance Resource Breakdown</h3>
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-gray-500 text-[10px] uppercase tracking-wider border-b border-white/5">
                        <th className="text-left py-2 pr-4">Hostname</th>
                        <th className="text-left py-2 pr-4">IP</th>
                        <th className="text-right py-2 pr-4">CPU</th>
                        <th className="text-right py-2 pr-4">RAM</th>
                        <th className="text-right py-2 pr-4">Disk</th>
                        <th className="text-right py-2 pr-4">Ping</th>
                        <th className="text-center py-2">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...displayVms].sort((a, b) => a.hostname.localeCompare(b.hostname)).map(vm => {
                        const ramPct = vm.latest_ram_total && vm.latest_ram_total > 0 ? Math.round(((vm.latest_ram_used || 0) / vm.latest_ram_total) * 100) : null;
                        return (
                        <tr key={vm.id} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                          <td className="py-2.5 pr-4 font-semibold text-gray-200">{vm.hostname}</td>
                          <td className="py-2.5 pr-4 text-gray-400 font-mono">{vm.ip_address}</td>
                          <td className="py-2.5 pr-4 text-right font-mono"><span className={vm.latest_cpu != null && vm.latest_cpu >= 80 ? 'text-red-400 font-bold' : 'text-gray-300'}>{vm.latest_cpu != null ? `${vm.latest_cpu.toFixed(1)}%` : '—'}</span></td>
                          <td className="py-2.5 pr-4 text-right font-mono"><span className={ramPct != null && ramPct >= 80 ? 'text-red-400 font-bold' : 'text-gray-300'}>{ramPct != null ? `${ramPct}%` : '—'}</span></td>
                          <td className="py-2.5 pr-4 text-right font-mono"><span className={vm.latest_disk_percent != null && vm.latest_disk_percent >= 80 ? 'text-red-400 font-bold' : 'text-gray-300'}>{vm.latest_disk_percent != null ? `${vm.latest_disk_percent.toFixed(1)}%` : '—'}</span></td>
                          <td className="py-2.5 pr-4 text-right font-mono text-gray-300">{vm.latest_response_time_ms != null ? `${vm.latest_response_time_ms.toFixed(1)}ms` : '—'}</td>
                          <td className="py-2.5 text-center"><span className={`inline-block w-2 h-2 rounded-full ${vm.is_reachable === true ? 'bg-emerald-400' : vm.is_reachable === false ? 'bg-red-400' : 'bg-gray-500'}`} /></td>
                        </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
              );
            })()}
          </>
        )}
      </main>
    </div>
  );
}
