"use client";

export interface ProgressStepperProps {
  completedStages: string[];
  activeStage?: string;
  isComplete: boolean;
}

const STAGES = [
  { id: "checking_pods", label: "Checking Pods" },
  { id: "reading_logs", label: "Reading Logs" },
  { id: "analyzing_events", label: "Analyzing Events" },
  { id: "inspecting_deployments", label: "Inspecting Deployments" },
  { id: "checking_networking", label: "Checking Networking" },
  { id: "ai_reasoning", label: "AI Reasoning" },
  { id: "completed", label: "Root Cause Found" },
];

export function ProgressStepper({
  completedStages,
  activeStage,
  isComplete,
}: ProgressStepperProps) {
  return (
    <div className="w-full rounded-2xl border border-gray-800 bg-gray-900/60 p-6 backdrop-blur-xl">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-400">
        Investigation Status
      </h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-7">
        {STAGES.map((stage) => {
          const isDone = completedStages.includes(stage.id) || isComplete;
          const isCurrent = activeStage === stage.id && !isDone;

          return (
            <div
              key={stage.id}
              className={`flex items-center gap-3 rounded-xl border p-3 transition-all ${
                isDone
                  ? "border-green-500/30 bg-green-950/20 text-green-400"
                  : isCurrent
                  ? "border-blue-500/40 bg-blue-950/30 text-blue-400 animate-pulse"
                  : "border-gray-800/80 bg-gray-950/40 text-gray-500"
              }`}
            >
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gray-900">
                {isDone ? (
                  <svg className="h-4 w-4 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                ) : isCurrent ? (
                  <div className="h-2 w-2 rounded-full bg-blue-400 animate-ping" />
                ) : (
                  <div className="h-1.5 w-1.5 rounded-full bg-gray-700" />
                )}
              </div>
              <span className="text-xs font-medium">{stage.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
