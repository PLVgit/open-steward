import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ProfilePage } from "./ProfilePage";
import { ConfigProvider } from "@/context/ConfigContext";
import type { ColumnProfile, ProfileResponse, ValidationFinding } from "@/lib/types";

function column(partial: Partial<ColumnProfile>): ColumnProfile {
  return {
    column_name: "col",
    dtype: "BIGINT",
    row_count: 18,
    null_count: 0,
    null_pct: 0,
    distinct_count: 18,
    distinct_pct: 100,
    empty_string_count: null,
    empty_string_pct: null,
    ...partial,
  };
}

function response(partial: {
  columns?: ColumnProfile[];
  findings?: ValidationFinding[];
  table_name?: string;
  row_count?: number;
  column_count?: number;
}): ProfileResponse {
  return {
    profile: {
      table_name: partial.table_name ?? "staging.orders",
      row_count: partial.row_count ?? 18,
      column_count: partial.column_count ?? (partial.columns?.length ?? 0),
      columns: partial.columns ?? [],
    },
    findings: partial.findings ?? [],
  };
}

function mockProfile(body: ProfileResponse) {
  return vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ConfigProvider>
        <ProfilePage />
      </ConfigProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

/** Read a table cell value by its column-name row, by header index. */
function cellInRow(columnName: string, headerIndex: number): string {
  const row = screen.getByText(columnName).closest("tr")!;
  return row.querySelectorAll("td")[headerIndex]?.textContent ?? "";
}

const SAMPLE = response({
  table_name: "staging.orders",
  row_count: 18,
  column_count: 2,
  columns: [
    column({ column_name: "order_id", dtype: "BIGINT", empty_string_count: null, empty_string_pct: null }),
    column({
      column_name: "coupon_code",
      dtype: "VARCHAR",
      null_count: 15,
      null_pct: 83.3,
      distinct_count: 3,
      distinct_pct: 16.7,
      empty_string_count: 0,
      empty_string_pct: 0,
    }),
  ],
  findings: [
    {
      finding_type: "high_null_rate",
      severity: "warning",
      message: "Column 'coupon_code' has 83.3% null values.",
      affected_job: null,
      affected_table: "staging.orders",
      recommendation: "Investigate whether nulls are expected.",
    },
  ],
});

describe("ProfilePage", () => {
  it("shows a loading state before the profile resolves", () => {
    vi.stubGlobal("fetch", mockProfile(SAMPLE));
    renderPage();
    expect(screen.getByText(/Loading profile/)).toBeInTheDocument();
  });

  it("renders the table-level summary", async () => {
    vi.stubGlobal("fetch", mockProfile(SAMPLE));
    renderPage();
    await waitFor(() => expect(screen.getByText("order_id")).toBeInTheDocument());
    const summaryValue = (label: string) =>
      screen.getByText(label).nextElementSibling?.textContent;
    expect(summaryValue("rows")).toBe("18");
    expect(summaryValue("columns")).toBe("2");
    // table name appears in the summary (and in the default input)
    expect(screen.getAllByText("staging.orders").length).toBeGreaterThan(0);
  });

  it("renders a row per column", async () => {
    vi.stubGlobal("fetch", mockProfile(SAMPLE));
    renderPage();
    await waitFor(() => expect(screen.getByText("order_id")).toBeInTheDocument());
    expect(screen.getByText("coupon_code")).toBeInTheDocument();
  });

  it("preserves null-vs-zero for empty-string stats", async () => {
    vi.stubGlobal("fetch", mockProfile(SAMPLE));
    renderPage();
    await waitFor(() => expect(screen.getByText("order_id")).toBeInTheDocument());
    // order_id is BIGINT → empty_string_count null → "—"; coupon_code VARCHAR → 0
    expect(cellInRow("order_id", 6)).toBe("—");
    expect(cellInRow("coupon_code", 6)).toBe("0");
  });

  it("renders profile findings", async () => {
    vi.stubGlobal("fetch", mockProfile(SAMPLE));
    renderPage();
    await waitFor(() => expect(screen.getByText("high_null_rate")).toBeInTheDocument());
  });

  it("refetches with the new table name when submitted", async () => {
    const fetchMock = mockProfile(SAMPLE);
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    await waitFor(() => expect(screen.getByText("order_id")).toBeInTheDocument());

    const input = screen.getByLabelText("Table name");
    fireEvent.change(input, { target: { value: "staging.customers" } });
    fireEvent.click(screen.getByRole("button", { name: "Profile" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/profile/?table=staging.customers&data_dir=.",
      ),
    );
  });

  it("shows an error state when the table is not found", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: "No file found for table 'staging.missing'." }),
      }),
    );
    renderPage();
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent(/No file found/);
  });
});
