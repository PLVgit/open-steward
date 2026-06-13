import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError } from "./api";

function mockFetchOnce(body: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    json: async () => body,
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("api client", () => {
  it("builds the pipelines URL with the file param", async () => {
    const fetchMock = mockFetchOnce([]);
    vi.stubGlobal("fetch", fetchMock);

    await api.listPipelines("demo_config.csv");

    expect(fetchMock).toHaveBeenCalledWith("/api/pipelines/?file=demo_config.csv");
  });

  it("passes data_dir to the statistics endpoint", async () => {
    const fetchMock = mockFetchOnce([]);
    vi.stubGlobal("fetch", fetchMock);

    await api.getStatistics("demo_config.csv");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/statistics/?file=demo_config.csv&data_dir=.",
    );
  });

  it("includes data_dir on findings only when provided", async () => {
    const fetchMock = mockFetchOnce([]);
    vi.stubGlobal("fetch", fetchMock);

    await api.getFindings("demo_config.csv", ".");
    expect(fetchMock).toHaveBeenCalledWith("/api/findings/?file=demo_config.csv&data_dir=.");

    await api.getFindings("demo_config.csv");
    expect(fetchMock).toHaveBeenLastCalledWith("/api/findings/?file=demo_config.csv");
  });

  it("throws ApiError with the backend detail on non-OK responses", async () => {
    const fetchMock = mockFetchOnce({ detail: "File not found: x.csv" }, false, 404);
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.listPipelines("x.csv")).rejects.toBeInstanceOf(ApiError);
    await expect(api.listPipelines("x.csv")).rejects.toMatchObject({
      status: 404,
      detail: "File not found: x.csv",
    });
  });
});
