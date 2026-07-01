import { createContext, useContext, useMemo, useState, ReactNode } from "react";

const STORAGE_KEY = "modir_developer_mode";

type AppModeContextValue = {
  developerMode: boolean;
  setDeveloperMode: (value: boolean) => void;
};

const AppModeContext = createContext<AppModeContextValue | undefined>(undefined);

export function AppModeProvider({ children }: { children: ReactNode }) {
  const [developerMode, setDeveloperModeState] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });

  const setDeveloperMode = (value: boolean) => {
    setDeveloperModeState(value);
    try {
      localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
    } catch {
      /* ignore */
    }
  };

  const value = useMemo(() => ({ developerMode, setDeveloperMode }), [developerMode]);
  return <AppModeContext.Provider value={value}>{children}</AppModeContext.Provider>;
}

export function useAppMode() {
  const ctx = useContext(AppModeContext);
  if (!ctx) {
    throw new Error("useAppMode must be used within AppModeProvider");
  }
  return ctx;
}
