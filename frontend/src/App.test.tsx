import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

  it("renders a placeholder for a not-yet-built route", () => {
    renderAt("/profile");
    expect(
      screen.getByText(/This view is a placeholder. It will be implemented in Ticket 18/),
    ).toBeInTheDocument();
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
});
