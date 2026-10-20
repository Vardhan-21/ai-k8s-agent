"use client";

import { useEffect, useState } from "react";
import { AuthCard } from "@/components/AuthCard";
import { ClusterSelector } from "@/components/ClusterSelector";
import { DiagnosisCard } from "@/components/DiagnosisCard";
import { HistoryTable } from "@/components/HistoryTable";
import { ProgressStepper } from "@/components/ProgressStepper";
import { useAuth } from "@/hooks/useAuth";
import { getKubernetesContexts, runInvestigation } from "@/services/api";
import { insforge } from "@/services/insforge";
import {
  ClusterContextInfo,
  DiagnosisResult,
  InvestigationHistoryItem,
} from "@/types";

export default function Home() {
  const {
    user,
    token,
    loading: authLoading,
    pendingVerificationEmail,
    signIn,
    signUp,
    verifyEmail,
    resendVerificationEmail,
    sendLoginOtp,
    clearPendingVerification,
    signOut,
  } = useAuth();

  const [status, setStatus] = useState<"ready" | "investigating" | "error">("ready");
  const [completedStages, setCompletedStages] = useState<string[]>([]);
  const [activeStage, setActiveStage] = useState<string | undefined>(undefined);
  const [diagnosis, setDiagnosis] = useState<DiagnosisResult | null>(null);
  const [historyItems, setHistoryItems] = useState<InvestigationHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Cluster context selection state
  const [contexts, setContexts] = useState<ClusterContextInfo[]>([]);
  const [selectedContext, setSelectedContext] = useState<string | null>(null);
  const [contextsLoading, setContextsLoading] = useState(false);
  const [investigatedContext, setInvestigatedContext] = useState<string | null>(null);

  // Load history and contexts whenever user / token becomes available
  useEffect(() => {
    if (user && token) {
      loadHistory();
      loadContexts();
    }
  }, [user, token]);

  const loadContexts = async () => {
    setContextsLoading(true);
    try {
      const resp = await getKubernetesContexts(token || undefined, true);
      setContexts(resp.contexts);
      // Auto-select current default context, or fallback to first reachable
      if (!selectedContext) {
        if (resp.current_context) {
          setSelectedContext(resp.current_context);
        } else if (resp.contexts.length > 0) {
          const firstReachable = resp.contexts.find((c) => c.status === "reachable");
          setSelectedContext(firstReachable ? firstReachable.name : resp.contexts[0].name);
        }
      }
    } catch (err: any) {
      console.warn("Could not load Kubernetes contexts:", err);
      // Fallback empty list
    } finally {
      setContextsLoading(false);
    }
  };

  const loadHistory = async () => {
    if (!user) return;
    setHistoryLoading(true);
    try {
      // Query InsForge database
      const { data, error } = await insforge.database
        .from("investigations")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", { ascending: false })
        .limit(10);

      if (!error && data) {
        setHistoryItems(data as InvestigationHistoryItem[]);
      } else {
        // Fallback to backend history endpoint
        const API_BASE_URL =
          process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
        const res = await fetch(`${API_BASE_URL}/investigate/history?limit=10`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const fallbackData = await res.json();
          setHistoryItems(fallbackData);
        }
      }
    } catch (err) {
      console.error("Failed to load history:", err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleInvestigate = async () => {
    if (!token) return;

    setStatus("investigating");
    setErrorMessage(null);
    setCompletedStages([]);
    setActiveStage("checking_pods");
    setInvestigatedContext(selectedContext);

    const investigationId = `inv_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

    // Setup live SSE progress stream
    let eventSource: EventSource | null = null;
    try {
      eventSource = new EventSource(`${API_BASE}/investigate/progress/${investigationId}`);
      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.completed_stages) {
            setCompletedStages(payload.completed_stages);
          }
          if (payload.stage) {
            setActiveStage(payload.stage);
            setCompletedStages((prev) =>
              prev.includes(payload.stage) ? prev : [...prev, payload.stage]
            );
          }
        } catch (e) {
          // Ignore parse errors
        }
      };
    } catch (e) {
      console.warn("Could not establish SSE progress connection:", e);
    }

    try {
      const response = await runInvestigation(token, investigationId, selectedContext || undefined);
      if (response && response.diagnosis) {
        setDiagnosis(response.diagnosis);
        setCompletedStages([
          "checking_pods",
          "reading_logs",
          "analyzing_events",
          "inspecting_deployments",
          "checking_networking",
          "ai_reasoning",
          "completed",
        ]);
        setActiveStage(undefined);
        setStatus("ready");
        // Refresh history
        await loadHistory();
      } else {
        throw new Error("No diagnosis received from investigation engine");
      }
    } catch (err: any) {
      console.error("Investigation error:", err);
      setStatus("error");
      const errorDetail =
        err.response?.data?.detail ||
        err.message ||
        "Unable to connect to Kubernetes cluster. Please verify kubeconfig path, cluster access, and kubectl permissions.";
      setErrorMessage(errorDetail);
    } finally {
      if (eventSource) {
        eventSource.close();
      }
    }
  };

  const selectedCtxObj = contexts.find((c) => c.name === selectedContext);
  const isSelectedClusterUnreachable = selectedCtxObj?.status === "unreachable";

  // If unauthenticated, show Auth Card
  if (!user) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-gray-950 px-6 py-12">
        <div className="w-full max-w-md space-y-6">
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-extrabold tracking-tight text-white">
              AI Kubernetes Agent
            </h1>
            <p className="text-sm text-gray-400">
              Senior SRE Troubleshooting with InsForge Authentication
            </p>
          </div>
          <AuthCard
            onSignIn={signIn}
            onSignUp={signUp}
            onVerifyEmail={verifyEmail}
            onResendVerification={resendVerificationEmail}
            onSendLoginOtp={sendLoginOtp}
            pendingEmail={pendingVerificationEmail}
            onCancelVerification={clearPendingVerification}
          />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-950 text-white pb-16">
      {/* Top Header */}
      <header className="border-b border-gray-800 bg-gray-900/40 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600/20 border border-blue-500/30 text-blue-400">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h1 className="text-base font-bold text-white leading-tight">
                AI Kubernetes Agent
              </h1>
              <p className="text-[11px] text-gray-400">Autonomous Incident SRE</p>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <span className="hidden sm:inline text-gray-400 font-mono">
              {user.email}
            </span>
            <button
              onClick={signOut}
              className="rounded-lg border border-gray-800 bg-gray-900 px-3 py-1.5 text-xs text-gray-300 transition hover:bg-gray-800 hover:text-white"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main Dashboard Container */}
      <div className="max-w-6xl mx-auto px-6 pt-10 space-y-8">
        {/* Cluster Discovery & Selector */}
        <ClusterSelector
          contexts={contexts}
          selectedContext={selectedContext}
          onSelectContext={(name) => setSelectedContext(name)}
          isLoading={contextsLoading}
          onRefresh={loadContexts}
          disabled={status === "investigating"}
        />

        {/* Main CTA Section */}
        <div className="rounded-2xl border border-gray-800 bg-gradient-to-b from-gray-900/60 to-gray-950 p-8 text-center space-y-6">
          <div className="max-w-xl mx-auto space-y-2">
            <h2 className="text-3xl font-extrabold tracking-tight text-white">
              Investigate Kubernetes Incident
            </h2>
            <p className="text-sm text-gray-400">
              Collect pods, container logs, warning events, deployments, and network routing evidence.
              Then correlate root causes with AI SRE reasoning.
            </p>
            {selectedContext && (
              <p className="text-xs text-indigo-300 font-mono pt-1">
                Active target: <span className="font-semibold">{selectedContext}</span>
              </p>
            )}
          </div>

          <div className="flex flex-col items-center justify-center gap-4">
            <button
              onClick={handleInvestigate}
              disabled={status === "investigating" || isSelectedClusterUnreachable || !selectedContext}
              className="inline-flex items-center gap-2.5 rounded-xl bg-blue-600 px-8 py-3.5 text-sm font-semibold text-white shadow-xl shadow-blue-600/20 transition-all hover:bg-blue-500 hover:shadow-blue-500/30 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {status === "investigating" ? (
                <>
                  <div className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                  <span>Investigating Kubernetes Cluster...</span>
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <span>Investigate Cluster</span>
                </>
              )}
            </button>

            {isSelectedClusterUnreachable && (
              <p className="text-xs text-rose-400">
                Cannot start investigation: selected cluster is currently unreachable.
              </p>
            )}

            {/* Status indicator */}
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <span className="relative flex h-2 w-2">
                <span
                  className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${
                    status === "investigating"
                      ? "animate-ping bg-blue-400"
                      : status === "error"
                      ? "bg-red-400"
                      : "bg-green-400"
                  }`}
                />
                <span
                  className={`relative inline-flex h-2 w-2 rounded-full ${
                    status === "investigating"
                      ? "bg-blue-500"
                      : status === "error"
                      ? "bg-red-500"
                      : "bg-green-500"
                  }`}
                />
              </span>
              System Status:{" "}
              <span
                className={`font-medium capitalize ${
                  status === "investigating"
                    ? "text-blue-400"
                    : status === "error"
                    ? "text-red-400"
                    : "text-green-400"
                }`}
              >
                {status}
              </span>
            </div>
          </div>
        </div>

        {/* Error Notification Banner */}
        {errorMessage && (
          <div className="rounded-xl border border-red-500/30 bg-red-950/40 p-4 text-sm text-red-300 flex items-center justify-between">
            <div className="space-y-1">
              <p className="font-semibold">Investigation Error</p>
              <p className="text-xs text-red-400">{errorMessage}</p>
            </div>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-xs text-red-400 underline hover:text-red-300 flex-shrink-0 ml-4"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Realtime Investigation Progress */}
        {(status === "investigating" || completedStages.length > 0) && (
          <div className="space-y-2">
            {investigatedContext && (
              <p className="text-xs text-slate-400">
                Investigating cluster context: <span className="font-mono text-indigo-300">{investigatedContext}</span>
              </p>
            )}
            <ProgressStepper
              completedStages={completedStages}
              activeStage={activeStage}
              isComplete={completedStages.includes("completed")}
            />
          </div>
        )}

        {/* Diagnosis Result Card */}
        {diagnosis && (
          <div>
            <DiagnosisCard diagnosis={diagnosis} />
          </div>
        )}

        {/* Recent Investigations History */}
        <HistoryTable
          items={historyItems}
          loading={historyLoading}
          onSelect={(item) => {
            setDiagnosis({
              root_cause: item.root_cause,
              explanation: item.explanation || "",
              fix: item.fix || "",
              kubectl_command: item.kubectl_command || "",
              confidence: item.confidence,
            });
            window.scrollTo({ top: 300, behavior: "smooth" });
          }}
        />
      </div>
    </main>
  );
}
