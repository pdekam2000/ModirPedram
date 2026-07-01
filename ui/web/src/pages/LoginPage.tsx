import { useState } from "react";
import { useAuth } from "../context/AuthContext";

export function LoginPage() {
  const { userExists, login, register } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (!userExists) {
        if (password !== confirm) {
          throw new Error("Passwords do not match.");
        }
        await register(username, password);
      } else {
        await login(username, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page product-page">
      <header className="header">
        <div>
          <p className="eyebrow">ModirAgent OS</p>
          <h1>{userExists ? "Local Login" : "Create Local User"}</h1>
          <p className="subtitle">Local-only gate. No cloud accounts. Password is hashed on disk.</p>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <form className="card login-card" onSubmit={(e) => void handleSubmit(e)}>
        <label className="field-row full-width">
          Username
          <input className="filter-input full-width" value={username} onChange={(e) => setUsername(e.target.value)} />
        </label>
        <label className="field-row full-width">
          Password
          <input
            className="filter-input full-width"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {!userExists && (
          <label className="field-row full-width">
            Confirm password
            <input
              className="filter-input full-width"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </label>
        )}
        <button type="submit" className="primary-btn" disabled={busy}>
          {busy ? "Please wait…" : userExists ? "Login" : "Create Local User"}
        </button>
      </form>
    </div>
  );
}
