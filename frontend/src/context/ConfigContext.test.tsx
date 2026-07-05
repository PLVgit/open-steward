import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import {
  CONFIG_STORAGE_KEY,
  ConfigProvider,
  DEFAULT_CONFIG_FILE,
  useConfig,
} from "./ConfigContext";

/** Minimal consumer exposing the context for assertions. */
function Probe() {
  const { configFile, setConfigFile } = useConfig();
  return (
    <div>
      <span data-testid="value">{configFile}</span>
      <button onClick={() => setConfigFile("showcase_config.csv")}>set</button>
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
});
