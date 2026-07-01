import { useState } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { AppModeProvider, useAppMode } from "./context/AppModeContext";
import { ToastProvider } from "./components/ToastProvider";
import { ProductDashboardPage } from "./pages/ProductDashboardPage";
import { CreateVideoPage } from "./pages/CreateVideoPage";
import { SchedulePlannerPage } from "./pages/SchedulePlannerPage";
import { ResultsPage } from "./pages/ResultsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { UpgradeCenterPage } from "./pages/UpgradeCenterPage";
import { DeveloperConsolePage } from "./pages/DeveloperConsolePage";
import { LoginPage } from "./pages/LoginPage";
import { AutomationCenterPage } from "./pages/AutomationCenterPage";
import { UploadCenterPage } from "./pages/UploadCenterPage";
import type { UserNavItem } from "./product/constants";
import "./App.css";
import "./styles/platform-theme.css";

function AppShell() {
  const { developerMode, setDeveloperMode } = useAppMode();
  const { authenticated, username, logout, ready, localMode } = useAuth();
  const [nav, setNav] = useState<UserNavItem>("dashboard");

  const userNav: { id: UserNavItem; label: string }[] = [
    { id: "dashboard", label: "Dashboard" },
    { id: "create", label: "Create Video" },
    { id: "schedule", label: "Schedule Planner" },
    { id: "results", label: "Results" },
    { id: "automation", label: "Automation Center" },
    { id: "upload", label: "Upload Center" },
    { id: "upgrade", label: "Upgrade Center" },
    { id: "settings", label: "Settings" },
  ];

  function renderPage() {
    if (nav === "developer") return <DeveloperConsolePage />;
    if (nav === "create") return <CreateVideoPage />;
    if (nav === "schedule") return <SchedulePlannerPage />;
    if (nav === "results") return <ResultsPage />;
    if (nav === "automation") return <AutomationCenterPage />;
    if (nav === "upload") return <UploadCenterPage />;
    if (nav === "upgrade") return <UpgradeCenterPage />;
    if (nav === "settings") return <SettingsPage />;
    return <ProductDashboardPage />;
  }

  if (!ready) {
    return <div className="login-page product-page"><p className="muted">Loading platform…</p></div>;
  }

  if (!authenticated) {
    return <LoginPage />;
  }

  return (
    <div className="app-shell platform-shell">
      <aside className="sidebar platform-sidebar">
        <p className="eyebrow">MODIR AGENT OS</p>
        <p className="sidebar-owner muted">Pedram AI Content Factory</p>
        {!localMode && <p className="sidebar-user">Signed in as {username}</p>}
        <nav>
          {userNav.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item nav-button ${nav === item.id ? "active" : ""}`}
              onClick={() => setNav(item.id)}
            >
              {item.label}
            </button>
          ))}
          {developerMode && (
            <button
              type="button"
              className={`nav-item nav-button dev-nav ${nav === "developer" ? "active" : ""}`}
              onClick={() => setNav("developer")}
            >
              Developer Console
            </button>
          )}
        </nav>
        <div className="sidebar-footer">
          {!localMode && (
            <button type="button" className="link-button full-width" onClick={() => void logout()}>
              Logout
            </button>
          )}
          <label className="field-row compact">
            <input type="checkbox" checked={developerMode} onChange={(e) => setDeveloperMode(e.target.checked)} />
            Developer Mode
          </label>
        </div>
      </aside>
      <main className="app-main">{renderPage()}</main>
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <AppModeProvider>
          <AppShell />
        </AppModeProvider>
      </AuthProvider>
    </ToastProvider>
  );
}
