// TypeScript mirrors of the backend Pydantic models. Keep these in sync with
// backend/app/models and backend/app/schemas.

export interface PipelineJob {
  config_key: string;
  pipeline_name: string;
  enabled: boolean;
  source_table: string;
  target_table: string;
  sql_query: string | null;
  execution_order: number | null;
  primary_key: string | null;
  load_type: string | null;
}

export type Severity = "error" | "warning" | "info";

export interface ValidationFinding {
  finding_type: string;
  severity: Severity;
  message: string;
  affected_job: string | null;
  affected_table: string | null;
  recommendation: string | null;
}

export interface EdgeDetail {
  source: string;
  target: string;
  config_key: string;
}

export interface GraphResponse {
  nodes: string[];
  edges: EdgeDetail[];
  execution_order: string[] | null;
  cycle_detected: boolean;
}

export interface JobStatistics {
  config_key: string;
  pipeline_name: string;
  source_table: string;
  target_table: string;
  source_count: number | null;
  target_count: number | null;
  lost_rows: number | null;
  loss_pct: number | null;
  target_empty: boolean | null;
  primary_key: string | null;
  primary_key_null_count: number | null;
  primary_key_null_pct: number | null;
  primary_key_duplicate_count: number | null;
}

export interface ColumnProfile {
  column_name: string;
  dtype: string;
  row_count: number;
  null_count: number;
  null_pct: number;
  distinct_count: number;
  distinct_pct: number;
  empty_string_count: number | null;
  empty_string_pct: number | null;
}

export interface TableProfile {
  table_name: string;
  row_count: number;
  column_count: number;
  columns: ColumnProfile[];
}

export interface ProfileResponse {
  profile: TableProfile;
  findings: ValidationFinding[];
}
