import { createContext, useContext, useState, type ReactNode } from "react";

// The backend confines config files to its samples/ directory and every
// endpoint requires a ?file= parameter. We keep the currently selected config
// filename in one place so all pages share it. This is intentionally minimal —
// no external state library — per the skeleton's scope.

export const DEFAULT_CONFIG_FILE = "demo_config.csv";

interface ConfigContextValue {
  configFile: string;
  setConfigFile: (file: string) => void;
}

const ConfigContext = createContext<ConfigContextValue | undefined>(undefined);

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [configFile, setConfigFile] = useState(DEFAULT_CONFIG_FILE);
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
