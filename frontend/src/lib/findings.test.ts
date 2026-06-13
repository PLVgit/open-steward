import { describe, expect, it } from "vitest";

import { filterBySeverity, summarizeFindings } from "./findings";
import type { ValidationFinding } from "./types";

function finding(partial: Partial<ValidationFinding>): ValidationFinding {
  return {
    finding_type: "x",
    severity: "info",
    message: "m",
    affected_job: null,
    affected_table: null,
    recommendation: null,
    ...partial,
  };
}

const FINDINGS: ValidationFinding[] = [
  finding({ severity: "error" }),
  finding({ severity: "error" }),
  finding({ severity: "warning" }),
  finding({ severity: "info" }),
];

describe("summarizeFindings", () => {
  it("counts by severity and total", () => {
    expect(summarizeFindings(FINDINGS)).toEqual({ error: 2, warning: 1, info: 1, total: 4 });
  });

  it("handles an empty list", () => {
    expect(summarizeFindings([])).toEqual({ error: 0, warning: 0, info: 0, total: 0 });
  });
});

describe("filterBySeverity", () => {
  it("returns everything for 'all'", () => {
    expect(filterBySeverity(FINDINGS, "all")).toHaveLength(4);
  });

  it("returns only the matching severity", () => {
    expect(filterBySeverity(FINDINGS, "error")).toHaveLength(2);
    expect(filterBySeverity(FINDINGS, "warning")).toHaveLength(1);
    expect(filterBySeverity(FINDINGS, "info")).toHaveLength(1);
  });
});
