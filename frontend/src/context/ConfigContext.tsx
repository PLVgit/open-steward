import { createContext, useContext, useState, type ReactNode } from "react";

// The backend confines config files to its samples/ directory and every
// endpoint requires a ?file= parameter. We keep the currently selected config
// filename in one place so all pages share it. This is intentionally minimal —
// no external state library — per the skeleton's scope.

export const DEFAULT_CONFIG_FILE = "demo_config.csv";

// The selection persists across reloads so a demo session (e.g. on
// showcase_config.csv) survives a refresh.
export const CONFIG_STORAGE_KEY = "open-steward.config-file";

function initialConfigFile(): string {
  // localStorage can throw (disabled storage, some private modes) — fall back.
  try {
    const stored = window.localStorage.getItem(CONFIG_STORAGE_KEY);
    if (stored && stored.trim()) return stored;
  } catch {
    /* ignore */
  }
  return DEFAULT_CONFIG_FILE;
}

interface ConfigContextValue {
  configFile: string;
  setConfigFile: (file: string) => void;
}

const ConfigContext = createContext<ConfigContextValue | undefined>(undefined);

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [configFile, setConfigFileState] = useState(initialConfigFile);

  const setConfigFile = (file: string) => {
    setConfigFileState(file);
    try {
      window.localStorage.setItem(CONFIG_STORAGE_KEY, file);
    } catch {
      /* ignore */
    }
  };

  return (
    <ConfigContext.Provider value={{ configFile, setConfigFile }}>
      {children}
    </ConfigContext.Provider>
  );
}

export function useConfig(): ConfigContextValue {
  const ctx = useContext(ConfigContext);
  if (!ctx) {
    throw new Error("useConfig must be used within a ConfigProvider");
  }
  return ctx;
}
