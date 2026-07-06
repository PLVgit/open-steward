import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { StatisticsPage } from "./StatisticsPage";
import { ConfigProvider } from "@/context/ConfigContext";
import type { JobStatistics } from "@/lib/types";

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

function mockStats(body: JobStatistics[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body }),
  );
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ConfigProvider>
        <StatisticsPage />
      </ConfigProvider>
    </MemoryRouter>,
  );
}

/** Read a metric value by its label (single-job renders only). */
function metricValue(label: string): string {
  const valueEl = screen.getByText(label).nextElementSibling;
  return valueEl?.textContent ?? "";
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("StatisticsPage", () => {
  it("shows a loading state before statistics resolve", () => {
    mockStats([stat({})]);
    renderPage();
    expect(screen.getByText(/Loading statistics/)).toBeInTheDocument();
  });

  it("renders a card per job with its config_key", async () => {
    mockStats([
      stat({ config_key: "etl_001" }),
      stat({ config_key: "etl_002" }),
      stat({ config_key: "etl_003" }),
    ]);
    renderPage();
    await waitFor(() => expect(screen.getByText("etl_001")).toBeInTheDocument());
    expect(screen.getByText("etl_002")).toBeInTheDocument();
    expect(screen.getByText("etl_003")).toBeInTheDocument();
  });

  it("renders null as '—' and real zero as '0' (single job)", async () => {
    mockStats([
      stat({
        config_key: "etl_x",
        target_count: null,
        lost_rows: null,
        loss_pct: null,
        target_empty: null,
      }),
    ]);
    renderPage();
    await waitFor(() => expect(screen.getByText("etl_x")).toBeInTheDocument());

    expect(metricValue("target_count")).toBe("—"); // null → dash
    expect(metricValue("source_count")).toBe("10"); // real value
    expect(metricValue("loss_pct")).toBe("—"); // null → dash
    expect(metricValue("target_empty")).toBe("—"); // null → dash
  });

  it("renders a real zero metric as '0', not '—'", async () => {
    mockStats([stat({ config_key: "etl_zero", lost_rows: 0, loss_pct: 0 })]);
    renderPage();
    await waitFor(() => expect(screen.getByText("etl_zero")).toBeInTheDocument());
    expect(metricValue("lost_rows")).toBe("0");
    expect(metricValue("loss_pct")).toBe("0%");
    expect(metricValue("pk_duplicate_count")).toBe("0");
  });

  it("renders correct summary counts for a mixed set", async () => {
    mockStats([
      stat({ config_key: "a", lost_rows: 2 }),
      stat({ config_key: "b", target_count: null, lost_rows: null }),
      stat({ config_key: "c", primary_key_duplicate_count: 1 }),
    ]);
    renderPage();
    await waitFor(() => expect(screen.getByText("jobs with statistics")).toBeInTheDocument());

    const summaryValue = (label: string) =>
      screen.getByText(label).previousElementSibling?.textContent;
    expect(summaryValue("jobs with statistics")).toBe("3");
    expect(summaryValue("jobs with row loss")).toBe("1");
    expect(summaryValue("jobs with missing data")).toBe("1");
    expect(summaryValue("jobs with PK issues")).toBe("1");
  });

  it("shows an empty state when there are no jobs", async () => {
    mockStats([]);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/No enabled jobs with statistics/)).toBeInTheDocument(),
    );
  });

  it("shows an error state when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    renderPage();
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });

  it("recovers via the Retry button after an error", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("down"))
      .mockResolvedValue({ ok: true, status: 200, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Retry/ }));

    await waitFor(() =>
      expect(screen.getByText(/No enabled jobs with statistics/)).toBeInTheDocument(),
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
