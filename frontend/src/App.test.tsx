import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { App } from "./App";
import { ConfigProvider } from "./context/ConfigContext";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ConfigProvider>
        <App />
      </ConfigProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear(); // the config selection persists via localStorage
});

describe("App shell", () => {
  it("renders all navigation links", () => {
    // Render a stub route (no backend fetch) so the nav can be asserted
    // synchronously without an unawaited Overview state update.
    renderAt("/graph");
    for (const label of ["Overview", "Graph", "Findings", "Statistics", "Profile"]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  it("renders the Profile page at the /profile route", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          profile: { table_name: "staging.orders", row_count: 0, column_count: 0, columns: [] },
          findings: [],
        }),
      }),
    );
    renderAt("/profile");
    expect(screen.getByText("Table Profile")).toBeInTheDocument();
  });

  it("shows the job count on the Overview page when the backend responds", async () => {
    const jobs = [
      { config_key: "etl_001", pipeline_name: "Load Orders", enabled: true },
      { config_key: "etl_002", pipeline_name: "Old Job", enabled: false },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => jobs }),
    );
    renderAt("/");
    await waitFor(() => expect(screen.getByText(/Connected\./)).toBeInTheDocument());
    expect(screen.getByText(/2 jobs \(1 enabled\)/)).toBeInTheDocument();
  });

  it("shows an error message when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
    renderAt("/");
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });

  it("applies a new config file on Enter, not on every keystroke", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, status: 200, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);
    renderAt("/");
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/pipelines/?file=demo_config.csv"),
    );

    const input = screen.getByLabelText("Config file");
    fireEvent.change(input, { target: { value: "showcase_config.csv" } });
    // Typing alone must not trigger a refetch (no error flashes mid-typing).
    expect(fetchMock).not.toHaveBeenCalledWith("/api/pipelines/?file=showcase_config.csv");

    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/pipelines/?file=showcase_config.csv"),
    );
  });
});
