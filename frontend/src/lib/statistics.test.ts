import { describe, expect, it } from "vitest";

import { boolText, dash, pct, summarizeStatistics } from "./statistics";
import type { JobStatistics } from "./types";

function stat(partial: Partial<JobStatistics>): JobStatistics {
  return {
    config_key: "etl",
    pipeline_name: "Job",
    source_table: "raw.t",
    target_table: "staging.t",
    source_count: 10,
    target_count: 10,
    lost_rows: 0,
    loss_pct: 0,
    target_empty: false,
    primary_key: "id",
    primary_key_null_count: 0,
    primary_key_null_pct: 0,
    primary_key_duplicate_count: 0,
    ...partial,
  };
}

describe("summarizeStatistics", () => {
  it("counts row-loss, missing-data and PK-issue jobs", () => {
    const stats = [
      stat({ config_key: "a", lost_rows: 2 }), // row loss
      stat({ config_key: "b", target_count: null, lost_rows: null }), // missing data
      stat({ config_key: "c", primary_key_duplicate_count: 1 }), // pk issue
      stat({ config_key: "d", primary_key_null_count: 3 }), // pk issue
      stat({ config_key: "e" }), // clean
    ];
    expect(summarizeStatistics(stats)).toEqual({
      total: 5,
      withRowLoss: 1,
      withMissingData: 1,
      withPkIssues: 2,
    });
  });

  it("treats zero as a real value, not an issue", () => {
    const stats = [stat({ lost_rows: 0, primary_key_null_count: 0, primary_key_duplicate_count: 0 })];
    expect(summarizeStatistics(stats)).toEqual({
      total: 1,
      withRowLoss: 0,
      withMissingData: 0,
      withPkIssues: 0,
    });
  });

  it("treats null PK metrics as not-an-issue", () => {
    const stats = [
      stat({ primary_key: null, primary_key_null_count: null, primary_key_duplicate_count: null }),
    ];
    expect(summarizeStatistics(stats).withPkIssues).toBe(0);
  });

  it("handles an empty list", () => {
    expect(summarizeStatistics([])).toEqual({
      total: 0,
      withRowLoss: 0,
      withMissingData: 0,
      withPkIssues: 0,
    });
  });
});

describe("formatters preserve the null-vs-zero distinction", () => {
  it("dash renders 0 as '0' and null as '—'", () => {
    expect(dash(0)).toBe("0");
    expect(dash(42)).toBe("42");
    expect(dash(null)).toBe("—");
  });

  it("pct renders 0 as '0%' and null as '—'", () => {
    expect(pct(0)).toBe("0%");
    expect(pct(12.5)).toBe("12.5%");
    expect(pct(null)).toBe("—");
  });

  it("boolText renders false as 'no', true as 'yes', null as '—'", () => {
    expect(boolText(false)).toBe("no");
    expect(boolText(true)).toBe("yes");
    expect(boolText(null)).toBe("—");
  });
});
