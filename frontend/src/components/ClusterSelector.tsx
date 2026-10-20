"use client";

import React from "react";
import { ClusterContextInfo } from "@/types";

interface ClusterSelectorProps {
  contexts: ClusterContextInfo[];
  selectedContext: string | null;
  onSelectContext: (contextName: string) => void;
  isLoading: boolean;
  onRefresh: () => void;
  disabled?: boolean;
}

export function ClusterSelector({
  contexts,
  selectedContext,
  onSelectContext,
  isLoading,
  onRefresh,
  disabled = false,
}: ClusterSelectorProps) {
  const currentSelected = contexts.find((c) => c.name === selectedContext);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <svg
            className="w-5 h-5 text-indigo-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
            />
          </svg>
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
            Target Kubernetes Cluster
          </h3>
        </div>
        <button
          onClick={onRefresh}
          disabled={isLoading || disabled}
          className="flex items-center space-x-1.5 text-xs text-slate-400 hover:text-indigo-400 transition-colors disabled:opacity-40"
          title="Refresh cluster contexts"
        >
          <svg
            className={`w-3.5 h-3.5 ${isLoading ? "animate-spin text-indigo-400" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          <span>{isLoading ? "Refreshing..." : "Refresh"}</span>
        </button>
      </div>

      {contexts.length === 0 ? (
        <div className="py-4 text-center text-xs text-slate-500 bg-slate-950/60 rounded-lg border border-slate-800">
          {isLoading ? (
            <span className="flex items-center justify-center space-x-2 text-slate-400">
              <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping" />
              <span>Discovering Kubernetes clusters from kubeconfig...</span>
            </span>
          ) : (
            <span>No Kubernetes contexts found in kubeconfig. Please verify KUBECONFIG_PATH.</span>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {contexts.map((ctx) => {
              const isSelected = ctx.name === selectedContext;
              const isReachable = ctx.status === "reachable";
              return (
                <button
                  key={ctx.name}
                  type="button"
                  disabled={disabled}
                  onClick={() => onSelectContext(ctx.name)}
                  className={`text-left p-3 rounded-lg border transition-all text-xs relative ${
                    isSelected
                      ? "bg-indigo-950/40 border-indigo-500/80 ring-1 ring-indigo-500/40"
                      : "bg-slate-950/40 border-slate-800 hover:border-slate-700"
                  } ${disabled ? "opacity-60 cursor-not-allowed" : "cursor-pointer"}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="font-mono font-medium text-slate-200 truncate pr-2 max-w-[240px]">
                      {ctx.name}
                    </div>
                    <div className="flex items-center space-x-1.5 flex-shrink-0">
                      <span
                        className={`w-2 h-2 rounded-full ${
                          isReachable
                            ? "bg-emerald-400 ring-2 ring-emerald-950"
                            : "bg-rose-400 ring-2 ring-rose-950"
                        }`}
                      />
                      <span
                        className={`text-[10px] font-semibold uppercase tracking-wider ${
                          isReachable ? "text-emerald-400" : "text-rose-400"
                        }`}
                      >
                        {ctx.status}
                      </span>
                    </div>
                  </div>

                  <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400">
                    <span className="truncate max-w-[180px] text-slate-500">
                      Cluster: {ctx.cluster}
                    </span>
                    {ctx.is_current && (
                      <span className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded">
                        default
                      </span>
                    )}
                  </div>

                  {isSelected && (
                    <div className="mt-2 pt-2 border-t border-indigo-900/40 flex items-center justify-between text-[10px] text-indigo-300">
                      <span>✓ Selected for investigation</span>
                      {ctx.server && (
                        <span className="font-mono text-slate-400 truncate max-w-[160px]">
                          {ctx.server}
                        </span>
                      )}
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {currentSelected && currentSelected.status === "unreachable" && (
            <div className="mt-3 p-2.5 rounded-lg bg-rose-950/30 border border-rose-800/40 text-xs text-rose-300 flex items-start space-x-2">
              <svg
                className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
              <div>
                <p className="font-semibold">Selected cluster is unreachable</p>
                <p className="text-[11px] text-rose-400 mt-0.5">
                  {currentSelected.error ||
                    "Please ensure the Kubernetes cluster is running and accessible."}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
