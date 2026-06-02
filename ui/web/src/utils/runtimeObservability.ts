import { RuntimeStatusResponse } from "../api/client";

export const RUNTIME_POLL_STATES = new Set(["DISPATCHED", "RUNNING"]);
export const RUNTIME_TERMINAL_STATES = new Set(["COMPLETED", "FAILED"]);

export function normalizeRuntimeState(value: string | null | undefined): string {
  return String(value || "")
    .trim()
    .toUpperCase();
}

export function shouldPollRuntimeStatus(state: string | null | undefined): boolean {
  return RUNTIME_POLL_STATES.has(normalizeRuntimeState(state));
}

export function isTerminalRuntimeState(state: string | null | undefined): boolean {
  return RUNTIME_TERMINAL_STATES.has(normalizeRuntimeState(state));
}

export function formatDurationSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) {
    return "—";
  }
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  if (minutes > 0) {
    return `${minutes}m ${remainder}s`;
  }
  return `${remainder}s`;
}

export function formatProviderMode(
  family: string | null | undefined,
  mode: string | null | undefined,
): string {
  const provider = family || "—";
  const executionMode = mode || "—";
  if (provider === "—" && executionMode === "—") {
    return "—";
  }
  if (executionMode === "—") {
    return provider;
  }
  return `${provider} · ${executionMode}`;
}

export function gateStatus(
  passed: boolean | null | undefined,
  unknownLabel = "—",
): { label: string; className: string } {
  if (passed === true) {
    return { label: "PASSED", className: "runtime-gate runtime-gate-pass" };
  }
  if (passed === false) {
    return { label: "FAILED", className: "runtime-gate runtime-gate-fail" };
  }
  return { label: unknownLabel, className: "runtime-gate runtime-gate-unknown" };
}

export function resolveValidationBlock(status: RuntimeStatusResponse | null): Record<string, unknown> | null {
  const operations = (status?.execution_runtime as Record<string, unknown> | undefined)?.operations;
  if (operations && typeof operations === "object") {
    const validation = (operations as Record<string, unknown>).validation;
    if (validation && typeof validation === "object") {
      return validation as Record<string, unknown>;
    }
  }
  return null;
}

export function resolveArtifacts(status: RuntimeStatusResponse | null): Array<Record<string, unknown>> {
  const runtime = status?.execution_runtime as Record<string, unknown> | undefined;
  const byCategory = runtime?.artifacts_by_category as Record<string, unknown> | undefined;
  const clips = byCategory?.video_generation;
  if (!Array.isArray(clips)) {
    return [];
  }
  return clips.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null);
}

export function truncateHash(value: string | null | undefined, length = 16): string {
  if (!value) {
    return "—";
  }
  const text = String(value);
  if (text.length <= length + 3) {
    return text;
  }
  return `${text.slice(0, length)}…`;
}

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
}
