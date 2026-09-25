import { endpoints } from "./endpoints";
import type { AnalysisResult, ApiErrorBody, ModelInfo } from "@/types";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly requestId: string | null,
    public readonly analysisId: string | null,
  ) {
    super(code);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<{ body: T; requestId: string | null }> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  if (!baseUrl) throw new ApiError(0, "API_NOT_CONFIGURED", null, null);
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, { ...options, cache: "no-store" });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", null, null);
  }
  if (!response.ok) {
    // The server's message may contain request data. Only trusted status/code are used in UI.
    const body = await response.json().catch(() => ({})) as ApiErrorBody;
    throw new ApiError(
      response.status,
      body.error?.code ?? "UNKNOWN_ERROR",
      response.headers.get("X-Request-Id") ?? body.error?.requestId ?? null,
      body.analysisId ?? null,
    );
  }
  return { body: await response.json() as T, requestId: response.headers.get("X-Request-Id") };
}

export async function fetchModels(): Promise<ModelInfo[]> {
  const response = await request<{ models: ModelInfo[] }>(endpoints.models);
  return response.body.models;
}

export async function createAnalysis(text: string, modelId: string, includeExplanation = false): Promise<{ result: AnalysisResult; requestId: string | null }> {
  return await request<AnalysisResult>(endpoints.analyses, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, modelId, ...(includeExplanation ? { includeExplanation: true } : {}) }),
  }).then(({ body, requestId }) => ({ result: body, requestId }));
}
