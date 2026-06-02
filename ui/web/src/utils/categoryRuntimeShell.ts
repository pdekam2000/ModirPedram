import { RuntimeStatusResponse } from "../api/client";

export type CategoryRuntimeSlot = {
  category_key: string;
  category_name: string;
  status: string;
  provider?: string | null;
  artifacts?: unknown[];
  error?: unknown;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  cost_estimate?: unknown;
  runtime_notes?: string[];
  executable?: boolean;
  future_router?: string | null;
  executed?: boolean;
  dry_run?: boolean;
  live_tts?: boolean;
  voice_preflight?: Record<string, unknown> | null;
  narration_adapter?: Record<string, unknown> | null;
  segment_count?: number | null;
  live_tts_requested?: boolean;
  approval?: VoiceApprovalBlock | AssemblyApprovalBlock | null;
  source_type?: string | null;
  source_ready?: boolean;
  timing_strategy?: string | null;
  cue_count?: number | null;
  formats_written?: string[];
  manifest_path?: string | null;
  validation_status?: string | null;
  subtitle_preflight?: Record<string, unknown> | null;
  supported_formats?: string[];
  assembly_mode?: string | null;
  subtitle_mode?: string | null;
  expected_output?: string | null;
  output_created?: boolean;
  real_assembly_executed?: boolean;
  assembly_preflight?: Record<string, unknown> | null;
  real_assembly_requested?: boolean;
};

export type AssemblyApprovalBlock = {
  gate_version?: string;
  approval_required?: boolean;
  approval_state?: string;
  approved_by?: string | null;
  approved_at?: string | null;
  approval_reason?: string | null;
  approval_expires_at?: string | null;
  estimated_runtime_seconds?: number | null;
  estimated_output_size?: number | null;
  estimated_disk_usage?: number | null;
  assembly_eligible?: boolean;
  assembly_blocked_reasons?: string[];
};

export type VoiceApprovalBlock = {
  gate_version?: string;
  approval_required?: boolean;
  approval_state?: string;
  approved_by?: string | null;
  approved_at?: string | null;
  approval_reason?: string | null;
  estimated_voice_cost?: number | null;
  estimated_voice_cost_currency?: string;
  estimated_voice_cost_confidence?: string;
  estimated_character_count?: number | null;
  estimated_segment_count?: number | null;
  approval_expires_at?: string | null;
  live_tts_eligible?: boolean;
  live_tts_blocked_reasons?: string[];
};

export type VoiceRuntimeObservability = {
  category_key: string;
  status: string;
  statusLabel: string;
  statusClassName: string;
  provider: string;
  executed: string;
  dryRun: string;
  preflightStatus: string;
  preflightCode: string;
  segmentCount: string;
  totalTextLength: string;
  runtimeNotes: string;
  errorCode: string;
  isVoice: true;
  approvalRequired: string;
  approvalState: string;
  estimatedCharacters: string;
  estimatedSegments: string;
  estimatedVoiceCost: string;
  approvalExpiresAt: string;
  liveTtsEligible: string;
  blockedReasons: string;
  approvalGateNote: string;
  approvalStateKey: string;
  providerIsElevenlabs: boolean;
  preflightReady: boolean;
  hasNarration: boolean;
  credentialsMissing: boolean;
  voiceTtsRunning: boolean;
  blockedReasonCodes: string[];
  defaultTtlMinutes: number;
};

const STATUS_LABELS: Record<string, string> = {
  planned: "Planned",
  pending: "Preflight ready",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  skipped: "No narration",
};

const FORBIDDEN_TTS_ACTIONS = [
  "generate voice",
  "generate narration",
  "generateVoice",
  "dispatchVoice",
  "runTts",
  "elevenlabs",
] as const;

function dash(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return value;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function readErrorCode(error: unknown): string {
  const record = asRecord(error);
  return record?.code ? String(record.code) : "";
}

export function resolveCategoryRuntimeSlots(
  status: RuntimeStatusResponse | null | undefined,
  legacyPanel?: Record<string, unknown>,
): CategoryRuntimeSlot[] {
  const fromStatus = status?.category_runtime_slots;
  if (Array.isArray(fromStatus) && fromStatus.length > 0) {
    return fromStatus.map((raw) => normalizeSlot(raw as Record<string, unknown>));
  }

  const panelSlots = legacyPanel?.category_runtime_slots;
  if (Array.isArray(panelSlots) && panelSlots.length > 0) {
    return panelSlots.map((raw) => normalizeSlot(raw as Record<string, unknown>));
  }

  const runtime = legacyPanel?.execution_runtime as Record<string, unknown> | undefined;
  const categoryRuntime = runtime?.category_runtime as Record<string, unknown> | undefined;
  if (!categoryRuntime) {
    return defaultPlaceholderSlots();
  }

  return Object.entries(categoryRuntime).map(([categoryKey, raw]) =>
    normalizeSlot({ category_key: categoryKey, ...(asRecord(raw) || {}) }),
  );
}

function normalizeSlot(raw: Record<string, unknown>): CategoryRuntimeSlot {
  const categoryKey = String(raw.category_key || "unknown");
  const artifacts = Array.isArray(raw.artifacts) ? raw.artifacts : [];
  const runtimeNotes = Array.isArray(raw.runtime_notes)
    ? raw.runtime_notes.map(String)
    : undefined;

  return {
    category_key: categoryKey,
    category_name: String(raw.category_name || categoryKey.replace(/_generation$/, "")),
    status: String(raw.status || "planned"),
    provider: raw.provider ? String(raw.provider) : null,
    artifacts,
    error: raw.error ?? null,
    started_at: raw.started_at ? String(raw.started_at) : null,
    completed_at: raw.completed_at ? String(raw.completed_at) : null,
    duration_seconds: typeof raw.duration_seconds === "number" ? raw.duration_seconds : null,
    cost_estimate: raw.cost_estimate ?? null,
    runtime_notes: runtimeNotes,
    executable: raw.executable === true || categoryKey === "video_generation",
    future_router: raw.future_router ? String(raw.future_router) : null,
    executed: typeof raw.executed === "boolean" ? raw.executed : undefined,
    dry_run: typeof raw.dry_run === "boolean" ? raw.dry_run : undefined,
    live_tts: typeof raw.live_tts === "boolean" ? raw.live_tts : undefined,
    voice_preflight: asRecord(raw.voice_preflight),
    narration_adapter: asRecord(raw.narration_adapter),
    segment_count: typeof raw.segment_count === "number" ? raw.segment_count : null,
    live_tts_requested: typeof raw.live_tts_requested === "boolean" ? raw.live_tts_requested : undefined,
    approval: asRecord(raw.approval) as VoiceApprovalBlock | null,
    source_type: raw.source_type ? String(raw.source_type) : null,
    source_ready: typeof raw.source_ready === "boolean" ? raw.source_ready : undefined,
    timing_strategy: raw.timing_strategy ? String(raw.timing_strategy) : null,
    cue_count: typeof raw.cue_count === "number" ? raw.cue_count : null,
    formats_written: Array.isArray(raw.formats_written) ? raw.formats_written.map(String) : undefined,
    manifest_path: raw.manifest_path ? String(raw.manifest_path) : null,
    validation_status: raw.validation_status ? String(raw.validation_status) : null,
    subtitle_preflight: asRecord(raw.subtitle_preflight),
    supported_formats: Array.isArray(raw.supported_formats)
      ? raw.supported_formats.map(String)
      : undefined,
  };
}

function defaultPlaceholderSlots(): CategoryRuntimeSlot[] {
  return [
    { category_key: "video_generation", category_name: "video", status: "planned", executable: true },
    { category_key: "voice_generation", category_name: "voice", status: "planned", executable: false },
    { category_key: "music_generation", category_name: "music", status: "planned", executable: false },
    { category_key: "subtitle_generation", category_name: "subtitle_generation", status: "planned", executable: false },
    { category_key: "assembly_generation", category_name: "assembly_generation", status: "planned", executable: false },
  ];
}

export function formatCategoryStatus(status: string | null | undefined): string {
  const key = String(status || "planned").toLowerCase();
  return STATUS_LABELS[key] || key;
}

export function formatVoiceStatusLabel(
  status: string | null | undefined,
  errorCode?: string | null,
): string {
  const key = String(status || "planned").toLowerCase();
  if (key === "failed" && String(errorCode || "").toUpperCase() === "CREDENTIALS_MISSING") {
    return "Setup needed";
  }
  return formatCategoryStatus(status);
}

export function categoryStatusClass(status: string | null | undefined, errorCode?: string | null): string {
  const key = String(status || "planned").toLowerCase();
  if (key === "pending" || key === "running" || key === "completed") {
    return "runtime-gate runtime-gate-pass";
  }
  if (key === "failed") {
    return "runtime-gate runtime-gate-fail";
  }
  if (key === "skipped") {
    return "runtime-gate runtime-gate-unknown";
  }
  if (key === "failed" && String(errorCode || "").toUpperCase() === "CREDENTIALS_MISSING") {
    return "runtime-gate runtime-gate-fail";
  }
  return "runtime-gate runtime-gate-unknown";
}

function formatApprovalState(state: string | null | undefined): string {
  const key = String(state || "").toLowerCase();
  const labels: Record<string, string> = {
    not_required: "Not required",
    required: "Approval required",
    approved: "Approved for TTS",
    rejected: "Voice rejected",
    expired: "Approval expired",
  };
  return labels[key] || dash(state || undefined);
}

function formatEstimatedCost(approval: VoiceApprovalBlock | null): string {
  if (!approval || approval.estimated_voice_cost == null) {
    return "—";
  }
  const currency = approval.estimated_voice_cost_currency || "USD";
  const confidence = approval.estimated_voice_cost_confidence
    ? ` (${approval.estimated_voice_cost_confidence} confidence)`
    : "";
  return `${currency} ${Number(approval.estimated_voice_cost).toFixed(4)}${confidence}`;
}

function resolveApprovalBlock(
  voice: CategoryRuntimeSlot,
  runtimeVoiceSlot: Record<string, unknown> | null,
  operationsGate: Record<string, unknown> | null,
): VoiceApprovalBlock | null {
  return (
    voice.approval ||
    (asRecord(runtimeVoiceSlot?.approval) as VoiceApprovalBlock | null) ||
    (asRecord(operationsGate) as VoiceApprovalBlock | null)
  );
}

export function resolveVoiceRuntimeObservability(
  status: RuntimeStatusResponse | null | undefined,
  legacyPanel?: Record<string, unknown>,
): VoiceRuntimeObservability {
  const slots = resolveCategoryRuntimeSlots(status, legacyPanel);
  const voice =
    slots.find((slot) => slot.category_key === "voice_generation") ||
    ({
      category_key: "voice_generation",
      category_name: "voice",
      status: String(legacyPanel?.voice_generation_status || "planned"),
      provider: null,
    } as CategoryRuntimeSlot);

  const operationsDryRun = asRecord(
    (legacyPanel?.voice_preflight_dry_run as unknown) ||
      asRecord(asRecord(legacyPanel?.execution_runtime)?.operations)?.voice_preflight_dry_run,
  );
  const operationsApprovalGate = asRecord(
    asRecord(asRecord(legacyPanel?.execution_runtime)?.operations)?.voice_approval_gate,
  );
  const runtimeVoiceSlot = asRecord(
    asRecord(asRecord(legacyPanel?.execution_runtime)?.category_runtime)?.voice_generation,
  );
  const voicePreflight = voice.voice_preflight || asRecord(runtimeVoiceSlot?.voice_preflight);
  const preflightRecord = asRecord(voicePreflight) || operationsDryRun;
  const adapter =
    voice.narration_adapter || asRecord(runtimeVoiceSlot?.narration_adapter);
  const errorCode =
    readErrorCode(voice.error) ||
    (preflightRecord?.code ? String(preflightRecord.code) : "");
  const segmentCount =
    voice.segment_count ??
    (typeof adapter?.segment_count === "number" ? adapter.segment_count : null) ??
    (typeof operationsDryRun?.segment_count === "number" ? operationsDryRun.segment_count : null);

  const totalTextLength =
    typeof adapter?.total_text_length === "number" ? adapter.total_text_length : null;

  const runtimeNotes = (voice.runtime_notes || [])
    .concat(Array.isArray(adapter?.warnings) ? adapter.warnings.map(String) : [])
    .filter(Boolean);

  const preflightStatus =
    preflightRecord?.status != null
      ? String(preflightRecord.status)
      : preflightRecord?.ready === true
        ? "ready"
        : preflightRecord?.ready === false
          ? "failed"
          : "";

  const executedValue =
    typeof voice.executed === "boolean"
      ? voice.executed
      : typeof legacyPanel?.voice_generation_executed === "boolean"
        ? legacyPanel.voice_generation_executed
        : typeof operationsDryRun?.executed === "boolean"
          ? operationsDryRun.executed
          : null;

  const dryRunValue =
    typeof voice.dry_run === "boolean"
      ? voice.dry_run
      : typeof operationsDryRun?.dry_run === "boolean"
        ? operationsDryRun.dry_run
        : null;

  const approval = resolveApprovalBlock(voice, runtimeVoiceSlot, operationsApprovalGate);
  const approvalRequired =
    typeof approval?.approval_required === "boolean" ? approval.approval_required : null;
  const approvalState = approval?.approval_state ? String(approval.approval_state) : "";
  const estimatedCharacters =
    approval?.estimated_character_count ??
    (typeof totalTextLength === "number" ? Number(totalTextLength) : null);
  const estimatedSegments =
    approval?.estimated_segment_count ??
    (typeof segmentCount === "number" ? segmentCount : null);
  const blockedReasons = Array.isArray(approval?.live_tts_blocked_reasons)
    ? approval.live_tts_blocked_reasons.map(String).filter(Boolean)
    : [];
  const liveTtsEligible =
    typeof approval?.live_tts_eligible === "boolean" ? approval.live_tts_eligible : null;

  const providerRaw =
    voice.provider && voice.provider !== "—"
      ? voice.provider
      : String(runtimeVoiceSlot?.provider || "");
  const providerIsElevenlabs = providerRaw.toLowerCase() === "elevenlabs";
  const preflightReady =
    preflightRecord?.ready === true || String(preflightStatus).toLowerCase() === "ready";
  const hasNarration =
    String(voice.status || "").toLowerCase() !== "skipped" &&
    (Number(segmentCount) > 0 || Number(totalTextLength) > 0);
  const credentialsMissing =
    String(errorCode || "").toUpperCase() === "CREDENTIALS_MISSING" ||
    String(preflightRecord?.code || "").toUpperCase() === "CREDENTIALS_MISSING";
  const voiceTtsRunning =
    String(voice.status || "").toLowerCase() === "running" || voice.live_tts === true;

  return {
    category_key: "voice_generation",
    status: voice.status || "planned",
    statusLabel: formatVoiceStatusLabel(voice.status, errorCode),
    statusClassName: categoryStatusClass(voice.status, errorCode),
    provider: dash(voice.provider),
    executed: executedValue === null ? "—" : String(executedValue),
    dryRun: dryRunValue === null ? "—" : String(dryRunValue),
    preflightStatus: dash(preflightStatus),
    preflightCode: dash(
      (preflightRecord?.code as string | undefined) ||
        (operationsDryRun?.reject_code as string | undefined) ||
        errorCode ||
        undefined,
    ),
    segmentCount: segmentCount === null ? "—" : String(segmentCount),
    totalTextLength: totalTextLength === null ? "—" : String(totalTextLength),
    runtimeNotes: runtimeNotes.length > 0 ? runtimeNotes.join(" · ") : "—",
    errorCode: dash(errorCode || undefined),
    isVoice: true,
    approvalRequired: approvalRequired === null ? "—" : String(approvalRequired),
    approvalState: formatApprovalState(approvalState),
    estimatedCharacters: estimatedCharacters === null ? "—" : String(estimatedCharacters),
    estimatedSegments: estimatedSegments === null ? "—" : String(estimatedSegments),
    estimatedVoiceCost: formatEstimatedCost(approval),
    approvalExpiresAt: dash(approval?.approval_expires_at || undefined),
    liveTtsEligible: liveTtsEligible === null ? "—" : String(liveTtsEligible),
    blockedReasons: blockedReasons.length > 0 ? blockedReasons.join(" · ") : "—",
    approvalGateNote:
      "Read-only gate metadata — approving authorizes future voice generation only; no audio is generated in this phase.",
    approvalStateKey: approvalState.toLowerCase() || "not_required",
    providerIsElevenlabs: providerIsElevenlabs,
    preflightReady,
    hasNarration,
    credentialsMissing,
    voiceTtsRunning,
    blockedReasonCodes: blockedReasons,
    defaultTtlMinutes: 240,
  };
}

export function uiContainsLiveTtsActions(source: string): boolean {
  const lowered = source.toLowerCase();
  return (
    lowered.includes("<button") &&
    (lowered.includes("generate voice") ||
      lowered.includes("generate narration") ||
      lowered.includes("run tts") ||
      lowered.includes("dispatchvoice"))
  );
}

export { FORBIDDEN_TTS_ACTIONS };
