import { ExecutionCenterPage } from "./pages/ExecutionCenterPage";
import { ToastProvider } from "./components/ToastProvider";
import "./App.css";

export default function App() {
  return (
    <ToastProvider>
      <div className="app-shell">
      <aside className="sidebar">
        <p className="eyebrow">MODIR AGENT OS</p>
        <p className="sidebar-owner muted">Pedram AI Content Factory</p>
        <nav>
          <a className="nav-item active" href="#">
            Execution Center
          </a>
          <span className="nav-item disabled">Content Brain</span>
          <span className="nav-item disabled">Story Studio</span>
          <span className="nav-item disabled">Providers</span>
        </nav>
      </aside>
      <main className="app-main">
        <ExecutionCenterPage />
      </main>
    </div>
    </ToastProvider>
  );
}
