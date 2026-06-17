"use client";

import { useState, useRef, useEffect } from "react";
import { format } from "date-fns";
import { Bell, CheckCircle2, AlertTriangle, XCircle, Clock } from "lucide-react";
import { useGlobalAlertHistory } from "@/lib/hooks/use-alerts";

export default function GlobalNotificationBell() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  
  const { data: alerts, isLoading, error } = useGlobalAlertHistory();

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Filter alerts for the last 7 days to keep it relevant
  const recentAlerts = alerts?.filter(a => {
    const sentDate = new Date(a.sent_at || Date.now());
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    return sentDate >= sevenDaysAgo;
  }) || [];

  const unreadCount = Math.min(recentAlerts.length, 9); // Simple indicator

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-400 hover:text-white transition-colors rounded-full hover:bg-white/5 focus:outline-none"
        aria-label="Notifications"
      >
        <Bell className="w-5 h-5" />
        {recentAlerts.length > 0 && (
          <span className="absolute top-1 right-1 flex items-center justify-center w-4 h-4 text-[9px] font-bold text-white bg-red-500 rounded-full border border-surface-950">
            {unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-surface-900 border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden backdrop-blur-xl">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-surface-800/50">
            <h3 className="text-sm font-bold text-white">Notifications</h3>
            <span className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold">Last 7 days</span>
          </div>
          
          <div className="max-h-[400px] overflow-y-auto hide-scrollbar">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <svg className="animate-spin h-5 w-5 text-brand-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
            ) : error ? (
              <div className="py-8 text-center px-4">
                <p className="text-xs text-red-400">Failed to load notifications.</p>
              </div>
            ) : recentAlerts.length === 0 ? (
              <div className="py-12 text-center flex flex-col items-center">
                <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mb-3">
                  <CheckCircle2 className="w-6 h-6 text-gray-500" />
                </div>
                <p className="text-sm text-gray-400 font-medium">All caught up</p>
                <p className="text-xs text-gray-500 mt-1">No recent alerts in your fleet.</p>
              </div>
            ) : (
              <div className="divide-y divide-white/5">
                {recentAlerts.map((alert) => (
                  <div key={alert.id} className="p-4 hover:bg-white/5 transition-colors cursor-pointer group">
                    <div className="flex gap-3">
                      <div className="flex-shrink-0 mt-0.5">
                        {alert.alert_type === 'VM_RECOVERED' ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        ) : alert.alert_type === 'VM_UNREACHABLE' ? (
                          <XCircle className="w-4 h-4 text-red-400" />
                        ) : (
                          <AlertTriangle className="w-4 h-4 text-amber-400" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-gray-200 truncate group-hover:text-white transition-colors">
                          {alert.hostname || `VM #${alert.vm_id}`}
                        </p>
                        <p className="text-xs text-gray-400 mt-0.5">
                          {alert.alert_type.replace(/_/g, " ")}
                        </p>
                        <div className="flex items-center gap-2 mt-2">
                          <span className="flex items-center text-[10px] text-gray-500 font-mono">
                            <Clock className="w-3 h-3 mr-1" />
                            {alert.sent_at ? format(new Date(alert.sent_at), "MMM d, HH:mm") : "Unknown"}
                          </span>
                          {!alert.success && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-bold">
                              Failed to send
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          
          <div className="p-3 border-t border-white/10 bg-surface-800/80">
            <button 
              onClick={() => setIsOpen(false)}
              className="w-full text-center text-xs font-semibold text-gray-400 hover:text-white transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
