import type {
  GraphResponse,
  JobStatistics,
  PipelineJob,
  ProfileResponse,
  ValidationFinding,
} from "./types";

// All requests go through this base prefix. In local development Vite proxies
// "/api" to the backend (see vite.config.ts), so no CORS setup is needed.
// Override with VITE_API_BASE if the backend is served elsewhere.
export const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, params: Record<string, string>): Promise<T> {
  const qs = new URLSearchParams(params).toString();
  const url = `${API_BASE}${path}${qs ? `?${qs}` : ""}`;

  const res = await fetch(url);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // response had no JSON body; keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  listPipelines: (file: string) =>
    request<PipelineJob[]>("/pipelines/", { file }),

  getGraph: (file: string) =>
    request<GraphResponse>("/graph/", { file }),

  getFindings: (file: string, dataDir?: string) =>
    request<ValidationFinding[]>(
      "/findings/",
      dataDir === undefined ? { file } : { file, data_dir: dataDir },
    ),

  getStatistics: (file: string, dataDir = ".") =>
    request<JobStatistics[]>("/statistics/", { file, data_dir: dataDir }),

  profileTable: (table: string, dataDir = ".") =>
    request<ProfileResponse>("/profile/", { table, data_dir: dataDir }),

  listConfigs: () =>
    request<{ files: string[]; manifests: string[] }>("/configs/", {}),

  listTables: (dataDir = ".") =>
    request<{ tables: string[] }>("/tables/", { data_dir: dataDir }),
};
