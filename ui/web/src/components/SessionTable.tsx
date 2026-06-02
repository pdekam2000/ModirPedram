import { SessionSummary } from "../api/client";
import { RuntimeStatusPollState } from "../hooks/useRuntimeStatusPoll";
import { RuntimeObservabilityChip } from "./RuntimeObservability";
import { formatScore, StatusBadge } from "./shared";

export type ArchiveFilter = "active" | "archived" | "all";

export type SessionFiltersState = {
  query: string;
  status: string;
  provider: string;
  risk: string;
  archive: ArchiveFilter;
};

type Props = {
  filters: SessionFiltersState;
  providers: string[];
  onChange: (next: SessionFiltersState) => void;
};

export function SessionFilters({ filters, providers, onChange }: Props) {
  return (
    <div className="filters-bar">
      <input
        className="filter-input"
        placeholder="Search session, brief, provider…"
        value={filters.query}
        onChange={(event) => onChange({ ...filters, query: event.target.value })}
      />
      <select
        className="filter-select"
        value={filters.archive}
        onChange={(event) =>
          onChange({ ...filters, archive: event.target.value as ArchiveFilter })
        }
      >
        <option value="active">Active sessions</option>
        <option value="archived">Archived sessions</option>
        <option value="all">All sessions</option>
      </select>
      <select
        className="filter-select"
        value={filters.status}
        onChange={(event) => onChange({ ...filters, status: event.target.value })}
      >
        <option value="">All statuses</option>
        {[...new Set(["SIMULATED", "PLANNED", "GOVERNED", "AWAITING_APPROVAL", "APPROVED_FOR_EXECUTION", "READY", "READY_WITH_WARNINGS", "NOT_READY", "QUEUED", "DEQUEUED", "DISPATCHED", "RUNNING", "COMPLETED", "EXPIRED", "EXECUTING", "FAILED", "BUDGET_BLOCKED", "CANCELLED"])].map(
          (status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ),
        )}
      </select>
      <select
        className="filter-select"
        value={filters.provider}
        onChange={(event) => onChange({ ...filters, provider: event.target.value })}
      >
        <option value="">All providers</option>
        {providers.map((provider) => (
          <option key={provider} value={provider}>
            {provider}
          </option>
        ))}
      </select>
      <select
        className="filter-select"
        value={filters.risk}
        onChange={(event) => onChange({ ...filters, risk: event.target.value })}
      >
        <option value="">All risk</option>
        <option value="blocked">Budget blocked</option>
        <option value="pending">Pending approval</option>
        <option value="low_confidence">Low confidence (&lt;50)</option>
      </select>
    </div>
  );
}

export function filterSessions(sessions: SessionSummary[], filters: SessionFiltersState): SessionSummary[] {
  const query = filters.query.trim().toLowerCase();

  return sessions.filter((session) => {
    if (filters.archive === "active" && session.archived) {
      return false;
    }
    if (filters.archive === "archived" && !session.archived) {
      return false;
    }
    if (filters.status && session.status !== filters.status) {
      return false;
    }
    if (filters.provider && session.provider !== filters.provider) {
      return false;
    }
    if (filters.risk === "blocked" && session.budget_state !== "blocked") {
      return false;
    }
    if (filters.risk === "pending" && session.approval_state !== "pending") {
      return false;
    }
    if (
      filters.risk === "low_confidence" &&
      !(session.execution_confidence !== null && session.execution_confidence < 50)
    ) {
      return false;
    }
    if (!query) {
      return true;
    }
    return [session.session_id, session.brief_id, session.provider]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
}

export function riskClass(session: SessionSummary): string {
  if (session.budget_state === "blocked") {
    return "risk-high";
  }
  if (session.approval_state === "pending") {
    return "risk-medium";
  }
  if (session.execution_confidence !== null && session.execution_confidence < 50) {
    return "risk-medium";
  }
  return "risk-low";
}

export function SessionTable({
  sessions,
  loading,
  openingId,
  runtimePollMap = {},
  onOpen,
}: {
  sessions: SessionSummary[];
  loading: boolean;
  openingId: string | null;
  runtimePollMap?: Record<string, RuntimeStatusPollState>;
  onOpen: (sessionId: string) => void;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Session ID</th>
            <th>Status</th>
            <th>Runtime</th>
            <th>Provider</th>
            <th>Story Quality</th>
            <th>Approval</th>
            <th>Budget</th>
            <th>Priority</th>
            <th>Confidence</th>
            <th>Created</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {loading && sessions.length === 0 ? (
            <tr>
              <td colSpan={11} className="empty">
                Loading sessions…
              </td>
            </tr>
          ) : sessions.length === 0 ? (
            <tr>
              <td colSpan={11} className="empty">
                No sessions match the current filters.
              </td>
            </tr>
          ) : (
            sessions.map((session) => (
              <tr
                key={session.session_id}
                className={`${riskClass(session)}${session.archived ? " session-archived" : ""}`}
              >
                <td className="mono">
                  {session.session_id}
                  {session.archived && <span className="archived-badge">Archived</span>}
                </td>
                <td>
                  <StatusBadge status={session.status} />
                </td>
                <td>
                  <RuntimeObservabilityChip status={runtimePollMap[session.session_id]?.status ?? null} />
                </td>
                <td>{session.provider}</td>
                <td>{formatScore(session.story_quality_score)}</td>
                <td>{session.approval_state}</td>
                <td>{session.budget_state}</td>
                <td>{session.priority_band}</td>
                <td>{formatScore(session.execution_confidence)}</td>
                <td>{session.archived ? session.archived_at || "—" : session.created_at}</td>
                <td>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => onOpen(session.session_id)}
                    disabled={openingId === session.session_id}
                  >
                    {openingId === session.session_id ? "Opening…" : "Open"}
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
