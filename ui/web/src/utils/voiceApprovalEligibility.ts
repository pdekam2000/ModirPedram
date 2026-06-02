import { VoiceRuntimeObservability } from "./categoryRuntimeShell";

export type VoiceApprovalAction = "approve" | "reject" | "expire" | "reset";

export type VoiceActionEligibility = {
  visible: boolean;
  allowed: boolean;
  reason: string;
};

export type VoiceSessionContext = {
  archived?: boolean;
  cancelRequested?: boolean;
  isLegacy?: boolean;
};

export type VoiceApprovalEligibilityMap = Record<VoiceApprovalAction, VoiceActionEligibility>;

function blocked(reason: string, visible = false): VoiceActionEligibility {
  return { visible, allowed: false, reason };
}

function allowedEntry(reason: string): VoiceActionEligibility {
  return { visible: true, allowed: true, reason };
}

export function evaluateVoiceApprovalEligibility(
  voice: VoiceRuntimeObservability,
  session: VoiceSessionContext = {},
): VoiceApprovalEligibilityMap {
  const state = voice.approvalStateKey;
  const hidden = (reason: string): VoiceApprovalEligibilityMap => ({
    approve: blocked(reason),
    reject: blocked(reason),
    expire: blocked(reason),
    reset: blocked(reason),
  });

  if (session.isLegacy) {
    return hidden("Legacy session — voice approval actions unavailable.");
  }

  if (session.archived) {
    return {
      approve: blocked("Session archived — voice approval disabled.", true),
      reject: blocked("Session archived — voice approval disabled.", true),
      expire: blocked("Session archived — voice approval disabled.", true),
      reset: blocked("Session archived — voice approval disabled.", true),
    };
  }

  if (session.cancelRequested) {
    return {
      approve: blocked("Session cancellation requested.", true),
      reject: blocked("Session cancellation requested.", true),
      expire: blocked("Session cancellation requested.", true),
      reset: blocked("Session cancellation requested.", true),
    };
  }

  if (!voice.hasNarration) {
    return hidden("No narration — voice approval unavailable.");
  }

  if (voice.credentialsMissing) {
    return hidden("ElevenLabs credentials missing — setup needed.");
  }

  if (voice.voiceTtsRunning) {
    return hidden("Voice TTS is running — actions unavailable.");
  }

  const approveBase =
    voice.providerIsElevenlabs &&
    voice.preflightReady &&
    state !== "approved";

  const approve = approveBase
    ? allowedEntry("Approve future voice generation metadata.")
    : state === "approved"
      ? blocked("Voice is already approved.", true)
      : !voice.preflightReady
        ? blocked("Voice preflight not ready.")
        : blocked("Approve unavailable for current voice slot state.");

  const rejectVisible = state === "required" || state === "approved";
  const reject = rejectVisible
    ? allowedEntry("Reject voice approval.")
    : blocked("Reject available only when approval is required or approved.");

  const expireVisible = state === "approved";
  const expire = expireVisible
    ? allowedEntry("Expire active voice approval.")
    : blocked("Expire available only when approval is approved.");

  const resetVisible = state === "rejected" || state === "expired" || state === "approved";
  const reset = resetVisible
    ? allowedEntry("Reset voice approval metadata.")
    : blocked("Reset available for rejected, expired, or approved states.");

  return { approve, reject, expire, reset };
}
