import type { UatAssemblyMode, UatRunResponse, UatVideoProvider, UatVoiceProvider } from "../api/uatRuntimeClient";

export const UAT_BRAND_TITLE = "MODIR AGENT OS";
export const UAT_BRAND_SUBTITLE = "Pedram AI Content Factory";
export const UAT_RUNTIME_MODE_LABEL = "Generic UAT Runtime";
export const UAT_GENERATE_LABEL = "Generate UAT Video";

export const UAT_SAFETY_WARNING =
  "This run may use real providers and generate billable content. One supervised run only — nothing is published automatically.";

export const UAT_PHASE_I_ROUTING_WARNING =
  "This UAT Runtime is generic and does not run Phase I continuity chaining (starter image → Use to Video → 3 clips → Use Frame ×2 → remove image). " +
  "Use Execution Center → Runway Live Smoke → 3-Clip Continuity (Phase I) for Phase I.";

export type UatStageKey =
  | "content_brain"
  | "session_builder"
  | "video"
  | "voice"
  | "subtitle"
  | "assembly"
  | "final_mp4";

export type UatStageDef = {
  key: UatStageKey;
  label: string;
  backendKey?: string;
};

export const UAT_STAGE_ORDER: UatStageDef[] = [
  { key: "content_brain", label: "Content Brain", backendKey: "content_brain" },
  { key: "session_builder", label: "Session Builder", backendKey: "content_brain" },
  { key: "video", label: "Video Runtime", backendKey: "video" },
  { key: "voice", label: "Voice Runtime", backendKey: "voice" },
  { key: "subtitle", label: "Subtitle Runtime", backendKey: "subtitle" },
  { key: "assembly", label: "Assembly Runtime", backendKey: "assembly" },
  { key: "final_mp4", label: "Final Video", backendKey: "final_mp4" },
];

export type ProviderChipState = "ready" | "approval" | "unavailable";

export function providerChipLabel(state: ProviderChipState): string {
  if (state === "ready") return "Ready";
  if (state === "approval") return "Approval Required";
  return "Not Available";
}

export function videoProviderChip(provider: UatVideoProvider): ProviderChipState {
  if (provider === "mock") return "ready";
  return "approval";
}

export function voiceProviderChip(provider: UatVoiceProvider): ProviderChipState {
  if (provider === "mock") return "ready";
  return "approval";
}

export function assemblyModeChip(mode: UatAssemblyMode): ProviderChipState {
  if (mode === "dry_run_only") return "ready";
  return "approval";
}

export type UatWorkspaceStatus = "READY" | "RUNNING" | "COMPLETED" | "FAILED";

export function workspaceStatusFromRun(status: UatRunResponse | null, running: boolean): UatWorkspaceStatus {
  if (running || status?.status === "running") return "RUNNING";
  if (status?.status === "completed") return "COMPLETED";
  if (status?.status === "failed") return "FAILED";
  return "READY";
}

export function stageStatus(
  stageKey: UatStageKey,
  status: UatRunResponse | null,
  currentStage: string | null | undefined,
): "pending" | "active" | "completed" | "failed" {
  const order = UAT_STAGE_ORDER.map((item) => item.key);
  const normalizedCurrent = currentStage ? normalizeStageKey(currentStage) : null;
  const currentIndex = normalizedCurrent ? order.indexOf(normalizedCurrent) : -1;
  const stageIndex = order.indexOf(stageKey);

  const def = UAT_STAGE_ORDER.find((item) => item.key === stageKey);
  const backendKey = def?.backendKey ?? stageKey;
  const stageResult = status?.stages?.[backendKey];

  if (status?.status === "failed") {
    const failedStage = inferFailedStage(status, currentStage);
    if (failedStage === stageKey) {
      return "failed";
    }
  }

  if (stageResult && (stageResult as { success?: boolean }).success === false) {
    return "failed";
  }

  if (stageKey === "final_mp4") {
    if (status?.status === "completed") return "completed";
    if (currentStage === "final_mp4") return "active";
    return stageIndex <= currentIndex ? "completed" : "pending";
  }

  if (stageKey === "session_builder") {
    const brain = status?.stages?.content_brain;
    if (brain && (brain as { success?: boolean }).success) {
      if (currentIndex > stageIndex) return "completed";
      if (normalizedCurrent === "content_brain" && currentIndex >= stageIndex) return "active";
      if (currentIndex === stageIndex) return "active";
    }
    if (currentIndex > stageIndex) return "completed";
    return "pending";
  }

  if (stageResult && (stageResult as { success?: boolean }).success) {
    return "completed";
  }

  if (normalizedCurrent === stageKey) return "active";
  if (currentIndex > stageIndex) return "completed";
  return "pending";
}

function inferFailedStage(
  status: UatRunResponse,
  currentStage: string | null | undefined,
): UatStageKey | null {
  if (status.failed_stage) {
    const key = normalizeStageKey(status.failed_stage);
    if (key) return key;
  }

  if (currentStage && currentStage !== "failed") {
    const key = normalizeStageKey(currentStage);
    if (key) return key;
  }

  const log = status.progress_log ?? [];
  for (let index = log.length - 1; index >= 0; index -= 1) {
    const entry = log[index];
    if (entry.stage === "failed") continue;
    const key = normalizeStageKey(entry.stage);
    if (!key) continue;
    const def = UAT_STAGE_ORDER.find((item) => item.key === key);
    const backendKey = def?.backendKey ?? key;
    const result = status.stages?.[backendKey] as { success?: boolean } | undefined;
    if (!result?.success) {
      return key;
    }
  }
  return null;
}

function normalizeStageKey(value: string): UatStageKey | null {
  if (value === "starting") return "content_brain";
  if (value === "failed") return null;
  const match = UAT_STAGE_ORDER.find((item) => item.key === value || item.backendKey === value);
  return match?.key ?? null;
}

export function formatPlatformLabel(platform: string): string {
  if (platform === "youtube_shorts") return "YouTube Shorts";
  if (platform === "instagram_reels") return "Instagram Reels";
  if (platform === "tiktok") return "TikTok";
  return platform;
}

export function estimateUatCostUsd(config: {
  videoProvider: UatVideoProvider;
  voiceProvider: UatVoiceProvider;
  assemblyMode: UatAssemblyMode;
  confirmRealVoice: boolean;
}): string {
  let low = 0;
  let high = 0;
  if (config.videoProvider !== "mock") {
    low += 0.5;
    high += 2.5;
  }
  if (config.voiceProvider === "elevenlabs" && config.confirmRealVoice) {
    low += 0.15;
    high += 1.0;
  }
  if (config.assemblyMode === "real_assembly") {
    low += 0;
    high += 0;
  }
  if (low === 0 && high === 0) return "$0.00 (mock / dry-run)";
  return `$${low.toFixed(2)} – $${high.toFixed(2)} est.`;
}

export const REVIEW_SCORE_FIELDS = [
  { key: "story_quality_score", label: "Story" },
  { key: "visual_quality_score", label: "Visual" },
  { key: "voice_quality_score", label: "Voice" },
  { key: "subtitle_quality_score", label: "Subtitle" },
  { key: "continuity_score", label: "Continuity" },
  { key: "overall_quality_score", label: "Overall" },
] as const;
