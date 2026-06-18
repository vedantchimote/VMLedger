"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Server } from "lucide-react";
import dynamic from "next/dynamic";
import { api } from "@/lib/api-client";
import type { VM } from "@/types/api";

const WebTerminal = dynamic(() => import("@/components/WebTerminal"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-[#0d1117] rounded-lg border border-gray-800">
      <div className="flex flex-col items-center space-y-3">
        <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-gray-500 text-sm font-mono">Loading xterm.js engine...</p>
      </div>
    </div>
  ),
});

export default function TerminalPage() {
  const params = useParams();
  const router = useRouter();
  const vmId = parseInt(params.id as string, 10);

  const [vm, setVm] = useState<VM | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadVm() {
      try {
        const response = await api.vms.get(vmId);
        setVm(response);
      } catch (error) {
        console.error("Failed to load VM:", error);
      } finally {
        setLoading(false);
      }
    }

    if (vmId) {
      loadVm();
    }
  }, [vmId]);

  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-black">
        <div className="flex flex-col items-center space-y-4">
          <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-gray-400 font-medium">Initializing secure terminal...</p>
        </div>
      </div>
    );
  }

  if (!vm) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-black">
        <div className="text-center p-8 border border-red-900/30 bg-red-900/10 rounded-lg max-w-md">
          <Server className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-white mb-2">VM Not Found</h2>
          <p className="text-gray-400 mb-6">
            The virtual machine you are trying to connect to could not be found or you don't have access.
          </p>
          <button
            onClick={() => router.push("/dashboard")}
            className="px-4 py-2 bg-gray-800 text-white rounded hover:bg-gray-700 transition-colors"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen w-full bg-black text-gray-200 overflow-hidden">
      {/* Top Navigation Bar */}
      <div className="flex items-center justify-between px-6 py-3 bg-[#0d1117] border-b border-gray-800 shadow-sm z-10">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => window.close()}
            className="p-2 -ml-2 rounded-md text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
            title="Close Terminal Tab"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center space-x-3 border-l border-gray-700 pl-4">
            <div className={`w-3 h-3 rounded-full ${vm.is_reachable ? 'bg-green-500' : 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]'}`}></div>
            <div>
              <h1 className="text-sm font-bold text-white tracking-wide">
                {vm.hostname}
              </h1>
              <p className="text-xs text-gray-500 font-mono mt-0.5">
                {vm.ip_address}:{vm.ssh_port}
              </p>
            </div>
          </div>
        </div>
        
        <div className="flex items-center space-x-4">
          <div className="text-xs text-gray-500 bg-gray-900 px-3 py-1.5 rounded-md border border-gray-800 hidden sm:block">
            <span className="font-mono text-indigo-400">Ctrl+C</span> to interrupt process
          </div>
          <button
            onClick={() => window.close()}
            className="px-4 py-1.5 text-sm font-medium bg-red-500/10 text-red-400 border border-red-500/20 rounded-md hover:bg-red-500/20 transition-colors"
            title="Disconnect SSH Session and Close Tab"
          >
            Disconnect
          </button>
        </div>
      </div>

      {/* Terminal Area */}
      <div className="flex-1 p-4 sm:p-6 lg:p-8 bg-black">
        <div className="h-full w-full max-w-7xl mx-auto">
          <WebTerminal vmId={vmId} />
        </div>
      </div>
    </div>
  );
}
