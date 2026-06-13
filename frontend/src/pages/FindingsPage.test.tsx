import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { FindingsPage } from "./FindingsPage";
import { ConfigProvider } from "@/context/ConfigContext";
import type { ValidationFinding } from "@/lib/types";

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

function mockFindings(body: ValidationFinding[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body }),
  );
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ConfigProvider>
        <FindingsPage />
      </ConfigProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

const SAMPLE: ValidationFinding[] = [
  finding({
    finding_type: "duplicate_target",
    severity: "error",
    message: "Two jobs write to mart.orders.",
    affected_table: "mart.orders",
    recommendation: "Give each job a distinct target.",
  }),
  finding({
    finding_type: "select_star",
    severity: "warning",
    message: "SELECT * is fragile.",
    affected_job: "etl_001",
  }),
  finding({
    finding_type: "missing_filter_on_full_load",
    severity: "info",
    message: "Full load without a filter.",
  }),
];

describe("FindingsPage", () => {
  it("shows a loading state before findings resolve", () => {
    mockFindings(SAMPLE);
    renderPage();
    expect(screen.getByText(/Loading findings/)).toBeInTheDocument();
  });

  it("renders summary counts and a row per finding", async () => {
    mockFindings(SAMPLE);
    renderPage();
    await waitFor(() => expect(screen.getByText("1 errors")).toBeInTheDocument());
    expect(screen.getByText("1 warnings")).toBeInTheDocument();
    expect(screen.getByText("1 info")).toBeInTheDocument();
    expect(screen.getByText("duplicate_target")).toBeInTheDocument();
    expect(screen.getByText("select_star")).toBeInTheDocument();
    expect(screen.getByText("missing_filter_on_full_load")).toBeInTheDocument();
  });

  it("renders a recommendation only when present", async () => {
    mockFindings(SAMPLE);
    renderPage();
    await waitFor(() => expect(screen.getByText("duplicate_target")).toBeInTheDocument());
    // The error finding has a recommendation; the warning/info do not.
    expect(screen.getByText("→ Give each job a distinct target.")).toBeInTheDocument();
    expect(screen.queryAllByText(/^→/)).toHaveLength(1);
  });

  it("filters to a single severity when a filter button is clicked", async () => {
    mockFindings(SAMPLE);
    renderPage();
    await waitFor(() => expect(screen.getByText("select_star")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Errors" }));

    expect(screen.getByText("duplicate_target")).toBeInTheDocument();
    expect(screen.queryByText("select_star")).not.toBeInTheDocument();
    expect(screen.queryByText("missing_filter_on_full_load")).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no findings", async () => {
    mockFindings([]);
    renderPage();
    await waitFor(() => expect(screen.getByText(/No findings/)).toBeInTheDocument());
  });

  it("shows an error state when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    renderPage();
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });
});
