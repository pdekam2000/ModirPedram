import { RuntimeStatusResponse } from "../api/client";
import { formatDurationSeconds } from "./runtimeObservability";
import {
  CategoryRuntimeSlot,
  categoryStatusClass,
  resolveCategoryRuntimeSlots,
} from "./categoryRuntimeShell";

export const SUBTITLE_SAFETY_COPY = "Subtitle files only — no video burn-in yet.";

export const SUBTITLE_STATUS_LABELS: Record<string, string> = {
  planned: "Not started",
  pending: "Ready",
  running: "Generating subtitles",
  completed: "Subtitles ready",
  failed: "Failed",
  skipped: "No subtitle source",
  cancelled: "Cancelled",
};

export const SUBTITLE_SOURCE_TYPE_LABELS: Record<string, string> = {
  narration_text_only: "Narration text",
  narration_with_timing: "Voice manifest timing",
  unavailable: "No source",
};

export const SUBTITLE_TIMING_LABELS: Record<string, string> = {
  equal_chunk: "Equal chunk (estimated)",
  audio_duration: "Audio duration (voice manifest)",
  auto: "Auto",
};

export const EXPECTED_SUBTITLE_FILES = [
  { format: "srt", file_name: "subtitles.srt" },
  { format: "vtt", file_name: "subtitles.vtt" },
  { format: "ass", file_name: "subtitles.ass" },
  { format: "manifest", file_name: "subtitle_manifest.json" },
] as const;

export type SubtitleArtifactRow = {
  format: string;
  file_name: string;
  file_path: string;
  validation_status: string;
  size_bytes: string;
};

export type SubtitleRuntimeObservability = {
  category_key: "subtitle_generation";
  status: string;
  statusLabel: string;
  statusClassName: string;
  provider: string;
  sourceType: string;
  sourceReady: string;
  timingStrategy: string;
  cueCount: string;
  formatsWritten: string;
  validationStatus: string;
  manifestPath: string;
  startedAt: string;
  completedAt: string;
  durationSeconds: string;
  runtimeNotes: string;
  errorCode: string;
  errorMessage: string;
  executed: string;
  dryRun: string;
  artifacts: SubtitleArtifactRow[];
  safetyNote: string;
  showArtifactSection: boolean;
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
  const record = asRecord(error);
  return record?.code ? String(record.code) : "";
}

function readErrorMessage(error: unknown): string {
  const record = asRecord(error);
  return record?.message ? String(record.message) : "";
}

function formatSourceType(value: string | null | undefined): string {
  const key = String(value || "").toLowerCase();
  return SUBTITLE_SOURCE_TYPE_LABELS[key] || dash(value || undefined);
}

function formatTimingStrategy(value: string | null | undefined): string {
  const key = String(value || "").toLowerCase();
  return SUBTITLE_TIMING_LABELS[key] || dash(value || undefined);
}

export function formatSubtitleStatusLabel(
  status: string | null | undefined,
  errorCode?: string | null,
): string {
  const key = String(status || "planned").toLowerCase();
  if (key === "failed" && String(errorCode || "").toUpperCase() === "SOURCE_NOT_READY") {
    return "No subtitle source";
  }
  return SUBTITLE_STATUS_LABELS[key] || key;
}

export function findSubtitleRuntimeSlot(
  status: RuntimeStatusResponse | null | undefined,
  legacyPanel?: Record<string, unknown>,
): CategoryRuntimeSlot {
  const slots = resolveCategoryRuntimeSlots(status, legacyPanel);
  const fromSlots =
    slots.find((slot) => slot.category_key === "subtitle_generation") ||
    slots.find((slot) => slot.category_key === "subtitles");

  if (fromSlots) {
    return {
      ...fromSlots,
      category_key: "subtitle_generation",
      category_name: "subtitle_generation",
    };
  }

  const runtime = asRecord(legacyPanel?.execution_runtime) || asRecord(status?.execution_runtime);
  const categoryRuntime = asRecord(runtime?.category_runtime);
  const raw =
    asRecord(categoryRuntime?.subtitle_generation) || asRecord(categoryRuntime?.subtitles);

  if (raw) {
    return {
      category_key: "subtitle_generation",
      category_name: "subtitle_generation",
      status: String(raw.status || "planned"),
      provider: raw.provider ? String(raw.provider) : "local_subtitle_runtime",
      artifacts: Array.isArray(raw.artifacts) ? raw.artifacts : [],
      error: raw.error ?? null,
      started_at: raw.started_at ? String(raw.started_at) : null,
      completed_at: raw.completed_at ? String(raw.completed_at) : null,
      duration_seconds: typeof raw.duration_seconds === "number" ? raw.duration_seconds : null,
      runtime_notes: Array.isArray(raw.runtime_notes) ? raw.runtime_notes.map(String) : [],
      executed: typeof raw.executed === "boolean" ? raw.executed : undefined,
      dry_run: typeof raw.dry_run === "boolean" ? raw.dry_run : undefined,
      source_type: raw.source_type ? String(raw.source_type) : null,
      source_ready: typeof raw.source_ready === "boolean" ? raw.source_ready : undefined,
      timing_strategy: raw.timing_strategy ? String(raw.timing_strategy) : null,
      cue_count: typeof raw.cue_count === "number" ? raw.cue_count : null,
      formats_written: Array.isArray(raw.formats_written) ? raw.formats_written.map(String) : undefined,
      manifest_path: raw.manifest_path ? String(raw.manifest_path) : null,
      validation_status: raw.validation_status ? String(raw.validation_status) : null,
      subtitle_preflight: asRecord(raw.subtitle_preflight),
    };
  }

  return {
    category_key: "subtitle_generation",
    category_name: "subtitle_generation",
    status: "planned",
    provider: "local_subtitle_runtime",
  };
}

function artifactRecordFromRaw(raw: unknown): SubtitleArtifactRow | null {
  const record = asRecord(raw);
  if (!record) {
    return null;
  }
  const fileName = String(record.file_name || "");
  const filePath = String(record.file_path || "");
  if (!fileName && !filePath) {
    return null;
  }
  return {
    format: String(record.format || fileName.split(".").pop() || "unknown"),
    file_name: fileName || filePath.split(/[/\\]/).pop() || "—",
    file_path: dash(filePath || undefined),
    validation_status: dash(
      record.validation_status ? String(record.validation_status) : undefined,
    ),
    size_bytes:
      typeof record.size_bytes === "number" ? String(record.size_bytes) : "—",
  };
}

function resolveArtifactRows(
  slot: CategoryRuntimeSlot,
  legacyPanel?: Record<string, unknown>,
  status?: RuntimeStatusResponse | null,
): SubtitleArtifactRow[] {
  const slotArtifacts = Array.isArray(slot.artifacts)
    ? slot.artifacts.map(artifactRecordFromRaw).filter(Boolean)
    : [];

  const runtime = asRecord(legacyPanel?.execution_runtime) || asRecord(status?.execution_runtime);
  const byCategory = asRecord(runtime?.artifacts_by_category);
  const categoryArtifacts = [
    ...(Array.isArray(byCategory?.subtitle_generation) ? byCategory.subtitle_generation : []),
    ...(Array.isArray(byCategory?.subtitles) ? byCategory.subtitles : []),
  ]
    .map(artifactRecordFromRaw)
    .filter(Boolean) as SubtitleArtifactRow[];

  const merged = new Map<string, SubtitleArtifactRow>();
  for (const row of [...slotArtifacts, ...categoryArtifacts]) {
    if (row) {
      merged.set(row.file_name.toLowerCase(), row);
    }
  }

  const manifestPath = slot.manifest_path || null;
  const manifestDir =
    manifestPath && manifestPath.includes("/")
      ? manifestPath.replace(/[/\\][^/\\]+$/, "")
      : manifestPath && manifestPath.includes("\\")
        ? manifestPath.replace(/\\[^\\]+$/, "")
        : null;

  for (const expected of EXPECTED_SUBTITLE_FILES) {
    if (merged.has(expected.file_name)) {
      continue;
    }
    const matched = [...merged.values()].find((row) =>
      row.file_name.toLowerCase().endsWith(expected.file_name),
    );
    if (matched) {
      merged.set(expected.file_name, matched);
      continue;
    }
    if (manifestDir && slot.status === "completed") {
      merged.set(expected.file_name, {
        format: expected.format,
        file_name: expected.file_name,
        file_path: `${manifestDir}/${expected.file_name}`.replace(/\\/g, "/"),
        validation_status: "—",
        size_bytes: "—",
      });
    }
  }

  return EXPECTED_SUBTITLE_FILES.map((expected) => {
    return (
      merged.get(expected.file_name) || {
        format: expected.format,
        file_name: expected.file_name,
        file_path: "—",
        validation_status: "—",
        size_bytes: "—",
      }
    );
  });
}

export function resolveSubtitleRuntimeObservability(
  status: RuntimeStatusResponse | null | undefined,
  legacyPanel?: Record<string, unknown>,
): SubtitleRuntimeObservability {
  const slot = findSubtitleRuntimeSlot(status, legacyPanel);
  const preflight = slot.subtitle_preflight || null;
  const errorCode = readErrorCode(slot.error);
  const statusKey = String(slot.status || "planned").toLowerCase();

  const sourceTypeRaw =
    slot.source_type ||
    (preflight?.source_type ? String(preflight.source_type) : null);
  const sourceReadyValue =
    typeof slot.source_ready === "boolean"
      ? slot.source_ready
      : typeof preflight?.source_ready === "boolean"
        ? preflight.source_ready
        : null;

  const formatsWritten =
    Array.isArray(slot.formats_written) && slot.formats_written.length > 0
      ? slot.formats_written.join(", ")
      : "—";

  const cueCount =
    typeof slot.cue_count === "number"
      ? slot.cue_count
      : Array.isArray(slot.artifacts) && slot.artifacts.length > 0
        ? (asRecord(slot.artifacts[0])?.cue_count as number | undefined)
        : null;

  const runtimeNotes = (slot.runtime_notes || []).filter(Boolean);

  const executedValue =
    typeof slot.executed === "boolean" ? slot.executed : null;
  const dryRunValue = typeof slot.dry_run === "boolean" ? slot.dry_run : null;

  const artifacts = resolveArtifactRows(slot, legacyPanel, status);
  const hasIndexedArtifacts = artifacts.some((row) => row.file_path !== "—");
  const showArtifactSection =
    statusKey === "completed" || statusKey === "running" || hasIndexedArtifacts;

  return {
    category_key: "subtitle_generation",
    status: statusKey,
    statusLabel: formatSubtitleStatusLabel(statusKey, errorCode),
    statusClassName: categoryStatusClass(statusKey, errorCode),
    provider: dash(slot.provider || "local_subtitle_runtime"),
    sourceType: formatSourceType(sourceTypeRaw),
    sourceReady: sourceReadyValue === null ? "—" : String(sourceReadyValue),
    timingStrategy: formatTimingStrategy(slot.timing_strategy),
    cueCount: cueCount === null ? "—" : String(cueCount),
    formatsWritten,
    validationStatus: dash(slot.validation_status || undefined),
    manifestPath: dash(slot.manifest_path || undefined),
    startedAt: dash(slot.started_at || undefined),
    completedAt: dash(slot.completed_at || undefined),
    durationSeconds: formatDurationSeconds(slot.duration_seconds),
    runtimeNotes: runtimeNotes.length > 0 ? runtimeNotes.join(" · ") : "—",
    errorCode: dash(errorCode || undefined),
    errorMessage: dash(readErrorMessage(slot.error) || undefined),
    executed: executedValue === null ? "—" : String(executedValue),
    dryRun: dryRunValue === null ? "—" : String(dryRunValue),
    artifacts,
    safetyNote: SUBTITLE_SAFETY_COPY,
    showArtifactSection,
  };
}

export function uiContainsSubtitleForbiddenActions(source: string): boolean {
  const lowered = source.toLowerCase();
  const forbidden = [
    "burn in",
    "burn-in",
    "burn subtitles",
    "send to assembly",
    "assemble video",
    "run subtitles",
    "regenerate subtitles",
  ];
  const hasButton = lowered.includes("<button");
  if (!hasButton) {
    return lowered.includes("ffmpeg") && lowered.includes("subtitle");
  }
  return forbidden.some((term) => lowered.includes(term));
}
