import { RuntimeStatusResponse } from "../api/client";

export type FailoverAdvisory = {
  advisory_only?: boolean;
  advisory_version?: string;
  failover_recommended?: boolean;
  failover_allowed?: boolean;
  reason?: string;
  blocked_reason?: string | null;
  preferred_next_provider?: string | null;
  current_provider?: string | null;
  cost_warning?: string | null;
  capability_match?: boolean;
  partial_artifacts_present?: boolean;
  partial_artifacts_safe_to_reuse?: boolean;
  partial_artifact_count?: number;
  provider_selection?: {
    selected_provider?: string | null;
    ranked_candidates?: string[];
    warnings?: string[];
    engine_version?: string;
  };
  failover_plan?: {
    policy_id?: string;
    chain?: string[];
    warnings?: string[];
  };
};

export function resolveFailoverAdvisory(status: RuntimeStatusResponse | null): FailoverAdvisory | null {
  const runtime = status?.execution_runtime as Record<string, unknown> | undefined;
  const operations = runtime?.operations as Record<string, unknown> | undefined;
  const advisory = operations?.failover_advisory;
  if (!advisory || typeof advisory !== "object") {
    return null;
  }
  return advisory as FailoverAdvisory;
}

export function formatBooleanFlag(value: boolean | undefined | null): string {
  if (value === true) {
    return "Yes";
  }
  if (value === false) {
    return "No";
  }
  return "—";
}
