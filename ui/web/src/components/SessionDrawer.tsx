import { useState } from "react";
import { SessionActionType, SessionDetail } from "../api/client";
import { useSessionActions } from "../hooks/useSessionActions";
import { RuntimeStatusPollState } from "../hooks/useRuntimeStatusPoll";
import { parseActionError, ACTION_META } from "../utils/sessionActions";
import { ConfirmActionDialog } from "./ConfirmActionDialog";
import { RuntimeObservabilityPanel } from "./RuntimeObservability";
import { SessionActionBar } from "./SessionActionBar";
import { SessionActionsPanel } from "./SessionActionsPanel";
import { useToast } from "./ToastProvider";
import {
  CollapsibleJson,
  formatScore,
  KeyValue,
  PanelCard,
  renderExtraData,
  StatusBadge,
} from "./shared";

type Props = {
  detail: SessionDetail | null;
  onClose: () => void;
  tab: string;
  onTabChange: (tab: string) => void;
  runtimePoll?: RuntimeStatusPollState;
  onAfterAction?: () => Promise<void> | void;
};

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "actions", label: "Actions" },
  { id: "timeline", label: "Timeline" },
  { id: "simulation", label: "Simulation" },
  { id: "json", label: "Raw JSON" },
];

export function SessionDrawer({
  detail,
  onClose,
  tab,
  onTabChange,
  runtimePoll,
  onAfterAction,
}: Props) {
  const { showToast } = useToast();
  const [pendingAction, setPendingAction] = useState<SessionActionType | null>(null);

  const {
    eligibility,
    loading: eligibilityLoading,
    acting,
    error: eligibilityError,
    lastResult,
    executeAction,
  } = useSessionActions(detail?.session_id ?? null);

  if (!detail) {
    return null;
  }

  const sq = detail.story_quality_panel.data;
  const ap = detail.approval_panel.data;
  const bu = detail.budget_panel.data;
  const pr = detail.priority_panel.data;
  const ps = detail.provider_selection_panel.data;
  const rd = detail.readiness_panel.data;
  const qu = detail.queue_panel.data;
  const rt = detail.provider_runtime_panel.data;
  const readinessDecision =
    detail.execution_readiness?.decision ?? (rd.decision as string | undefined) ?? "—";
  const queueState =
    (detail.queue_item?.queue_state as string | undefined) ??
    (qu.queue_state as string | undefined) ??
    "—";
  const runtimeState =
    (detail.execution_runtime?.state as string | undefined) ??
    (rt.runtime_state as string | undefined) ??
    "—";

  const currentState = eligibility?.current_state || detail.status || "—";
  const opsControl =
    detail.session?.operations_control && typeof detail.session.operations_control === "object"
      ? (detail.session.operations_control as Record<string, unknown>)
      : {};
  const isArchived = Boolean(detail.archived ?? opsControl.archived);
  const archivedAt = detail.archived_at ?? (opsControl.archived_at as string | undefined);
  const archivedBy = detail.archived_by ?? (opsControl.archived_by as string | undefined);
  const archiveReason = detail.archive_reason ?? (opsControl.archive_reason as string | undefined);

  function openActionDialog(action: SessionActionType) {
    setPendingAction(action);
  }

  async function handleConfirm(reason: string) {
    if (!pendingAction) {
      return;
    }
    try {
      const result = await executeAction(pendingAction, reason);
      showToast("success", result?.message || `${ACTION_META[pendingAction].label} completed`);
      await onAfterAction?.();
    } catch (err) {
      showToast("error", parseActionError(err));
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <aside className="session-drawer">
      <div className="drawer-header">
        <div className="drawer-header-main">
          <p className="eyebrow">Session Detail</p>
          <h2 className="mono">{detail.session_id}</h2>
          <div className="drawer-sub">
            <StatusBadge status={detail.status} />
            <span className="muted">{detail.created_at}</span>
            {readinessDecision !== "—" && (
              <span className={`status status-${readinessDecision.toLowerCase()}`}>{readinessDecision}</span>
            )}
            {queueState !== "—" && queueState !== readinessDecision && (
              <span className={`status status-${queueState.toLowerCase()}`}>{queueState}</span>
            )}
            {runtimeState !== "—" && runtimeState !== queueState && runtimeState !== readinessDecision && (
              <span className={`status status-${runtimeState.toLowerCase()}`}>{runtimeState}</span>
            )}
            {isArchived && <span className="archived-badge">Archived</span>}
          </div>
          {(detail.session_schema_version || detail.session_uuid) && (
            <div className="session-identity">
              {detail.session_schema_version && (
                <KeyValue label="Schema" value={detail.session_schema_version} />
              )}
              {detail.session_uuid && (
                <KeyValue label="UUID" value={<span className="mono">{detail.session_uuid}</span>} />
              )}
              {detail.source_session_uuid != null && (
                <KeyValue
                  label="Source UUID"
                  value={
                    detail.source_session_uuid ? (
                      <span className="mono">{detail.source_session_uuid}</span>
                    ) : (
                      "— (original session)"
                    )
                  }
                />
              )}
            </div>
          )}
          <SessionActionBar
            eligibility={eligibility}
            loading={eligibilityLoading}
            acting={acting}
            onActionClick={openActionDialog}
          />
        </div>
        <button type="button" className="link-button" onClick={onClose}>
          Close
        </button>
      </div>

      <div className="drawer-tabs">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            className={tab === item.id ? "tab active" : "tab"}
            onClick={() => onTabChange(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="drawer-content">
        {tab === "overview" && (
          <div className="panel-stack">
            {isArchived && (
              <PanelCard title="Archive" panel={{ status: "available", completeness: 1, warnings: [], metadata: {}, data: {} }}>
                <div className="kv-grid">
                  <KeyValue label="Archived" value="Yes" />
                  <KeyValue label="Archived At" value={archivedAt || "—"} />
                  <KeyValue label="Archived By" value={archivedBy || "—"} />
                  <KeyValue label="Archive Reason" value={archiveReason || "—"} />
                </div>
              </PanelCard>
            )}

            <PanelCard title="Story Quality" panel={detail.story_quality_panel}>
              <div className="kv-grid">
                <KeyValue label="Score" value={formatScore(sq.score as number | null)} />
                <KeyValue label="Decision" value={String(sq.decision ?? "—")} />
                <KeyValue label="Cost risk" value={formatScore(sq.cost_risk_score as number | null)} />
              </div>
              {renderExtraData(sq, ["score", "decision", "critical_failures", "warnings", "cost_risk_score", "raw"])}
            </PanelCard>

            <PanelCard title="Approval" panel={detail.approval_panel}>
              <div className="kv-grid">
                <KeyValue
                  label="Governance"
                  value={String((ap.decision as Record<string, unknown> | null)?.status ?? ap.approval_state ?? "—")}
                />
                <KeyValue label="Summary" value={String(ap.approval_state ?? "—")} />
                <KeyValue label="Credits" value={formatScore(ap.estimated_credits as number | null)} />
                <KeyValue label="Runtime (min)" value={formatScore(ap.estimated_runtime_minutes as number | null)} />
                <KeyValue label="Provider" value={String(ap.provider ?? "—")} />
              </div>
              {renderExtraData(ap, ["approval_state", "estimated_credits", "estimated_runtime_minutes", "provider", "decision", "request"])}
            </PanelCard>

            <PanelCard title="Budget" panel={detail.budget_panel}>
              <div className="kv-grid">
                <KeyValue
                  label="Governance"
                  value={String((bu.decision as Record<string, unknown> | null)?.budget_status ?? bu.budget_status ?? "—")}
                />
                <KeyValue label="State" value={String(bu.budget_state ?? "—")} />
                <KeyValue label="Allowed" value={bu.budget_allowed === undefined ? "—" : String(bu.budget_allowed)} />
                <KeyValue label="Estimated cost" value={formatScore(bu.estimated_cost as number | null)} />
              </div>
              {renderExtraData(bu, ["budget_state", "budget_status", "budget_allowed", "estimated_cost", "remaining_budget_after_run", "budget_block_reason", "decision"])}
            </PanelCard>

            <PanelCard title="Priority" panel={detail.priority_panel}>
              <div className="kv-grid">
                <KeyValue label="Band" value={String(pr.priority_band ?? "—")} />
                <KeyValue label="Score" value={formatScore(pr.priority_score as number | null)} />
                <KeyValue label="Queue position" value={String(pr.queue_position ?? "—")} />
              </div>
              {renderExtraData(pr, ["priority_band", "priority_score", "queue_position", "decision"])}
            </PanelCard>

            <PanelCard title="Provider Selection" panel={detail.provider_selection_panel}>
              <div className="kv-grid">
                <KeyValue label="Recommended" value={String(ps.recommended_provider ?? "—")} />
                <KeyValue label="Confidence" value={formatScore(ps.execution_confidence_score as number | null)} />
                <KeyValue label="Band" value={String(ps.confidence_band ?? "—")} />
                <KeyValue label="Retry risk" value={String(ps.expected_retry_risk ?? "—")} />
              </div>
              {renderExtraData(ps, ["recommended_provider", "alternative_providers", "execution_confidence_score", "confidence_band", "expected_retry_risk", "selection", "confidence"])}
            </PanelCard>

            <PanelCard title="Execution Readiness" panel={detail.readiness_panel}>
              <div className="kv-grid">
                <KeyValue label="Decision" value={String(readinessDecision)} />
                <KeyValue label="Score" value={formatScore(rd.readiness_score as number | null)} />
                <KeyValue
                  label="Failures"
                  value={Array.isArray(rd.readiness_failures) && rd.readiness_failures.length > 0 ? String(rd.readiness_failures.length) : "0"}
                />
                <KeyValue
                  label="Warnings"
                  value={Array.isArray(rd.readiness_warnings) && rd.readiness_warnings.length > 0 ? String(rd.readiness_warnings.length) : "0"}
                />
              </div>
              {renderExtraData(rd, ["decision", "readiness_score", "readiness_failures", "readiness_warnings", "readiness"])}
            </PanelCard>

            <PanelCard title="Execution Queue" panel={detail.queue_panel}>
              <div className="kv-grid">
                <KeyValue label="Queue state" value={String(queueState)} />
                <KeyValue label="Position" value={String(qu.queue_position ?? "—")} />
                <KeyValue label="Item ID" value={String(qu.queue_item_id ?? "—")} />
                <KeyValue label="Enqueued" value={String(qu.enqueued_at ?? "—")} />
                <KeyValue label="Expires" value={String(qu.expires_at ?? "—")} />
                <KeyValue
                  label="Fingerprint"
                  value={
                    qu.queue_fingerprint ? (
                      <span className="mono truncate">{String(qu.queue_fingerprint).slice(0, 24)}…</span>
                    ) : (
                      "—"
                    )
                  }
                />
              </div>
              {renderExtraData(qu, ["queue_state", "queue_position", "queue_item_id", "enqueued_at", "expires_at", "queue_fingerprint", "queue_item"])}
            </PanelCard>

            <section className="domain-card">
              <div className="domain-card-header">
                <div>
                  <h3>Provider Runtime</h3>
                  <span className={detail.provider_runtime_panel.status === "missing" ? "panel-status panel-status-missing" : "panel-status panel-status-available"}>
                    {detail.provider_runtime_panel.status}
                  </span>
                </div>
              </div>
              <div className="panel-body">
                <RuntimeObservabilityPanel
                  status={runtimePoll?.status ?? null}
                  pollState={runtimePoll}
                  legacyPanel={rt}
                  sessionId={detail.session_id}
                  sessionContext={{
                    archived: isArchived,
                    cancelRequested: Boolean(opsControl.cancel_requested),
                    isLegacy: !detail.session_schema_version && !detail.execution_runtime,
                  }}
                  onVoiceApprovalSuccess={onAfterAction}
                  onAssemblyApprovalSuccess={onAfterAction}
                />
                <div className="kv-grid runtime-legacy-grid">
                  <KeyValue label="Runtime state" value={String(runtimeState)} />
                  <KeyValue label="Category" value={String(rt.provider_category ?? "—")} />
                  <KeyValue label="Dispatched" value={String(rt.dispatched_at ?? "—")} />
                  <KeyValue label="Completed" value={String(rt.completed_at ?? "—")} />
                  <KeyValue label="Clip artifacts" value={String(rt.clip_artifact_count ?? "—")} />
                </div>
                {renderExtraData(rt, ["runtime_state", "provider_resolved", "provider_category", "provider_mode", "dispatch_id", "dispatched_at", "running_at", "completed_at", "clip_artifact_count", "video_generation_state", "failure", "execution_runtime"])}
              </div>
            </section>
          </div>
        )}

        {tab === "actions" && (
          <SessionActionsPanel
            detail={detail}
            eligibility={eligibility}
            loading={eligibilityLoading}
            error={eligibilityError}
            lastResult={lastResult}
            onActionClick={openActionDialog}
          />
        )}

        {tab === "timeline" && (
          <div className="timeline-list">
            {detail.timeline.length === 0 ? (
              <p className="empty-state">No timeline events recorded.</p>
            ) : (
              detail.timeline.map((event, index) => (
                <article key={`${event.timestamp}-${index}`} className="timeline-item">
                  <div className="timeline-meta">
                    <span className="mono">{event.timestamp}</span>
                    <span>{event.event_type}</span>
                    <StatusBadge status={event.status || "UNKNOWN"} />
                  </div>
                  <strong>{event.label}</strong>
                  <p>{event.message}</p>
                </article>
              ))
            )}
          </div>
        )}

        {tab === "simulation" && (
          <PanelCard title="Simulation Report" panel={detail.simulation_panel}>
            <CollapsibleJson value={detail.simulation_panel.data.report ?? detail.simulation_report} label="Simulation payload" />
          </PanelCard>
        )}

        {tab === "json" && <CollapsibleJson value={detail.session} label="Full session JSON" />}
      </div>

      <ConfirmActionDialog
        open={pendingAction !== null}
        action={pendingAction}
        currentState={currentState}
        loading={acting}
        onConfirm={(reason) => void handleConfirm(reason)}
        onCancel={() => setPendingAction(null)}
      />
    </aside>
  );
}
