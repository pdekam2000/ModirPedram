import { RuntimeStatusPollState } from "../hooks/useRuntimeStatusPoll";
import { RuntimeStatusResponse } from "../api/client";
import { KeyValue, StatusBadge } from "./shared";
import {
  formatBytes,
  formatDurationSeconds,
  formatProviderMode,
  gateStatus,
  isTerminalRuntimeState,
  normalizeRuntimeState,
  resolveArtifacts,
  resolveValidationBlock,
  truncateHash,
} from "../utils/runtimeObservability";
import { resolveFailoverAdvisory } from "../utils/failoverAdvisory";
import { FailoverAdvisoryPanel } from "./FailoverAdvisoryPanel";
import { CategoryRuntimeSlotsPanel } from "./CategoryRuntimeSlotsPanel";
import { VoiceRuntimeObservabilityPanel } from "./VoiceRuntimeObservabilityPanel";
import { SubtitleRuntimeObservabilityPanel } from "./SubtitleRuntimeObservabilityPanel";
import { AssemblyRuntimeObservabilityPanel } from "./AssemblyRuntimeObservabilityPanel";

type Props = {
  status: RuntimeStatusResponse | null;
  pollState?: RuntimeStatusPollState;
  legacyPanel?: Record<string, unknown>;
  compact?: boolean;
  sessionId?: string | null;
  sessionContext?: {
    archived?: boolean;
    cancelRequested?: boolean;
    isLegacy?: boolean;
  };
  onVoiceApprovalSuccess?: () => Promise<void> | void;
  onAssemblyApprovalSuccess?: () => Promise<void> | void;
};

function readLegacyString(panel: Record<string, unknown> | undefined, key: string): string | null {
  const value = panel?.[key];
  if (value === null || value === undefined || value === "") {
    return null;
  }
  return String(value);
}

export function RuntimeObservabilityPanel({
  status,
  pollState,
  legacyPanel,
  compact = false,
  sessionId = null,
  sessionContext,
  onVoiceApprovalSuccess,
  onAssemblyApprovalSuccess,
}: Props) {
  const providerFamily =
    status?.provider_family ||
    readLegacyString(legacyPanel, "provider_resolved") ||
    null;
  const providerMode = status?.provider_execution_mode || readLegacyString(legacyPanel, "provider_mode");
  const providerResolved =
    status?.provider_resolved || readLegacyString(legacyPanel, "provider_resolved") || "—";
  const runtimePhase =
    status?.operations_phase ||
    status?.job?.phase ||
    status?.runtime_state ||
    readLegacyString(legacyPanel, "runtime_state") ||
    "—";
  const sessionState = status?.state || readLegacyString(legacyPanel, "runtime_state") || "—";
  const sessionStateNormalized = normalizeRuntimeState(
    status?.state || status?.runtime_state || readLegacyString(legacyPanel, "runtime_state"),
  );

  const heartbeat = status?.heartbeat;
  const job = status?.job;
  const stale =
    !isTerminalRuntimeState(sessionStateNormalized) &&
    Boolean(heartbeat?.stale || job?.stale);
  const heartbeatHealthy = status ? !stale : null;
  const elapsed =
    heartbeat?.elapsed_seconds ??
    job?.elapsed_seconds ??
    null;

  const preflight = (status?.preflight as Record<string, unknown> | undefined) ?? null;
  const preflightGate = gateStatus(
    typeof preflight?.passed === "boolean" ? preflight.passed : null,
  );

  const validation = resolveValidationBlock(status);
  const validationGate = gateStatus(
    typeof validation?.passed === "boolean" ? validation.passed : null,
  );

  const telemetry = (status?.cost_telemetry as Record<string, unknown> | undefined) ?? null;
  const durationSeconds =
    typeof telemetry?.duration_seconds === "number"
      ? telemetry.duration_seconds
      : typeof elapsed === "number"
        ? elapsed
        : null;
  const estimatedCredits =
    typeof telemetry?.estimated_credits === "number" ? telemetry.estimated_credits : null;

  const artifacts = resolveArtifacts(status);
  const failoverAdvisory = resolveFailoverAdvisory(status);

  return (
    <section className={`runtime-observability ${compact ? "runtime-observability-compact" : ""}`}>
      {stale && (
        <div className="runtime-stale-banner" role="status">
          Job may be stuck — heartbeat stale
          {heartbeat?.stale_reason || job?.stale_reason
            ? ` (${String(heartbeat?.stale_reason || job?.stale_reason)})`
            : ""}
        </div>
      )}

      {pollState?.polling && (
        <div className="runtime-live-indicator" aria-live="polite">
          <span className="runtime-live-dot" />
          Live · polling every 5s
        </div>
      )}

      {pollState?.error && <div className="runtime-poll-error">{pollState.error}</div>}

      <div className="kv-grid">
        <KeyValue label="Session state" value={<StatusBadge status={String(sessionState)} />} />
        <KeyValue label="Provider" value={providerResolved} />
        <KeyValue
          label="Provider · Mode"
          value={formatProviderMode(providerFamily, providerMode)}
        />
        <KeyValue label="Runtime phase" value={String(runtimePhase)} />
        <KeyValue
          label="Heartbeat"
          value={
            heartbeatHealthy === null ? (
              "—"
            ) : heartbeatHealthy ? (
              <span className="runtime-gate runtime-gate-pass">Healthy</span>
            ) : (
              <span className="runtime-gate runtime-gate-fail">Stale</span>
            )
          }
        />
        <KeyValue
          label="Last heartbeat"
          value={String(heartbeat?.heartbeat_at || job?.heartbeat_at || "—")}
        />
        <KeyValue label="Elapsed" value={formatDurationSeconds(durationSeconds)} />
        <KeyValue
          label="Preflight"
          value={<span className={preflightGate.className}>{preflightGate.label}</span>}
        />
        <KeyValue
          label="Artifact validation"
          value={<span className={validationGate.className}>{validationGate.label}</span>}
        />
        <KeyValue label="Duration" value={formatDurationSeconds(durationSeconds)} />
        <KeyValue
          label="Est. credits"
          value={estimatedCredits === null ? "—" : String(estimatedCredits)}
        />
        <KeyValue label="Dispatch ID" value={String(status?.dispatch_id || "—")} />
      </div>

      {!compact && preflightGate.label === "FAILED" && Array.isArray(preflight?.reject_reasons) && (
        <details className="runtime-detail-block" open>
          <summary>Preflight failure</summary>
          <ul className="runtime-reason-list">
            {(preflight.reject_reasons as string[]).map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </details>
      )}

      {!compact && validationGate.label === "FAILED" && Array.isArray(validation?.reject_reasons) && (
        <details className="runtime-detail-block" open>
          <summary>Validation failure</summary>
          <ul className="runtime-reason-list">
            {(validation.reject_reasons as string[]).map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </details>
      )}

      {failoverAdvisory && <FailoverAdvisoryPanel advisory={failoverAdvisory} compact={compact} />}

      {!compact && (
        <CategoryRuntimeSlotsPanel status={status} legacyPanel={legacyPanel} compact={compact} />
      )}

      {!compact && (
        <VoiceRuntimeObservabilityPanel
          status={status}
          legacyPanel={legacyPanel}
          compact={compact}
          sessionId={sessionId}
          sessionContext={sessionContext}
          onVoiceApprovalSuccess={onVoiceApprovalSuccess}
        />
      )}

      {!compact && (
        <SubtitleRuntimeObservabilityPanel
          status={status}
          legacyPanel={legacyPanel}
          compact={compact}
        />
      )}

      {!compact && (
        <AssemblyRuntimeObservabilityPanel
          status={status}
          legacyPanel={legacyPanel}
          compact={compact}
          sessionId={sessionId}
          sessionContext={sessionContext}
          onAssemblyApprovalSuccess={onAssemblyApprovalSuccess}
        />
      )}

      {!compact && artifacts.length > 0 && (
        <div className="runtime-artifacts">
          <h4>Clip artifacts</h4>
          <div className="runtime-artifact-list">
            {artifacts.map((artifact, index) => {
              const clipNumber = artifact.clip_number ?? index + 1;
              const validationStatus = String(artifact.validation_status || "—");
              return (
                <article key={String(artifact.artifact_id || index)} className="runtime-artifact-card">
                  <div className="runtime-artifact-head">
                    <strong>Clip {String(clipNumber)}</strong>
                    <span className={`runtime-gate runtime-gate-${validationStatus === "valid" ? "pass" : validationStatus === "invalid" ? "fail" : "unknown"}`}>
                      {validationStatus}
                    </span>
                  </div>
                  <div className="kv-grid kv-grid-tight">
                    <KeyValue label="Size" value={formatBytes(artifact.size_bytes as number | null | undefined)} />
                    <KeyValue label="Validated" value={String(artifact.validated_at || "—")} />
                    <KeyValue
                      label="SHA256"
                      value={
                        artifact.sha256 ? (
                          <span className="mono" title={String(artifact.sha256)}>
                            {truncateHash(String(artifact.sha256), 20)}
                          </span>
                        ) : (
                          "—"
                        )
                      }
                    />
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

export function RuntimeObservabilityChip({ status }: { status: RuntimeStatusResponse | null }) {
  if (!status) {
    return <span className="muted">—</span>;
  }
  const phase = status.operations_phase || status.job?.phase || status.runtime_state || status.state || "—";
  const sessionStateNormalized = normalizeRuntimeState(status.state || status.runtime_state);
  const stale =
    !isTerminalRuntimeState(sessionStateNormalized) &&
    Boolean(status.heartbeat?.stale || status.job?.stale);
  return (
    <span className="runtime-chip-wrap">
      <span className="runtime-chip">{phase}</span>
      {stale && <span className="runtime-chip-stale" title="Heartbeat stale">Stale</span>}
      {(status.job?.active || status.heartbeat?.elapsed_seconds != null) && !stale && (
        <span className="runtime-live-dot" aria-hidden="true" />
      )}
    </span>
  );
}
