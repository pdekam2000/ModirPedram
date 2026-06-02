import { useState } from "react";
import {
  parseVoiceApprovalError,
  postVoiceApprove,
  postVoiceExpire,
  postVoiceReject,
  postVoiceResetApproval,
  VoiceApprovalActionResponse,
  VoiceApprovalSafetyError,
} from "../api/voiceApprovalClient";
import { VoiceRuntimeObservability } from "../utils/categoryRuntimeShell";
import {
  evaluateVoiceApprovalEligibility,
  VoiceApprovalAction,
  VoiceSessionContext,
} from "../utils/voiceApprovalEligibility";
import { formatBlockedReasons, VOICE_APPROVAL_ACTIONS_BANNER } from "../utils/voiceApprovalLabels";
import { VoiceApprovalConfirmDialog } from "./VoiceApprovalConfirmDialog";

type Props = {
  sessionId: string | null;
  voice: VoiceRuntimeObservability;
  sessionContext?: VoiceSessionContext;
  onSuccess?: () => Promise<void> | void;
};

const ACTION_LABELS: Record<VoiceApprovalAction, string> = {
  approve: "Approve voice",
  reject: "Reject voice",
  expire: "Expire approval",
  reset: "Reset approval",
};

export function VoiceApprovalControlsPanel({
  sessionId,
  voice,
  sessionContext = {},
  onSuccess,
}: Props) {
  const [pendingAction, setPendingAction] = useState<VoiceApprovalAction | null>(null);
  const [acting, setActing] = useState(false);
  const [safetyError, setSafetyError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<VoiceApprovalActionResponse | null>(null);

  const eligibility = evaluateVoiceApprovalEligibility(voice, sessionContext);
  const anyVisible = (["approve", "reject", "expire", "reset"] as VoiceApprovalAction[]).some(
    (action) => eligibility[action].visible,
  );

  async function handleConfirm(payload: {
    reason: string;
    ttlMinutes?: number;
    clearLiveTtsRequest?: boolean;
  }) {
    if (!sessionId || !pendingAction) {
      return;
    }
    setActing(true);
    setActionError(null);
    setSafetyError(null);
    try {
      let result: VoiceApprovalActionResponse;
      if (pendingAction === "approve") {
        result = await postVoiceApprove(sessionId, {
          request_live_tts: true,
          reason: payload.reason,
          ttl_minutes: payload.ttlMinutes,
          approved_by: "operator",
        });
      } else if (pendingAction === "reject") {
        result = await postVoiceReject(sessionId, {
          reason: payload.reason,
          rejected_by: "operator",
        });
      } else if (pendingAction === "expire") {
        result = await postVoiceExpire(sessionId, {
          reason: payload.reason,
          expired_by: "operator",
        });
      } else {
        result = await postVoiceResetApproval(sessionId, {
          reason: payload.reason,
          reset_by: "operator",
          clear_live_tts_request: payload.clearLiveTtsRequest,
        });
      }
      setLastResult(result);
      setPendingAction(null);
      await onSuccess?.();
    } catch (err) {
      if (err instanceof VoiceApprovalSafetyError) {
        setSafetyError(err.message);
      } else {
        setActionError(parseVoiceApprovalError(err));
      }
    } finally {
      setActing(false);
    }
  }

  if (sessionContext.isLegacy) {
    return (
      <div className="voice-approval-actions-section">
        <h5>Voice approval actions</h5>
        <p className="muted voice-runtime-note">Legacy session — voice approval actions unavailable.</p>
      </div>
    );
  }

  return (
    <div className="voice-approval-actions-section">
      <h5>Voice approval actions</h5>
      <p className="muted voice-runtime-note">{VOICE_APPROVAL_ACTIONS_BANNER}</p>

      {voice.credentialsMissing && (
        <p className="voice-approval-state-note">Setup needed — ElevenLabs credentials missing.</p>
      )}
      {!voice.hasNarration && (
        <p className="voice-approval-state-note">No narration — voice approval unavailable.</p>
      )}
      {voice.blockedReasonCodes.length > 0 && (
        <p className="voice-approval-blocked-note">
          Blocked because: {formatBlockedReasons(voice.blockedReasonCodes)}
        </p>
      )}

      {safetyError && <p className="action-error-inline">{safetyError}</p>}
      {actionError && <p className="action-error-inline">{actionError}</p>}

      {!sessionId ? (
        <p className="muted voice-runtime-note">Session id required for voice approval actions.</p>
      ) : anyVisible ? (
        <div className="voice-approval-action-grid">
          {(["approve", "reject", "expire", "reset"] as VoiceApprovalAction[]).map((action) => {
            const gate = eligibility[action];
            if (!gate.visible) {
              return null;
            }
            return (
              <article
                key={action}
                className={`action-eligibility-card ${gate.allowed ? "allowed" : "blocked"}`}
              >
                <div className="action-eligibility-head">
                  <strong>{ACTION_LABELS[action]}</strong>
                  <span className={gate.allowed ? "action-pill-allowed" : "action-pill-blocked"}>
                    {gate.allowed ? "Available" : "Blocked"}
                  </span>
                </div>
                <p className="muted action-eligibility-reason">{gate.reason}</p>
                <button
                  type="button"
                  className={action === "reject" ? "btn-danger" : action === "approve" ? "" : "btn-neutral"}
                  disabled={!gate.allowed || acting}
                  onClick={() => setPendingAction(action)}
                >
                  {ACTION_LABELS[action]}
                </button>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="muted voice-runtime-note">No voice approval actions available for the current state.</p>
      )}

      {lastResult && (
        <div className="voice-approval-last-result">
          <strong>Last action:</strong> {lastResult.action} · tts_executed={String(lastResult.tts_executed)}
          {lastResult.message ? ` — ${lastResult.message}` : ""}
        </div>
      )}

      <VoiceApprovalConfirmDialog
        open={pendingAction !== null}
        action={pendingAction}
        voice={voice}
        loading={acting}
        onConfirm={(payload) => void handleConfirm(payload)}
        onCancel={() => setPendingAction(null)}
      />
    </div>
  );
}
