import { SessionOverview } from "../api/client";
import { formatScore } from "./shared";

type Props = {
  overview: SessionOverview | null;
  loading: boolean;
  runtimeOverview?: {
    runtime_active_count?: number;
    runtime_stale_count?: number;
  };
};

const cards: Array<{
  key: keyof SessionOverview;
  label: string;
  format?: (value: SessionOverview) => string;
}> = [
  { key: "active_sessions_count", label: "Active Sessions" },
  { key: "archived_sessions_count", label: "Archived Sessions" },
  { key: "total_sessions", label: "Total Sessions" },
  { key: "simulated_count", label: "Simulated" },
  { key: "approved_count", label: "Approved" },
  { key: "blocked_count", label: "Blocked" },
  { key: "failed_count", label: "Failed" },
  { key: "runtime_active_count", label: "Runtime Active" },
  { key: "runtime_stale_count", label: "Runtime Stale" },
  {
    key: "avg_story_quality_score",
    label: "Avg Story Quality",
    format: (o) => formatScore(o.avg_story_quality_score),
  },
  {
    key: "avg_execution_confidence",
    label: "Avg Confidence",
    format: (o) => formatScore(o.avg_execution_confidence),
  },
];

export function OverviewCards({ overview, loading, runtimeOverview }: Props) {
  const mergedOverview = overview
    ? {
        ...overview,
        active_sessions_count: overview.active_sessions_count ?? overview.total_sessions,
        archived_sessions_count: overview.archived_sessions_count ?? 0,
        runtime_active_count:
          runtimeOverview?.runtime_active_count ?? overview.runtime_active_count ?? 0,
        runtime_stale_count:
          runtimeOverview?.runtime_stale_count ?? overview.runtime_stale_count ?? 0,
      }
    : null;

  return (
    <section className="overview-grid">
      {cards.map((card) => {
        const raw = mergedOverview ? mergedOverview[card.key as keyof SessionOverview] : null;
        const value =
          card.format && mergedOverview
            ? card.format(mergedOverview)
            : raw === null || raw === undefined
              ? loading
                ? "…"
                : "—"
              : String(raw);

        return (
          <article key={card.key} className="metric-card">
            <span className="metric-label">{card.label}</span>
            <strong className="metric-value">{value}</strong>
          </article>
        );
      })}
    </section>
  );
}
