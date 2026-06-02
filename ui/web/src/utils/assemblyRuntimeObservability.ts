import { RuntimeStatusResponse } from "../api/client";
import { formatDurationSeconds } from "./runtimeObservability";
import {
  CategoryRuntimeSlot,
  categoryStatusClass,
  resolveCategoryRuntimeSlots,
} from "./categoryRuntimeShell";

export const ASSEMBLY_SAFETY_COPY =
  "Assembly is currently running in dry-run mode only. No FFmpeg execution is enabled.";

export const ASSEMBLY_NO_OUTPUT_COPY = "No final video has been generated.";

export const ASSEMBLY_EXPECTED_OUTPUT_LABEL = "Expected Output Only";

export const EXPECTED_ASSEMBLY_OUTPUT = "FINAL_PUBLISH_READY.mp4";

export const ASSEMBLY_STATUS_LABELS: Record<string, string> = {
  planned: "Not started",
  pending: "Ready",
  running: "Preparing assembly",
  completed: "Assembly ready",
  failed: "Failed",
  skipped: "No assembly inputs",
  cancelled: "Cancelled",
};

export const ASSEMBLY_MODE_LABELS: Record<string, string> = {
  video_voice_subtitle: "Video + voice + subtitles",
  video_voice: "Video + voice",
  video_only: "Video only",
  voice_only: "Voice only",
  multi_language_audio: "Multi-language audio (reserved)",
  multi_subtitle_track: "Multi subtitle track (reserved)",
};

export const ASSEMBLY_SUBTITLE_MODE_LABELS: Record<string, string> = {
  burn_in: "Burn-in (ASS/SRT)",
  sidecar: "Sidecar mux (reserved)",
  none: "No subtitles",
};

export const ASSEMBLY_VALIDATION_LABELS: Record<string, string> = {
  READY: "Ready",
  PARTIAL: "Partial — missing inputs",
  FAILED: "Failed — inputs invalid",
};

export const ASSEMBLY_APPROVAL_STATE_LABELS: Record<string, string> = {
  not_required: "Not required",
  required: "Approval required",
  approved: "Approved for assembly",
  rejected: "Rejected",
  expired: "Expired",
};

export type AssemblyPlannedStepRow = {
  step: number;
  name: string;
  action: string;
  detail: string;
};

export type AssemblyRuntimeObservability = {
  category_key: "assembly_generation";
  status: string;
  statusLabel: string;
  statusClassName: string;
  provider: string;
  validationStatus: string;
  assemblyMode: string;
  subtitleMode: string;
  expectedOutput: string;
  expectedOutputPath: string;
  outputCreated: string;
  realAssemblyExecuted: string;
  plannedSteps: AssemblyPlannedStepRow[];
  inputSummary: string;
  outputSummary: string;
  warnings: string[];
  errors: string[];
  errorCode: string;
  errorMessage: string;
  startedAt: string;
  completedAt: string;
  durationSeconds: string;
  safetyNote: string;
  noOutputNote: string;
  showPlannedSteps: boolean;
  showExpectedOutput: boolean;
  isGeneratedOutput: boolean;
  approvalRequired: string;
  approvalState: string;
  approvalExpiresAt: string;
  estimatedRuntimeSeconds: string;
  estimatedOutputSize: string;
  estimatedDiskUsage: string;
  assemblyEligible: string;
  assemblyBlockedReasons: string[];
  showApprovalSection: boolean;
  approvalGloballyDisabledNote: string;
  approvalStateKey: string;
  validationStatusKey: string;
  dryRunCompleted: boolean;
  hasAssemblySlot: boolean;
  assemblyRunning: boolean;
  defaultTtlMinutes: number;
  plannedStepsCount: number;
};

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
  if (typeof error === "string" && error.trim()) {
    return error.trim();
  }
  const record = asRecord(error);
  return record?.code ? String(record.code) : "";
}

function readErrorMessage(error: unknown): string {
  const record = asRecord(error);
  return record?.message ? String(record.message) : "";
}

function formatAssemblyMode(value: string | null | undefined): string {
  const key = String(value || "").toLowerCase();
  return ASSEMBLY_MODE_LABELS[key] || dash(value || undefined);
}

function formatSubtitleMode(value: string | null | undefined): string {
  const key = String(value || "").toLowerCase();
  return ASSEMBLY_SUBTITLE_MODE_LABELS[key] || dash(value || undefined);
}

function formatValidationStatus(value: string | null | undefined): string {
  const key = String(value || "").toUpperCase();
  return ASSEMBLY_VALIDATION_LABELS[key] || dash(value || undefined);
}

export function formatAssemblyStatusLabel(
  status: string | null | undefined,
  errorCode?: string | null,
): string {
  const key = String(status || "planned").toLowerCase();
  if (key === "failed" && String(errorCode || "").toUpperCase() === "ASSEMBLY_REAL_EXECUTION_DISABLED") {
    return "Real execution disabled";
  }
  return ASSEMBLY_STATUS_LABELS[key] || key;
}

function formatInputSummary(summary: Record<string, unknown> | null): string {
  if (!summary) {
    return "—";
  }
  const video = summary.video_count ?? summary.video;
  const voice = summary.voice_count ?? summary.voice;
  const subtitle = summary.subtitle_count ?? summary.subtitle;
  const parts: string[] = [];
  if (video !== undefined && video !== null) {
    parts.push(`Video clips: ${video}`);
  }
  if (voice !== undefined && voice !== null) {
    parts.push(`Voice segments: ${voice}`);
  }
  if (subtitle !== undefined && subtitle !== null) {
    parts.push(`Subtitle tracks: ${subtitle}`);
  }
  return parts.length > 0 ? parts.join(" · ") : "—";
}

function formatOutputSummary(summary: Record<string, unknown> | null): string {
  if (!summary) {
    return "—";
  }
  const parts: string[] = [];
  const expected = summary.expected_output;
  const outputFile = summary.output_file;
  const created = summary.output_created;
  const size = summary.output_size;
  if (expected !== undefined && expected !== null && expected !== "") {
    parts.push(`Expected: ${expected}`);
  }
  if (outputFile !== undefined && outputFile !== null && outputFile !== "") {
    parts.push(`File: ${outputFile}`);
  }
  if (created !== undefined && created !== null) {
    parts.push(`Created: ${created}`);
  }
  if (size !== undefined && size !== null) {
    parts.push(`Size: ${size}`);
  }
  return parts.length > 0 ? parts.join(" · ") : "—";
}

function parsePlannedSteps(raw: unknown): AssemblyPlannedStepRow[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .map((item, index) => {
      const record = asRecord(item);
      if (!record) {
        return null;
      }
      const detailRecord = asRecord(record.detail);
      const detail = detailRecord ? JSON.stringify(detailRecord) : "—";
      return {
        step: typeof record.step === "number" ? record.step : index + 1,
        name: dash(record.name ? String(record.name) : undefined),
        action: dash(record.action ? String(record.action) : undefined),
        detail,
      };
    })
    .filter(Boolean) as AssemblyPlannedStepRow[];
}

function formatApprovalState(value: string | null | undefined): string {
  const key = String(value || "not_required").toLowerCase();
  return ASSEMBLY_APPROVAL_STATE_LABELS[key] || dash(value || undefined);
}

function formatBytesEstimate(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)} MB`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)} KB`;
  }
  return `${value} B`;
}

function parseStringList(raw: unknown): string[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.map((item) => {
    if (typeof item === "string") {
      return item;
    }
    const record = asRecord(item);
    if (record?.message) {
      return String(record.message);
    }
    if (record?.code) {
      return String(record.code);
    }
    return String(item);
  });
}

function resolveDurationSeconds(slot: CategoryRuntimeSlot): number | null {
  if (typeof slot.duration_seconds === "number") {
    return slot.duration_seconds;
  }
  const executionTime = (slot as Record<string, unknown>).execution_time_seconds;
  if (typeof executionTime === "number") {
    return executionTime;
  }
  return null;
}

function resolveExpectedOutputPath(
  slot: CategoryRuntimeSlot,
  sessionId: string | null,
): string {
  const outputSummary = asRecord((slot as Record<string, unknown>).output_summary);
  const outputFile = outputSummary?.output_file;
  if (typeof outputFile === "string" && outputFile.trim()) {
    return outputFile;
  }
  const expected = slot.expected_output || EXPECTED_ASSEMBLY_OUTPUT;
  if (sessionId) {
    return `storage/content_brain/execution/artifacts/${sessionId}/assembly_generation/${expected}`.replace(
      /\\/g,
      "/",
    );
  }
  return "—";
}

export function findAssemblyRuntimeSlot(
  status: RuntimeStatusResponse | null | undefined,
  legacyPanel?: Record<string, unknown>,
): CategoryRuntimeSlot {
  const slots = resolveCategoryRuntimeSlots(status, legacyPanel);
  const fromSlots =
    slots.find((slot) => slot.category_key === "assembly_generation") ||
    slots.find((slot) => slot.category_key === "assembly");

  if (fromSlots) {
    return {
      ...fromSlots,
      category_key: "assembly_generation",
      category_name: "assembly_generation",
    };
  }

  const runtime = asRecord(legacyPanel?.execution_runtime) || asRecord(status?.execution_runtime);
  const categoryRuntime = asRecord(runtime?.category_runtime);
  const raw = asRecord(categoryRuntime?.assembly_generation) || asRecord(categoryRuntime?.assembly);

  if (raw) {
    return {
      category_key: "assembly_generation",
      category_name: "assembly_generation",
      status: String(raw.status || "planned"),
      provider: raw.provider ? String(raw.provider) : "local_assembly_runtime",
      artifacts: Array.isArray(raw.artifacts) ? raw.artifacts : [],
      error: raw.error ?? null,
      started_at: raw.started_at ? String(raw.started_at) : null,
      completed_at: raw.completed_at ? String(raw.completed_at) : null,
      duration_seconds: typeof raw.duration_seconds === "number" ? raw.duration_seconds : null,
      validation_status: raw.validation_status ? String(raw.validation_status) : null,
      assembly_mode: raw.assembly_mode ? String(raw.assembly_mode) : null,
      subtitle_mode: raw.subtitle_mode ? String(raw.subtitle_mode) : null,
      expected_output: raw.expected_output ? String(raw.expected_output) : null,
      output_created: typeof raw.output_created === "boolean" ? raw.output_created : undefined,
      real_assembly_executed:
        typeof raw.real_assembly_executed === "boolean" ? raw.real_assembly_executed : undefined,
      assembly_preflight: asRecord(raw.assembly_preflight),
      approval: asRecord(raw.approval),
    } as CategoryRuntimeSlot;
  }

  return {
    category_key: "assembly_generation",
    category_name: "assembly_generation",
    status: "planned",
    provider: "local_assembly_runtime",
  };
}

export function hasAssemblyGenerationSlot(
  status: RuntimeStatusResponse | null | undefined,
  legacyPanel?: Record<string, unknown>,
): boolean {
  const slots = resolveCategoryRuntimeSlots(status, legacyPanel);
  if (
    slots.some(
      (entry) => entry.category_key === "assembly_generation" || entry.category_key === "assembly",
    )
  ) {
    return true;
  }
  const runtime = asRecord(legacyPanel?.execution_runtime) || asRecord(status?.execution_runtime);
  const categoryRuntime = asRecord(runtime?.category_runtime);
  return Boolean(categoryRuntime?.assembly_generation || categoryRuntime?.assembly);
}

export function isAssemblyDryRunCompleted(slot: CategoryRuntimeSlot): boolean {
  const record = slot as Record<string, unknown>;
  const status = String(slot.status || "").toLowerCase();
  const dryRun = record.dry_run === true;
  const steps = Array.isArray(record.planned_steps) ? record.planned_steps : [];
  return status === "completed" && dryRun && steps.length >= 1;
}

export function resolveAssemblyRuntimeObservability(
  status: RuntimeStatusResponse | null | undefined,
  legacyPanel?: Record<string, unknown>,
): AssemblyRuntimeObservability {
  const slot = findAssemblyRuntimeSlot(status, legacyPanel);
  const slotRecord = slot as Record<string, unknown>;
  const preflight = slot.assembly_preflight || null;
  const assemblyRun = asRecord(slotRecord.assembly_run);
  const errorCode = readErrorCode(slot.error);
  const statusKey = String(slot.status || "planned").toLowerCase();

  const outputSummaryRecord = asRecord(slotRecord.output_summary);
  const inputSummaryRecord =
    asRecord(slotRecord.input_summary) || asRecord(preflight?.input_summary);

  const outputCreatedValue =
    typeof slotRecord.output_created === "boolean"
      ? slotRecord.output_created
      : typeof outputSummaryRecord?.output_created === "boolean"
        ? outputSummaryRecord.output_created
        : false;

  const realAssemblyExecutedValue =
    typeof slotRecord.real_assembly_executed === "boolean"
      ? slotRecord.real_assembly_executed
      : false;

  const plannedSteps = parsePlannedSteps(slotRecord.planned_steps);
  const warnings = [
    ...parseStringList(slotRecord.warnings),
    ...parseStringList(preflight?.warnings),
  ];
  const errors = parseStringList(slotRecord.errors);
  if (errorCode && !errors.includes(errorCode)) {
    const message = readErrorMessage(slot.error);
    errors.unshift(message ? `${errorCode} — ${message}` : errorCode);
  }

  const sessionId = status?.session_id ? String(status.session_id) : null;
  const expectedOutput = dash(
    (slotRecord.expected_output as string | undefined) ||
      (outputSummaryRecord?.expected_output as string | undefined) ||
      EXPECTED_ASSEMBLY_OUTPUT,
  );
  const expectedOutputPath = resolveExpectedOutputPath(slot, sessionId);

  const showPlannedSteps =
    statusKey === "completed" || statusKey === "running" || plannedSteps.length > 0;
  const showExpectedOutput =
    statusKey !== "planned" || Boolean(slotRecord.expected_output || outputSummaryRecord);
  const isGeneratedOutput = outputCreatedValue === true;

  const approval = asRecord(slot.approval);
  const blockedReasons = Array.isArray(approval?.assembly_blocked_reasons)
    ? approval.assembly_blocked_reasons.map(String)
    : [];
  const approvalStateKey = String(approval?.approval_state || "not_required").toLowerCase();
  const approvalGloballyDisabledNote =
    approvalStateKey === "approved" &&
    blockedReasons.some((code) =>
      ["ASSEMBLY_REAL_EXECUTION_DISABLED", "ASSEMBLY_RUNTIME_EXECUTION_DISABLED"].includes(code),
    )
      ? "Assembly is approved for this session, but real FFmpeg execution is globally disabled."
      : "";

  const validationStatusKey = String(
    slot.validation_status || preflight?.validation_status || "",
  ).toUpperCase();
  const dryRunCompleted = isAssemblyDryRunCompleted(slot);
  const hasAssemblySlot = hasAssemblyGenerationSlot(status, legacyPanel);
  const assemblyRunning = statusKey === "running";

  return {
    category_key: "assembly_generation",
    status: statusKey,
    statusLabel: formatAssemblyStatusLabel(statusKey, errorCode),
    statusClassName: categoryStatusClass(statusKey, errorCode),
    provider: dash(slot.provider || "local_assembly_runtime"),
    validationStatus: formatValidationStatus(
      slot.validation_status || (preflight?.validation_status ? String(preflight.validation_status) : null),
    ),
    assemblyMode: formatAssemblyMode(slot.assembly_mode),
    subtitleMode: formatSubtitleMode(slot.subtitle_mode),
    expectedOutput,
    expectedOutputPath,
    outputCreated: String(outputCreatedValue),
    realAssemblyExecuted: String(realAssemblyExecutedValue),
    plannedSteps,
    inputSummary: formatInputSummary(inputSummaryRecord),
    outputSummary: formatOutputSummary(outputSummaryRecord),
    warnings,
    errors,
    errorCode: dash(errorCode || undefined),
    errorMessage: dash(readErrorMessage(slot.error) || undefined),
    startedAt: dash((slot.started_at || assemblyRun?.started_at) as string | undefined),
    completedAt: dash((slot.completed_at || assemblyRun?.completed_at) as string | undefined),
    durationSeconds: formatDurationSeconds(resolveDurationSeconds(slot)),
    safetyNote: ASSEMBLY_SAFETY_COPY,
    noOutputNote: realAssemblyExecutedValue ? "" : ASSEMBLY_NO_OUTPUT_COPY,
    showPlannedSteps,
    showExpectedOutput,
    isGeneratedOutput,
    approvalRequired:
      typeof approval?.approval_required === "boolean" ? String(approval.approval_required) : "—",
    approvalState: formatApprovalState(approval?.approval_state as string | undefined),
    approvalExpiresAt: dash(approval?.approval_expires_at as string | undefined),
    estimatedRuntimeSeconds: formatDurationSeconds(
      typeof approval?.estimated_runtime_seconds === "number"
        ? approval.estimated_runtime_seconds
        : null,
    ),
    estimatedOutputSize: formatBytesEstimate(
      typeof approval?.estimated_output_size === "number" ? approval.estimated_output_size : null,
    ),
    estimatedDiskUsage: formatBytesEstimate(
      typeof approval?.estimated_disk_usage === "number" ? approval.estimated_disk_usage : null,
    ),
    assemblyEligible:
      typeof approval?.assembly_eligible === "boolean" ? String(approval.assembly_eligible) : "—",
    assemblyBlockedReasons: blockedReasons,
    showApprovalSection: Boolean(approval),
    approvalGloballyDisabledNote,
    approvalStateKey,
    validationStatusKey,
    dryRunCompleted,
    hasAssemblySlot,
    assemblyRunning,
    defaultTtlMinutes: 30,
    plannedStepsCount: plannedSteps.length,
  };
}

export function uiContainsAssemblyForbiddenActions(source: string): boolean {
  const lowered = source.toLowerCase();
  const forbidden = [
    "run assembly",
    "generate final video",
    "export final video",
    "send to assembly",
    "burn in",
  ];
  const hasButton = lowered.includes("<button");
  if (!hasButton) {
    return (
      (lowered.includes("ffmpeg") && lowered.includes("assembly")) ||
      forbidden.some((term) => lowered.includes(term))
    );
  }
  return forbidden.some((term) => lowered.includes(term)) || lowered.includes("ffmpeg");
}
