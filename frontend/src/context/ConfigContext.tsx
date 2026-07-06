import { createContext, useContext, useState, type ReactNode } from "react";

// The backend confines config files to its samples/ directory and every
// endpoint requires a ?file= parameter. We keep the currently selected config
// filename in one place so all pages share it. This is intentionally minimal —
// no external state library — per the skeleton's scope.

export const DEFAULT_CONFIG_FILE = "demo_config.csv";

// The selection persists across reloads so a demo session (e.g. on
// showcase_config.csv) survives a refresh.
export const CONFIG_STORAGE_KEY = "open-steward.config-file";
export const RECENTS_STORAGE_KEY = "open-steward.recent-configs";
const MAX_RECENTS = 5;

function readStorage(key: string): string | null {
  // localStorage can throw (disabled storage, some private modes) — fall back.
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

function initialConfigFile(): string {
  const stored = readStorage(CONFIG_STORAGE_KEY);
  return stored && stored.trim() ? stored : DEFAULT_CONFIG_FILE;
}

function initialRecents(): string[] {
  const stored = readStorage(RECENTS_STORAGE_KEY);
  if (!stored) return [];
  try {
    const parsed = JSON.parse(stored);
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

interface ConfigContextValue {
  configFile: string;
  setConfigFile: (file: string) => void;
  /** Most-recently used config files, newest first (for input suggestions). */
  recentConfigs: string[];
}

const ConfigContext = createContext<ConfigContextValue | undefined>(undefined);

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [configFile, setConfigFileState] = useState(initialConfigFile);
  const [recentConfigs, setRecentConfigs] = useState<string[]>(initialRecents);

  const setConfigFile = (file: string) => {
    setConfigFileState(file);
    writeStorage(CONFIG_STORAGE_KEY, file);
    setRecentConfigs((prev) => {
      const next = [file, ...prev.filter((f) => f !== file)].slice(0, MAX_RECENTS);
      writeStorage(RECENTS_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  };

  return (
    <ConfigContext.Provider value={{ configFile, setConfigFile, recentConfigs }}>
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
