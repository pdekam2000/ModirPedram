import { SessionDetail, SessionActionEligibility, SessionActionResponse, SessionActionType } from "../api/client";
import { ACTION_META, SESSION_ACTIONS } from "../utils/sessionActions";
import { StatusBadge } from "./shared";

type AuditEntry = {
  event_id?: string;
  timestamp?: string;
  action?: string;
  actor?: string;
  previous_state?: string;
  next_state?: string;
  reason?: string;
  allowed?: boolean;
  blocked_reason?: string | null;
};

type Props = {
  detail: SessionDetail;
  eligibility: SessionActionEligibility | null;
  loading?: boolean;
  error?: string | null;
  lastResult?: SessionActionResponse | null;
  onActionClick: (action: SessionActionType) => void;
};

function auditEntries(detail: SessionDetail): AuditEntry[] {
  const raw = detail.session?.operations_audit_log;
  if (!Array.isArray(raw)) {
    return [];
  }
  return [...raw].reverse().slice(0, 20) as AuditEntry[];
}

export function SessionActionsPanel({
  detail,
  eligibility,
  loading,
  error,
  lastResult,
  onActionClick,
}: Props) {
  const currentState = eligibility?.current_state || detail.status || "—";
  const history = auditEntries(detail);
  const isLegacy = !detail.session_schema_version && !detail.execution_runtime;

  return (
    <div className="panel-stack actions-panel">
      {isLegacy && (
        <div className="info-banner">
          Legacy session — limited operations metadata. Eligibility uses current state only.
        </div>
      )}

      <section className="domain-card">
        <div className="domain-card-header">
          <h3>Current State</h3>
        </div>
        <div className="panel-body">
          <div className="kv-grid">
            <div>
              <span className="kv-label">Session state</span>
              <StatusBadge status={currentState} />
            </div>
            <div>
              <span className="kv-label">Eligibility API</span>
              <span>{loading ? "Loading…" : error ? "Error" : "Ready"}</span>
            </div>
          </div>
          {error && <p className="action-error-inline">{error}</p>}
        </div>
      </section>

      <section className="domain-card">
        <div className="domain-card-header">
          <h3>Action Eligibility</h3>
        </div>
        <div className="panel-body action-eligibility-grid">
          {SESSION_ACTIONS.map((action) => {
            const gate = eligibility?.actions?.[action];
            const allowed = gate?.allowed === true;
            const meta = ACTION_META[action];
            return (
              <article key={action} className={`action-eligibility-card ${allowed ? "allowed" : "blocked"}`}>
                <div className="action-eligibility-head">
                  <strong>{meta.label}</strong>
                  <span className={allowed ? "action-pill-allowed" : "action-pill-blocked"}>
                    {allowed ? "Allowed" : "Blocked"}
                  </span>
                </div>
                <p className="muted action-eligibility-reason">{gate?.reason || "—"}</p>
                <p className="action-safety-note">{meta.safetyNote}</p>
                <button
                  type="button"
                  className={meta.variant === "danger" ? "btn-danger" : meta.variant === "neutral" ? "btn-neutral" : ""}
                  disabled={loading || !allowed}
                  onClick={() => onActionClick(action)}
                >
                  {meta.label}
                </button>
              </article>
            );
          })}
        </div>
      </section>

      {lastResult && (
        <section className="domain-card">
          <div className="domain-card-header">
            <h3>Last Action Result</h3>
          </div>
          <div className="panel-body">
            <div className="kv-grid">
              <div>
                <span className="kv-label">Action</span>
                <span>{lastResult.action}</span>
              </div>
              <div>
                <span className="kv-label">Outcome</span>
                <span>{lastResult.ok ? "Success" : "Blocked"}</span>
              </div>
              <div>
                <span className="kv-label">Transition</span>
                <span className="mono">
                  {lastResult.previous_state || "—"} → {lastResult.next_state || "—"}
                </span>
              </div>
              <div>
                <span className="kv-label">Audit ID</span>
                <span className="mono">{lastResult.audit_event_id || "—"}</span>
              </div>
            </div>
            <p>{lastResult.message || lastResult.reason || "—"}</p>
          </div>
        </section>
      )}

      <section className="domain-card">
        <div className="domain-card-header">
          <h3>Action History</h3>
          <span className="muted">{history.length} recent</span>
        </div>
        <div className="panel-body">
          {history.length === 0 ? (
            <p className="empty-state">No operator actions recorded yet.</p>
          ) : (
            <div className="action-history-list">
              {history.map((entry, index) => (
                <article key={entry.event_id || index} className="action-history-item">
                  <div className="timeline-meta">
                    <span className="mono">{entry.timestamp || "—"}</span>
                    <span>{entry.action || "—"}</span>
                    <span className={entry.allowed ? "action-pill-allowed" : "action-pill-blocked"}>
                      {entry.allowed ? "allowed" : "blocked"}
                    </span>
                  </div>
                  <p className="mono action-history-transition">
                    {entry.previous_state || "—"} → {entry.next_state || "—"}
                  </p>
                  <p>
                    <strong>{entry.actor || "—"}</strong>
                    {entry.reason ? ` — ${entry.reason}` : ""}
                  </p>
                  {!entry.allowed && entry.blocked_reason && (
                    <p className="muted">{entry.blocked_reason}</p>
                  )}
                </article>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
