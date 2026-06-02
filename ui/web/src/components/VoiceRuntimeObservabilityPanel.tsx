import { RuntimeStatusResponse } from "../api/client";
import { KeyValue } from "./shared";
import { resolveVoiceRuntimeObservability } from "../utils/categoryRuntimeShell";
import { VoiceApprovalControlsPanel } from "./VoiceApprovalControlsPanel";
import { VoiceSessionContext } from "../utils/voiceApprovalEligibility";

type Props = {
  status: RuntimeStatusResponse | null;
  legacyPanel?: Record<string, unknown>;
  compact?: boolean;
  sessionId?: string | null;
  sessionContext?: VoiceSessionContext;
  onVoiceApprovalSuccess?: () => Promise<void> | void;
};

export function VoiceRuntimeObservabilityPanel({
  status,
  legacyPanel,
  compact = false,
  sessionId = null,
  sessionContext,
  onVoiceApprovalSuccess,
}: Props) {
  const voice = resolveVoiceRuntimeObservability(status, legacyPanel);

  return (
    <section className={`voice-runtime-observability ${compact ? "voice-runtime-observability-compact" : ""}`}>
      <h4>Voice runtime</h4>
      <p className="muted voice-runtime-note">
        Read-only dry-run observability — no live TTS execution in this phase.
      </p>
      <div className="voice-runtime-head">
        <strong>voice_generation</strong>
        <span className={voice.statusClassName}>{voice.statusLabel}</span>
      </div>
      <div className="kv-grid kv-grid-tight">
        <KeyValue label="Status" value={voice.status} />
        <KeyValue label="Provider" value={voice.provider} />
        <KeyValue label="Executed" value={voice.executed} />
        <KeyValue label="Dry run" value={voice.dryRun} />
        <KeyValue label="Preflight status" value={voice.preflightStatus} />
        <KeyValue label="Preflight code" value={voice.preflightCode} />
        {!compact && (
          <>
            <KeyValue label="Segment count" value={voice.segmentCount} />
            <KeyValue label="Total text length" value={voice.totalTextLength} />
            <KeyValue label="Error code" value={voice.errorCode} />
            <KeyValue label="Runtime notes" value={voice.runtimeNotes} />
          </>
        )}
      </div>
      <div className="voice-approval-gate-section">
        <h5>Voice approval gate</h5>
        <p className="muted voice-runtime-note">{voice.approvalGateNote}</p>
        <div className="kv-grid kv-grid-tight">
          <KeyValue label="Approval required" value={voice.approvalRequired} />
          <KeyValue label="Approval state" value={voice.approvalState} />
          <KeyValue label="Est. characters" value={voice.estimatedCharacters} />
          <KeyValue label="Est. segments" value={voice.estimatedSegments} />
          <KeyValue label="Est. voice cost" value={voice.estimatedVoiceCost} />
          <KeyValue label="Approval expires" value={voice.approvalExpiresAt} />
          <KeyValue label="Live TTS eligible" value={voice.liveTtsEligible} />
          <KeyValue label="Blocked because" value={voice.blockedReasons} />
        </div>
      </div>
      {!compact && (
        <VoiceApprovalControlsPanel
          sessionId={sessionId}
          voice={voice}
          sessionContext={sessionContext}
          onSuccess={onVoiceApprovalSuccess}
        />
      )}
    </section>
  );
}
