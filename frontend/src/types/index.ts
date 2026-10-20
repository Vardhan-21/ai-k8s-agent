/**
 * Shared TypeScript types for AI Kubernetes Agent.
 */

export interface HealthResponse {
  status: string;
  service: string;
}

export interface DiagnosisResult {
  root_cause: string;
  explanation: string;
  fix: string;
  kubectl_command: string;
  prevention_recommendation?: string;
  confidence: number;
  confidence_reasoning?: string;
}

export interface InvestigationPayload {
  pods: any;
  logs: any;
  events: any;
  deployments: any;
  network: any;
}

export interface InvestigationResponse {
  status: string;
  context?: string;
  investigation: InvestigationPayload;
  diagnosis: DiagnosisResult;
}

export interface ClusterContextInfo {
  name: string;
  cluster: string;
  user: string;
  is_current: boolean;
  server: string;
  status: "reachable" | "unreachable" | "unknown";
  error?: string | null;
}

export interface ContextsListResponse {
  contexts: ClusterContextInfo[];
  current_context: string | null;
  total: number;
}

export interface InvestigationHistoryItem {
  id: string;
  user_id: string;
  created_at: string;
  cluster_context?: string;
  root_cause: string;
  explanation?: string;
  fix?: string;
  kubectl_command?: string;
  namespace?: string;
  confidence: number;
  status: string;
}

export interface ProgressStage {
  id: string;
  label: string;
}
