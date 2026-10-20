import axios from "axios";
import { ContextsListResponse, InvestigationResponse } from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 60000, // 60s timeout for cluster investigation
});

/** Discover available Kubernetes contexts from kubeconfig. */
export async function getKubernetesContexts(
  token?: string,
  checkReachability: boolean = true
): Promise<ContextsListResponse> {
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const { data } = await apiClient.get<ContextsListResponse>(
    `/kubernetes/contexts?check=${checkReachability}`,
    { headers }
  );
  return data;
}

/** Trigger cluster investigation with authenticated bearer token on the selected context. */
export async function runInvestigation(
  token: string,
  investigationId?: string,
  context?: string
): Promise<InvestigationResponse> {
  const url = investigationId
    ? `/investigate?investigation_id=${encodeURIComponent(investigationId)}`
    : "/investigate";

  const { data } = await apiClient.post<InvestigationResponse>(
    url,
    { context: context || undefined },
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return data;
}

/** Check backend health. */
export async function getHealth() {
  const { data } = await apiClient.get("/health");
  return data;
}
