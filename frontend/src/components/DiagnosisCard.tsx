"use client";

import { useState } from "react";
import { DiagnosisResult } from "@/types";

interface DiagnosisCardProps {
  diagnosis: DiagnosisResult;
}

export function DiagnosisCard({ diagnosis }: DiagnosisCardProps) {
  const [copied, setCopied] = useState(false);

  const copyCommand = () => {
    if (diagnosis.kubectl_command) {
      navigator.clipboard.writeText(diagnosis.kubectl_command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const getConfidenceBadgeColor = (confidence: number) => {
    if (confidence >= 85) return "border-green-500/30 bg-green-500/10 text-green-400";
    if (confidence >= 60) return "border-yellow-500/30 bg-yellow-500/10 text-yellow-400";
    return "border-red-500/30 bg-red-500/10 text-red-400";
  };

  return (
    <div className="w-full rounded-2xl border border-gray-800 bg-gray-900/90 p-8 shadow-2xl backdrop-blur-xl space-y-6">
      {/* Header with Title & Confidence */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-gray-800 pb-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-blue-400">
            SRE Incident Diagnosis
          </span>
          <h2 className="text-2xl font-bold text-white mt-0.5">
            {diagnosis.root_cause}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${getConfidenceBadgeColor(
              diagnosis.confidence
            )}`}
          >
            <span className="h-2 w-2 rounded-full bg-current" />
            Confidence: {diagnosis.confidence}%
          </span>
        </div>
      </div>

      {/* Explanation */}
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">
          Explanation
        </h4>
        <p className="text-sm leading-relaxed text-gray-300">
          {diagnosis.explanation}
        </p>
      </div>

      {/* Suggested Fix */}
      <div className="rounded-xl border border-blue-500/20 bg-blue-950/20 p-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-blue-400 mb-1">
          Suggested Fix
        </h4>
        <p className="text-sm text-gray-200">{diagnosis.fix}</p>
      </div>

      {/* kubectl Command */}
      {diagnosis.kubectl_command && (
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              Remediation Command
            </h4>
            <button
              onClick={copyCommand}
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 transition"
            >
              {copied ? (
                <>
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Copied!
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  Copy Command
                </>
              )}
            </button>
          </div>
          <div className="relative rounded-xl border border-gray-800 bg-gray-950 p-4 font-mono text-xs text-green-400 overflow-x-auto">
            <code>{diagnosis.kubectl_command}</code>
          </div>
        </div>
      )}

      {/* Prevention Recommendation */}
      {diagnosis.prevention_recommendation && (
        <div className="border-t border-gray-800/80 pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">
            Prevention Recommendation
          </h4>
          <p className="text-xs text-gray-400 leading-relaxed">
            {diagnosis.prevention_recommendation}
          </p>
        </div>
      )}

      {/* Confidence Reasoning */}
      {diagnosis.confidence_reasoning && (
        <div className="text-[11px] text-gray-500 italic">
          Scoring Rationale: {diagnosis.confidence_reasoning}
        </div>
      )}
    </div>
  );
}
