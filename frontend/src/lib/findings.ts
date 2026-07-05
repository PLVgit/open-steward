import type { Severity, ValidationFinding } from "./types";

export type SeverityFilter = Severity | "all";

export interface FindingsSummary {
  error: number;
  warning: number;
  info: number;
  total: number;
}

/** Count findings by severity. Pure and testable. */
export function summarizeFindings(findings: ValidationFinding[]): FindingsSummary {
  const summary: FindingsSummary = { error: 0, warning: 0, info: 0, total: findings.length };
  for (const f of findings) {
    if (f.severity === "error") summary.error += 1;
    else if (f.severity === "warning") summary.warning += 1;
    else if (f.severity === "info") summary.info += 1;
  }
  return summary;
}

/** Return findings matching the given severity, or all of them for "all". */
export function filterBySeverity(
  findings: ValidationFinding[],
  severity: SeverityFilter,
): ValidationFinding[] {
  if (severity === "all") return findings;
  return findings.filter((f) => f.severity === severity);
}

const SEVERITY_RANK: Record<Severity, number> = { error: 0, warning: 1, info: 2 };

/** Order findings errors → warnings → info, keeping the original order within
 *  each severity (Array.prototype.sort is stable). Does not mutate the input. */
export function sortBySeverity(findings: ValidationFinding[]): ValidationFinding[] {
  return [...findings].sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);
}
