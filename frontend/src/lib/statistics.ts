import type { JobStatistics } from "./types";

export interface StatisticsSummary {
  total: number;
  withRowLoss: number;
  withMissingData: number;
  withPkIssues: number;
}

/**
 * Summarize a set of per-job statistics. Pure and testable.
 *
 * Null metrics mean "not computable" and never count as an issue; only real
 * positive values do. A zero value is a real value, not a missing one.
 */
export function summarizeStatistics(stats: JobStatistics[]): StatisticsSummary {
  let withRowLoss = 0;
  let withMissingData = 0;
  let withPkIssues = 0;

  for (const s of stats) {
    if (s.lost_rows != null && s.lost_rows > 0) withRowLoss += 1;
    if (s.source_count === null || s.target_count === null) withMissingData += 1;
    if (
      (s.primary_key_null_count ?? 0) > 0 ||
      (s.primary_key_duplicate_count ?? 0) > 0
    ) {
      withPkIssues += 1;
    }
  }

  return { total: stats.length, withRowLoss, withMissingData, withPkIssues };
}

/** Render a nullable number, preserving the null-vs-zero distinction. */
export function dash(value: number | null): string {
  return value === null ? "—" : String(value);
}

/** Render a nullable percentage. 0 renders as "0%", null as "—". */
export function pct(value: number | null): string {
  return value === null ? "—" : `${value}%`;
}

/** Render a nullable boolean as yes/no, or "—" when not computable. */
export function boolText(value: boolean | null): string {
  if (value === null) return "—";
  return value ? "yes" : "no";
}
