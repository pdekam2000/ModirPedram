import { RuntimeStatusResponse } from "../api/client";
import { KeyValue } from "./shared";
import { resolveAssemblyRuntimeObservability, ASSEMBLY_EXPECTED_OUTPUT_LABEL } from "../utils/assemblyRuntimeObservability";
import { AssemblyApprovalControlsPanel } from "./AssemblyApprovalControlsPanel";
import { AssemblySessionContext } from "../utils/assemblyApprovalEligibility";

type Props = {
  status: RuntimeStatusResponse | null;
  legacyPanel?: Record<string, unknown>;
  compact?: boolean;
  sessionId?: string | null;
  sessionContext?: AssemblySessionContext;
  onAssemblyApprovalSuccess?: () => Promise<void> | void;
};

export function AssemblyRuntimeObservabilityPanel({
  status,
  legacyPanel,
  compact = false,
  sessionId = null,
  sessionContext,
  onAssemblyApprovalSuccess,
}: Props) {
  const assembly = resolveAssemblyRuntimeObservability(status, legacyPanel);

  return (
    <section
      className={`assembly-runtime-observability ${compact ? "assembly-runtime-observability-compact" : ""}`}
    >
      <h4>Assembly runtime</h4>
      <p className="muted assembly-runtime-note">{assembly.safetyNote}</p>

      <div className="assembly-runtime-head">
        <strong>{assembly.category_key}</strong>
        <span className={assembly.statusClassName}>{assembly.statusLabel}</span>
      </div>

      <div className="kv-grid kv-grid-tight">
        <KeyValue label="Status" value={assembly.status} />
        <KeyValue label="Provider" value={assembly.provider} />
        <KeyValue label="Validation status" value={assembly.validationStatus} />
        {!compact && (
          <>
            <KeyValue label="Assembly mode" value={assembly.assemblyMode} />
            <KeyValue label="Subtitle mode" value={assembly.subtitleMode} />
            <KeyValue label="Expected output" value={assembly.expectedOutput} />
            <KeyValue label="Output created" value={assembly.outputCreated} />
            <KeyValue label="Real assembly executed" value={assembly.realAssemblyExecuted} />
            <KeyValue label="Input summary" value={assembly.inputSummary} />
            <KeyValue label="Output summary" value={assembly.outputSummary} />
            <KeyValue label="Started" value={assembly.startedAt} />
            <KeyValue label="Completed" value={assembly.completedAt} />
            <KeyValue label="Duration" value={assembly.durationSeconds} />
          </>
        )}
      </div>

      {!compact && assembly.showApprovalSection && (
        <div className="assembly-approval-gate-section">
          <h5>Assembly approval gate</h5>
          <div className="kv-grid kv-grid-tight">
            <KeyValue label="Approval required" value={assembly.approvalRequired} />
            <KeyValue label="Approval state" value={assembly.approvalState} />
            <KeyValue label="Assembly eligible" value={assembly.assemblyEligible} />
            <KeyValue label="Expires at" value={assembly.approvalExpiresAt} />
            <KeyValue label="Est. runtime" value={assembly.estimatedRuntimeSeconds} />
            <KeyValue label="Est. output size" value={assembly.estimatedOutputSize} />
            <KeyValue label="Est. disk usage" value={assembly.estimatedDiskUsage} />
          </div>
          {assembly.assemblyBlockedReasons.length > 0 && (
            <div className="assembly-approval-blocked">
              <strong>Blocked reasons</strong>
              <ul className="runtime-reason-list">
                {assembly.assemblyBlockedReasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          )}
          {assembly.approvalGloballyDisabledNote && (
            <p className="muted assembly-runtime-note">{assembly.approvalGloballyDisabledNote}</p>
          )}
          <AssemblyApprovalControlsPanel
            sessionId={sessionId}
            assembly={assembly}
            sessionContext={sessionContext}
            onAfterAction={onAssemblyApprovalSuccess}
          />
        </div>
      )}

      {!compact && assembly.showPlannedSteps && (
        <div className="assembly-planned-steps-section">
          <h5>Planned steps (preview only — not executed)</h5>
          {assembly.plannedSteps.length > 0 ? (
            <ol className="assembly-planned-steps-list">
              {assembly.plannedSteps.map((step) => (
                <li key={`${step.step}-${step.name}`} className="assembly-planned-step-row">
                  <strong>
                    {step.step}. {step.name}
                  </strong>
                  <span className="muted"> — {step.action}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted assembly-runtime-note">No planned steps yet.</p>
          )}
        </div>
      )}

      {!compact && assembly.showExpectedOutput && (
        <div className="assembly-expected-output-section">
          <h5>Expected output (not generated)</h5>
          <article className="assembly-expected-output-card">
            <div className="assembly-expected-output-head">
              <strong>{assembly.expectedOutput}</strong>
              <span className="assembly-expected-output-badge">{ASSEMBLY_EXPECTED_OUTPUT_LABEL}</span>
            </div>
            <div className="kv-grid kv-grid-tight">
              <KeyValue
                label="Path"
                value={
                  assembly.expectedOutputPath !== "—" ? (
                    <span className="mono" title={assembly.expectedOutputPath}>
                      {assembly.expectedOutputPath}
                    </span>
                  ) : (
                    "—"
                  )
                }
              />
              <KeyValue
                label="Status"
                value={assembly.isGeneratedOutput ? "Generated" : "Not generated"}
              />
            </div>
            {!assembly.isGeneratedOutput && assembly.noOutputNote && (
              <p className="muted assembly-runtime-note">{assembly.noOutputNote}</p>
            )}
          </article>
        </div>
      )}

      {!compact && assembly.warnings.length > 0 && (
        <div className="assembly-warnings-block">
          <strong>Warnings</strong>
          <ul className="runtime-reason-list">
            {assembly.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {!compact && assembly.errors.length > 0 && (
        <div className="assembly-error-block" role="status">
          <strong>Errors</strong>
          <ul className="runtime-reason-list">
            {assembly.errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      )}

      {!compact && assembly.errorCode !== "—" && assembly.errors.length === 0 && (
        <div className="assembly-error-block" role="status">
          <strong>Error</strong>: {assembly.errorCode}
          {assembly.errorMessage !== "—" ? ` — ${assembly.errorMessage}` : ""}
        </div>
      )}
    </section>
  );
}
