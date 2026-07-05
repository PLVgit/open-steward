import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { GraphPage } from "./GraphPage";
import { ConfigProvider } from "@/context/ConfigContext";
import type { GraphResponse } from "@/lib/types";

// Mock the React Flow wrapper so tests don't mount the canvas (jsdom has no
// layout measurement / ResizeObserver). We assert on node/edge counts instead.
vi.mock("@/components/graph/PipelineFlow", () => ({
  PipelineFlow: ({
    nodes,
    edges,
    jobNames,
  }: {
    nodes: unknown[];
    edges: unknown[];
    jobNames?: Map<string, string>;
  }) => (
    <div data-testid="flow">
      {nodes.length} nodes, {edges.length} edges, {jobNames?.size ?? 0} names
    </div>
  ),
}));

/** Serve the graph body from /graph/ and an optional job list from /pipelines/. */
function mockGraphResponse(body: GraphResponse, jobs: unknown[] = []) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: unknown) =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () => (String(url).includes("/pipelines/") ? jobs : body),
      }),
    ),
  );
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ConfigProvider>
        <GraphPage />
      </ConfigProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

const DAG: GraphResponse = {
  nodes: ["raw.orders", "staging.orders"],
  edges: [{ source: "raw.orders", target: "staging.orders", config_key: "etl_001" }],
  execution_order: ["raw.orders", "staging.orders"],
  cycle_detected: false,
};

describe("GraphPage", () => {
  it("shows a loading state before the graph resolves", () => {
    mockGraphResponse(DAG);
    renderPage();
    expect(screen.getByText(/Loading graph/)).toBeInTheDocument();
  });

  it("renders the flow with node and edge counts on success", async () => {
    mockGraphResponse(DAG);
    renderPage();
    await waitFor(() => expect(screen.getByTestId("flow")).toBeInTheDocument());
    expect(screen.getByTestId("flow")).toHaveTextContent("2 nodes, 1 edges");
  });

  it("passes pipeline names to the flow for the edge inspector", async () => {
    mockGraphResponse(DAG, [
      { config_key: "etl_001", pipeline_name: "Load Orders", enabled: true },
    ]);
    renderPage();
    await waitFor(() => expect(screen.getByTestId("flow")).toHaveTextContent("1 names"));
  });

  it("shows an error message when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    renderPage();
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });

  it("shows a cycle banner when a cycle is detected", async () => {
    mockGraphResponse({
      nodes: ["a", "b"],
      edges: [
        { source: "a", target: "b", config_key: "etl_1" },
        { source: "b", target: "a", config_key: "etl_2" },
      ],
      execution_order: null,
      cycle_detected: true,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Cycle detected")).toBeInTheDocument());
  });
});
