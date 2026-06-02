import type { BrowserStatusResponse } from "../api/browserOperationsClient";
import type { UatAssemblyMode, UatVideoProvider, UatVoiceProvider } from "../api/uatRuntimeClient";

export type UatFormState = {
  topic: string;
  platform: "youtube_shorts" | "tiktok" | "instagram_reels";
  durationSeconds: number;
  videoProvider: UatVideoProvider;
  voiceProvider: UatVoiceProvider;
  assemblyMode: UatAssemblyMode;
  confirmRealVoice: boolean;
  confirmRealVideo: boolean;
  confirmRealAssembly: boolean;
  oneRunAcknowledged: boolean;
};

export const UAT_MAX_DURATION_SECONDS = 90;
export const UAT_DEFAULT_MIN_DURATION_SECONDS = 15;

export const UAT_LIVE_VOICE_SMOKE_HELPER =
  "For real voice smoke UAT, duration may be auto-reduced to one provider-safe segment.";

export function isLiveVoiceSmokeUat(form: UatFormState): boolean {
  return form.voiceProvider === "elevenlabs" && form.confirmRealVoice;
}

export function uatSingleSegmentSafeDuration(videoProvider: UatVideoProvider): number {
  if (videoProvider === "hailuo_browser") {
    return 6;
  }
  return 10;
}

/** Provider-aware UAT duration default (Runway 10s, Hailuo 8s, mock 10s). */
export function uatDefaultDurationSeconds(videoProvider: UatVideoProvider): number {
  if (videoProvider === "hailuo_browser") {
    return 8;
  }
  return 10;
}

export function uatDurationMinSeconds(form: UatFormState): number {
  if (isLiveVoiceSmokeUat(form)) {
    return uatSingleSegmentSafeDuration(form.videoProvider);
  }
  return UAT_DEFAULT_MIN_DURATION_SECONDS;
}

export function uatDurationBounds(form: UatFormState): {
  min: number;
  max: number;
  helper: string;
} {
  const min = uatDurationMinSeconds(form);
  const max = UAT_MAX_DURATION_SECONDS;
  const providerDefault = uatDefaultDurationSeconds(form.videoProvider);
  const helper = isLiveVoiceSmokeUat(form)
    ? `${UAT_LIVE_VOICE_SMOKE_HELPER} Allowed: ${min}–${max}s.`
    : `Short-form UAT band: ${min}–${max} seconds. Default for this video provider: ${providerDefault}s.`;
  return { min, max, helper };
}

export function isUatDurationValid(form: UatFormState): boolean {
  const { min, max } = uatDurationBounds(form);
  return form.durationSeconds >= min && form.durationSeconds <= max;
}

export function liveVoiceSmokePreflightWarnings(form: UatFormState): string[] {
  if (!isLiveVoiceSmokeUat(form)) {
    return [];
  }
  const safeDuration = uatSingleSegmentSafeDuration(form.videoProvider);
  if (form.durationSeconds <= safeDuration) {
    return [];
  }
  return [
    `${UAT_LIVE_VOICE_SMOKE_HELPER} This run will use ${safeDuration}s before segment planning (11H-2d max 1 segment).`,
  ];
}

export function evaluateUatGenerateEligibility(
  form: UatFormState,
  running: boolean,
  browserStatus?: BrowserStatusResponse | null,
): {
  canGenerate: boolean;
  reasons: string[];
  preflightWarnings: string[];
} {
  const reasons: string[] = [];
  const preflightWarnings = liveVoiceSmokePreflightWarnings(form);
  const { min, max } = uatDurationBounds(form);

  if (!form.topic.trim()) {
    reasons.push("Topic is required.");
  }
  if (form.durationSeconds < min || form.durationSeconds > max) {
    reasons.push(`Duration must be between ${min} and ${max} seconds.`);
  }
  if (!form.oneRunAcknowledged) {
    reasons.push("Confirm one-run-only mode.");
  }
  if (form.voiceProvider === "elevenlabs" && !form.confirmRealVoice) {
    reasons.push("Voice approval required for ElevenLabs.");
  }
  if (form.assemblyMode === "real_assembly" && !form.confirmRealAssembly) {
    reasons.push("Assembly approval required for real FFmpeg assembly.");
  }
  if (isSupervisedRealRunwayUat(form)) {
    if (!form.confirmRealVideo) {
      reasons.push("Video approval required for real Runway browser execution.");
    } else if (!browserStatus?.ready_for_runway_browser) {
      reasons.push(
        browserStatus?.message ||
          "Runway browser must be running with CDP connected and Runway login detected.",
      );
    }
  }
  if (running) {
    reasons.push("A UAT run is already in progress.");
  }

  return { canGenerate: reasons.length === 0, reasons, preflightWarnings };
}

export function showVoiceApprovalGate(form: UatFormState): boolean {
  return form.voiceProvider === "elevenlabs";
}

export function showAssemblyApprovalGate(form: UatFormState): boolean {
  return form.assemblyMode === "real_assembly";
}

export function showRealVideoApprovalGate(form: UatFormState): boolean {
  return form.videoProvider === "runway_browser";
}

export function isSupervisedRealRunwayUat(form: UatFormState): boolean {
  return form.videoProvider === "runway_browser" && form.confirmRealVideo;
}
