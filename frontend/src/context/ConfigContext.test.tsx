import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import {
  CONFIG_STORAGE_KEY,
  ConfigProvider,
  DEFAULT_CONFIG_FILE,
  RECENTS_STORAGE_KEY,
  useConfig,
} from "./ConfigContext";

/** Minimal consumer exposing the context for assertions. */
function Probe() {
  const { configFile, setConfigFile, recentConfigs } = useConfig();
  return (
    <div>
      <span data-testid="value">{configFile}</span>
      <span data-testid="recents">{recentConfigs.join(",")}</span>
      <button onClick={() => setConfigFile("showcase_config.csv")}>set</button>
      <button onClick={() => setConfigFile("other_config.csv")}>set-other</button>
    </div>
  );
}

function renderProbe() {
  return render(
    <ConfigProvider>
      <Probe />
    </ConfigProvider>,
  );
}

afterEach(() => {
  localStorage.clear();
});

describe("ConfigProvider", () => {
  it("defaults to the demo config when nothing is stored", () => {
    renderProbe();
    expect(screen.getByTestId("value")).toHaveTextContent(DEFAULT_CONFIG_FILE);
  });

  it("restores the stored config file on init", () => {
    localStorage.setItem(CONFIG_STORAGE_KEY, "showcase_config.csv");
    renderProbe();
    expect(screen.getByTestId("value")).toHaveTextContent("showcase_config.csv");
  });

  it("persists the selected config file to localStorage", () => {
    renderProbe();
    fireEvent.click(screen.getByText("set"));
    expect(screen.getByTestId("value")).toHaveTextContent("showcase_config.csv");
    expect(localStorage.getItem(CONFIG_STORAGE_KEY)).toBe("showcase_config.csv");
  });

  it("tracks recent configs newest-first and de-duplicated", () => {
    renderProbe();
    fireEvent.click(screen.getByText("set"));
    fireEvent.click(screen.getByText("set-other"));
    fireEvent.click(screen.getByText("set")); // re-select → moves to front, no dupe
    expect(screen.getByTestId("recents")).toHaveTextContent(
      "showcase_config.csv,other_config.csv",
    );
    expect(JSON.parse(localStorage.getItem(RECENTS_STORAGE_KEY)!)).toEqual([
      "showcase_config.csv",
      "other_config.csv",
    ]);
  });

  it("restores recents from localStorage on init", () => {
    localStorage.setItem(RECENTS_STORAGE_KEY, JSON.stringify(["a.csv", "b.csv"]));
    renderProbe();
    expect(screen.getByTestId("recents")).toHaveTextContent("a.csv,b.csv");
  });
});
