import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  createLocalUser,
  fetchAuthConfig,
  fetchAuthMe,
  fetchLocalUser,
  getAuthToken,
  localAutoLogin,
  loginUser,
  logoutUser,
  setAuthToken,
} from "../api/platformClient";

type AuthContextValue = {
  ready: boolean;
  localMode: boolean;
  userExists: boolean;
  authenticated: boolean;
  username: string;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [localMode, setLocalMode] = useState(true);
  const [userExists, setUserExists] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        const config = await fetchAuthConfig();
        setLocalMode(Boolean(config.local_mode));
        setUserExists(Boolean(config.user_exists));
        if (config.username) {
          setUsername(config.username);
        }

        const token = getAuthToken();
        if (config.local_mode) {
          if (token) {
            const me = await fetchAuthMe();
            if (me.authenticated) {
              setAuthenticated(true);
              setUsername(me.username || config.username || "");
            } else {
              const result = await localAutoLogin();
              setAuthToken(result.token);
              setAuthenticated(true);
              setUsername(result.username);
              setUserExists(true);
            }
          } else {
            const result = await localAutoLogin();
            setAuthToken(result.token);
            setAuthenticated(true);
            setUsername(result.username);
            setUserExists(true);
          }
        } else if (token) {
          const me = await fetchAuthMe();
          setAuthenticated(Boolean(me.authenticated));
          setUsername(me.username || "");
          if (!config.user_exists) {
            const user = await fetchLocalUser();
            setUserExists(Boolean(user.exists));
          }
        } else if (!config.user_exists) {
          const user = await fetchLocalUser();
          setUserExists(Boolean(user.exists));
        }
      } catch {
        setUserExists(false);
        setAuthenticated(false);
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ready,
      localMode,
      userExists,
      authenticated,
      username,
      login: async (name, password) => {
        const result = await loginUser(name, password);
        setAuthToken(result.token);
        setAuthenticated(true);
        setUsername(result.username);
        setUserExists(true);
      },
      register: async (name, password) => {
        const result = await createLocalUser(name, password);
        setAuthToken(result.token);
        setAuthenticated(true);
        setUsername(result.username);
        setUserExists(true);
      },
      logout: async () => {
        try {
          await logoutUser();
        } finally {
          setAuthToken("");
          setAuthenticated(false);
          setUsername("");
        }
      },
    }),
    [ready, localMode, userExists, authenticated, username],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
