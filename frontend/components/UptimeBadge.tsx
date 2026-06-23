import React from 'react';

interface UptimeBadgeProps {
  uptimePercent: number;
  slaTier: string;
}

export function UptimeBadge({ uptimePercent, slaTier }: UptimeBadgeProps) {
  let colorClass = "bg-red-500/10 text-red-400 border-red-500/20";
  let dotClass = "bg-red-500";
  
  if (uptimePercent >= 99.99) {
    colorClass = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    dotClass = "bg-emerald-500";
  } else if (uptimePercent >= 99.95) {
    colorClass = "bg-green-500/10 text-green-400 border-green-500/20";
    dotClass = "bg-green-500";
  } else if (uptimePercent >= 99.9) {
    colorClass = "bg-blue-500/10 text-blue-400 border-blue-500/20";
    dotClass = "bg-blue-500";
  } else if (uptimePercent >= 99.5) {
    colorClass = "bg-yellow-500/10 text-yellow-400 border-yellow-500/20";
    dotClass = "bg-yellow-500";
  } else if (uptimePercent >= 99.0) {
    colorClass = "bg-orange-500/10 text-orange-400 border-orange-500/20";
    dotClass = "bg-orange-500";
  }

  return (
    <span 
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 border rounded-full text-xs font-medium ${colorClass}`}
      title={`${slaTier} SLA (${uptimePercent.toFixed(2)}% uptime last 30 days)`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`}></span>
      {uptimePercent >= 100 ? "100" : uptimePercent.toFixed(2)}%
    </span>
  );
}
