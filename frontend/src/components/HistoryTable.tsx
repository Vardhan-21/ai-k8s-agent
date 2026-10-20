"use client";

import { InvestigationHistoryItem } from "@/types";

interface HistoryTableProps {
  items: InvestigationHistoryItem[];
  onSelect?: (item: InvestigationHistoryItem) => void;
  loading?: boolean;
}

export function HistoryTable({ items, onSelect, loading }: HistoryTableProps) {
  if (loading) {
    return (
      <div className="w-full rounded-2xl border border-gray-800 bg-gray-900/40 p-6 text-center text-sm text-gray-500">
        Loading investigation history...
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <div className="w-full rounded-2xl border border-gray-800 bg-gray-900/40 p-8 text-center text-sm text-gray-500">
        No previous investigations found. Run your first cluster investigation above!
      </div>
    );
  }

  return (
    <div className="w-full rounded-2xl border border-gray-800 bg-gray-900/60 overflow-hidden backdrop-blur-xl">
      <div className="px-6 py-4 border-b border-gray-800">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
          Previous Investigations
        </h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-gray-800 bg-gray-950/40 text-gray-400 uppercase tracking-wider">
            <tr>
              <th className="px-6 py-3">Timestamp</th>
              <th className="px-6 py-3">Cluster</th>
              <th className="px-6 py-3">Root Cause</th>
              <th className="px-6 py-3">Namespace</th>
              <th className="px-6 py-3">Confidence</th>
              <th className="px-6 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60 text-gray-300">
            {items.map((item) => (
              <tr
                key={item.id}
                onClick={() => onSelect && onSelect(item)}
                className={`transition ${
                  onSelect ? "cursor-pointer hover:bg-gray-800/40" : ""
                }`}
              >
                <td className="px-6 py-3.5 whitespace-nowrap text-gray-400">
                  {item.created_at
                    ? new Date(item.created_at).toLocaleString()
                    : "Recent"}
                </td>
                <td className="px-6 py-3.5 whitespace-nowrap">
                  <span className="font-mono text-[11px] bg-slate-800/80 text-indigo-300 px-2 py-0.5 rounded border border-slate-700/60 max-w-[140px] truncate inline-block">
                    {item.cluster_context || "default"}
                  </span>
                </td>
                <td className="px-6 py-3.5 font-medium text-white max-w-xs truncate">
                  {item.root_cause}
                </td>
                <td className="px-6 py-3.5 text-gray-400">{item.namespace || "all"}</td>
                <td className="px-6 py-3.5">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                      item.confidence >= 80
                        ? "bg-green-500/10 text-green-400"
                        : item.confidence >= 60
                        ? "bg-yellow-500/10 text-yellow-400"
                        : "bg-red-500/10 text-red-400"
                    }`}
                  >
                    {item.confidence}%
                  </span>
                </td>
                <td className="px-6 py-3.5">
                  <span className="inline-flex items-center gap-1.5 text-gray-300 capitalize">
                    <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
                    {item.status || "completed"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
