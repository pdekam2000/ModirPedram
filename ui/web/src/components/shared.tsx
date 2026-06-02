import type { ReactNode } from "react";
import { PanelDTO } from "../api/client";

export function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function statusClass(status: string): string {
  return `status status-${status.toLowerCase().replace(/\s+/g, "_")}`;
}

export function panelStatusClass(status: string): string {
  return `panel-status panel-status-${status}`;
}

type PanelCardProps = {
  title: string;
  panel: PanelDTO;
  children: ReactNode;
};

export function PanelCard({ title, panel, children }: PanelCardProps) {
  const isEmpty = panel.status === "missing" || panel.completeness <= 0;

  return (
    <section className={`domain-card ${isEmpty ? "domain-card-empty" : ""}`}>
      <div className="domain-card-header">
        <div>
          <h3>{title}</h3>
          <span className={panelStatusClass(panel.status)}>{panel.status}</span>
        </div>
        <span className="completeness-pill">{Math.round(panel.completeness * 100)}%</span>
      </div>

      {panel.warnings.length > 0 && (
        <ul className="panel-warnings">
          {panel.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      {isEmpty ? (
        <p className="empty-state">No data recorded yet. Future Phase 9D–9F writers will populate this panel.</p>
      ) : (
        <div className="panel-body">{children}</div>
      )}

      {Object.keys(panel.metadata).length > 0 && (
        <details className="panel-meta">
          <summary>Metadata</summary>
          <pre>{JSON.stringify(panel.metadata, null, 2)}</pre>
        </details>
      )}
    </section>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={statusClass(status)}>{status}</span>;
}

export function CollapsibleJson({ value, label = "Raw JSON" }: { value: unknown; label?: string }) {
  return (
    <details className="json-details">
      <summary>{label}</summary>
      <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

export function KeyValue({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="kv">
      <span className="label">{label}</span>
      <span>{value ?? "—"}</span>
    </div>
  );
}

export function renderExtraData(data: Record<string, unknown>, knownKeys: string[]) {
  const extras = Object.entries(data).filter(
    ([key, value]) => !knownKeys.includes(key) && value !== null && value !== undefined,
  );
  if (extras.length === 0) {
    return null;
  }
  return (
    <details className="panel-meta">
      <summary>Additional fields</summary>
      <pre>{JSON.stringify(Object.fromEntries(extras), null, 2)}</pre>
    </details>
  );
}
