import { KeyValue } from "./shared";
import { FailoverAdvisory, formatBooleanFlag } from "../utils/failoverAdvisory";

type Props = {
  advisory: FailoverAdvisory;
  compact?: boolean;
};

function readRankedCandidates(advisory: FailoverAdvisory): string {
  const ranked = advisory.provider_selection?.ranked_candidates;
  if (!Array.isArray(ranked) || ranked.length === 0) {
    return "—";
  }
  return ranked.join(", ");
}

function readSelectionWarnings(advisory: FailoverAdvisory): string[] {
  const warnings = advisory.provider_selection?.warnings;
  return Array.isArray(warnings) ? warnings.filter((item) => String(item).trim()) : [];
}

export function FailoverAdvisoryPanel({ advisory, compact = false }: Props) {
  const selectionWarnings = readSelectionWarnings(advisory);
  const planWarnings = Array.isArray(advisory.failover_plan?.warnings)
    ? advisory.failover_plan!.warnings!.filter((item) => String(item).trim())
    : [];
  const nextProvider =
    advisory.preferred_next_provider ||
    advisory.provider_selection?.selected_provider ||
    null;

  return (
    <div className={`runtime-failover-advisory ${compact ? "runtime-failover-advisory-compact" : ""}`}>
      <h4>Failover Advisory</h4>
      <p className="runtime-advisory-note muted">Advisory only — no automatic failover</p>
      <div className="kv-grid kv-grid-tight">
        <KeyValue label="Recommended" value={formatBooleanFlag(advisory.failover_recommended)} />
        <KeyValue label="Reason" value={String(advisory.reason || "—")} />
        <KeyValue label="Current provider" value={String(advisory.current_provider || "—")} />
        <KeyValue label="Next provider" value={String(nextProvider || "—")} />
        <KeyValue label="Failover allowed" value={formatBooleanFlag(advisory.failover_allowed)} />
        {advisory.blocked_reason ? (
          <KeyValue label="Blocked reason" value={String(advisory.blocked_reason)} />
        ) : null}
        <KeyValue label="Capability match" value={formatBooleanFlag(advisory.capability_match)} />
        <KeyValue label="Cost warning" value={String(advisory.cost_warning || "—")} />
        <KeyValue
          label="Partial artifacts"
          value={
            advisory.partial_artifacts_present
              ? String(advisory.partial_artifact_count ?? "—")
              : "—"
          }
        />
        <KeyValue
          label="Partial reusable"
          value={formatBooleanFlag(advisory.partial_artifacts_safe_to_reuse)}
        />
      </div>

      {!compact && advisory.provider_selection && (
        <details className="runtime-detail-block">
          <summary>Provider selection (11D)</summary>
          <div className="kv-grid kv-grid-tight">
            <KeyValue
              label="Selected"
              value={String(advisory.provider_selection.selected_provider || "—")}
            />
            <KeyValue label="Ranked candidates" value={readRankedCandidates(advisory)} />
          </div>
          {selectionWarnings.length > 0 && (
            <ul className="runtime-reason-list">
              {selectionWarnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
        </details>
      )}

      {!compact && advisory.failover_plan?.chain && advisory.failover_plan.chain.length > 0 && (
        <details className="runtime-detail-block">
          <summary>Failover chain (11C)</summary>
          <p className="mono">{advisory.failover_plan.chain.join(" → ")}</p>
          {planWarnings.length > 0 && (
            <ul className="runtime-reason-list">
              {planWarnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
        </details>
      )}
    </div>
  );
}
