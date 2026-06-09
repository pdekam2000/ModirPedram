import { useCallback, useEffect, useMemo, useState } from "react";
import {
  API_BASE_URL,
  fetchSession,
  fetchSessions,
  fetchSessionSummary,
  SessionDetail,
  SessionOverview,
  SessionSummary,
} from "../api/client";
import { OverviewCards } from "../components/OverviewCards";
import { RuntimeObservabilityPanel } from "../components/RuntimeObservability";
import { SessionDrawer } from "../components/SessionDrawer";
import {
  filterSessions,
  SessionFilters,
  SessionFiltersState,
  SessionTable,
} from "../components/SessionTable";
import { useRuntimeStatusPoll, useRuntimeStatusPollMap } from "../hooks/useRuntimeStatusPoll";
import { RunwayBrowserPanel } from "../components/RunwayBrowserPanel";
import { UatRuntimePage } from "./UatRuntimePage";
import { RunwayLiveSmokePage } from "./RunwayLiveSmokePage";
import { ContentBrainTestStudioPage } from "./ContentBrainTestStudioPage";
import { TopicUniverseStudioPage } from "./TopicUniverseStudioPage";
import { shouldPollRuntimeStatus } from "../utils/runtimeObservability";

type ExecutionCenterTab = "sessions" | "uat" | "runway_smoke" | "content_brain_test" | "topic_universe";

export function ExecutionCenterPage() {
  const [centerTab, setCenterTab] = useState<ExecutionCenterTab>("sessions");
  const [overview, setOverview] = useState<SessionOverview | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<SessionDetail | null>(null);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [drawerTab, setDrawerTab] = useState("overview");
  const [runtimeRefreshKey, setRuntimeRefreshKey] = useState(0);
  const [filters, setFilters] = useState<SessionFiltersState>({
    query: "",
    status: "",
    provider: "",
    risk: "",
    archive: "active",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summary, list] = await Promise.all([fetchSessionSummary(), fetchSessions("all")]);
      setOverview(summary);
      setSessions(list.sessions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load execution center data");
      setOverview(null);
      setSessions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const providers = useMemo(
    () => [...new Set(sessions.map((session) => session.provider).filter(Boolean))],
    [sessions],
  );

  const filteredSessions = useMemo(
    () => filterSessions(sessions, filters),
    [sessions, filters],
  );

  const activeRuntimeSessionIds = useMemo(
    () =>
      sessions
        .filter((session) => !session.archived && shouldPollRuntimeStatus(session.status))
        .map((session) => session.session_id),
    [sessions],
  );

  const runtimePollMap = useRuntimeStatusPollMap(activeRuntimeSessionIds);

  const runtimeOverview = useMemo(() => {
    const staleCount = Object.values(runtimePollMap).filter(
      (entry) => entry.status?.heartbeat?.stale || entry.status?.job?.stale,
    ).length;
    const activeCount = Object.values(runtimePollMap).filter((entry) => entry.polling).length;
    return {
      runtime_active_count: activeCount || overview?.runtime_active_count || 0,
      runtime_stale_count: staleCount,
    };
  }, [runtimePollMap, overview?.runtime_active_count]);

  const selectedRuntimePoll = useRuntimeStatusPoll(
    selected?.session_id ?? null,
    Boolean(selected),
    runtimeRefreshKey,
  );

  const refreshAfterAction = useCallback(async () => {
    const [summary, list] = await Promise.all([fetchSessionSummary(), fetchSessions("all")]);
    setOverview(summary);
    setSessions(list.sessions);
    if (selected) {
      const detail = await fetchSession(selected.session_id);
      setSelected(detail);
    }
    setRuntimeRefreshKey((value) => value + 1);
  }, [selected]);

  async function openSession(sessionId: string) {
    setOpeningId(sessionId);
    setError(null);
    try {
      const detail = await fetchSession(sessionId);
      setSelected(detail);
      setDrawerTab("overview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open session");
    } finally {
      setOpeningId(null);
    }
  }

  return (
    <div className={`execution-layout ${centerTab !== "sessions" ? "execution-layout-uat" : ""}`}>
      <section className="execution-main">
        <header className="header">
          <div>
            <p className="eyebrow">ModirAgent OS · Execution Center</p>
            <h1>Execution Center</h1>
            <p className="subtitle">
              {centerTab === "uat"
                ? "Supervised user acceptance test workspace"
                : centerTab === "runway_smoke"
                  ? "Phase H live smoke with Runtime Studio approval buttons"
                  : centerTab === "content_brain_test"
                    ? "Content Brain intelligence pipeline — no Runway credits"
                    : centerTab === "topic_universe"
                      ? "Expand broad topics into SEO title banks before video planning"
                      : "Session dashboard with runtime observability and operator actions"}
            </p>
          </div>
          {centerTab === "sessions" && (
            <div className="header-meta">
              <span className="pill">API: {API_BASE_URL}</span>
              <button type="button" onClick={() => void load()} disabled={loading}>
                {loading ? "Refreshing…" : "Refresh"}
              </button>
            </div>
          )}
        </header>

        <div className="uat-center-tabs execution-center-tabs">
          <button
            type="button"
            className={`uat-center-tab ${centerTab === "sessions" ? "active" : ""}`}
            onClick={() => setCenterTab("sessions")}
          >
            Sessions
          </button>
          <button
            type="button"
            className={`uat-center-tab ${centerTab === "uat" ? "active" : ""}`}
            onClick={() => setCenterTab("uat")}
          >
            UAT Runtime
          </button>
          <button
            type="button"
            className={`uat-center-tab ${centerTab === "content_brain_test" ? "active" : ""}`}
            onClick={() => setCenterTab("content_brain_test")}
          >
            Content Brain Test Studio
          </button>
          <button
            type="button"
            className={`uat-center-tab ${centerTab === "topic_universe" ? "active" : ""}`}
            onClick={() => setCenterTab("topic_universe")}
          >
            Topic Universe Studio
          </button>
          <button
            type="button"
            className={`uat-center-tab ${centerTab === "runway_smoke" ? "active" : ""}`}
            onClick={() => setCenterTab("runway_smoke")}
          >
            Runway Live Smoke
          </button>
        </div>

        <RunwayBrowserPanel compact={centerTab !== "sessions"} />

        {centerTab === "uat" ? (
          <UatRuntimePage />
        ) : centerTab === "runway_smoke" ? (
          <RunwayLiveSmokePage />
        ) : centerTab === "content_brain_test" ? (
          <ContentBrainTestStudioPage />
        ) : centerTab === "topic_universe" ? (
          <TopicUniverseStudioPage />
        ) : (
          <>
            {error && <div className="error-banner">{error}</div>}

            <OverviewCards overview={overview} loading={loading} runtimeOverview={runtimeOverview} />

            {activeRuntimeSessionIds.length > 0 && (
              <section className="card runtime-active-card">
                <div className="card-header">
                  <h2>Active Runtime Jobs</h2>
                  <span className="muted">{activeRuntimeSessionIds.length} polling</span>
                </div>
                <div className="runtime-active-list">
                  {activeRuntimeSessionIds.map((sessionId) => (
                    <article key={sessionId} className="runtime-active-item">
                      <div className="runtime-active-head">
                        <button type="button" className="link-button mono" onClick={() => void openSession(sessionId)}>
                          {sessionId}
                        </button>
                        {runtimePollMap[sessionId]?.polling && <span className="runtime-live-dot" />}
                      </div>
                      <RuntimeObservabilityPanel
                        compact
                        status={runtimePollMap[sessionId]?.status ?? null}
                        pollState={runtimePollMap[sessionId]}
                      />
                    </article>
                  ))}
                </div>
              </section>
            )}

            <section className="card table-card">
              <div className="card-header">
                <h2>Execution Sessions</h2>
                <span className="muted">
                  {filteredSessions.length} shown · {sessions.length} total
                </span>
              </div>
              <SessionFilters filters={filters} providers={providers} onChange={setFilters} />
              <SessionTable
                sessions={filteredSessions}
                loading={loading}
                openingId={openingId}
                runtimePollMap={runtimePollMap}
                onOpen={(sessionId) => void openSession(sessionId)}
              />
            </section>
          </>
        )}
      </section>

      {centerTab === "sessions" && (
        <SessionDrawer
          detail={selected}
          onClose={() => setSelected(null)}
          tab={drawerTab}
          onTabChange={setDrawerTab}
          runtimePoll={selectedRuntimePoll}
          onAfterAction={() => refreshAfterAction()}
        />
      )}
    </div>
  );
}
