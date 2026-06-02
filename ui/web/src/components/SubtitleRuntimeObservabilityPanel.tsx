import { RuntimeStatusResponse } from "../api/client";
import { KeyValue } from "./shared";
import { formatBytes } from "../utils/runtimeObservability";
import { resolveSubtitleRuntimeObservability } from "../utils/subtitleRuntimeObservability";

type Props = {
  status: RuntimeStatusResponse | null;
  legacyPanel?: Record<string, unknown>;
  compact?: boolean;
};

export function SubtitleRuntimeObservabilityPanel({
  status,
  legacyPanel,
  compact = false,
}: Props) {
  const subtitle = resolveSubtitleRuntimeObservability(status, legacyPanel);

  return (
    <section
      className={`subtitle-runtime-observability ${compact ? "subtitle-runtime-observability-compact" : ""}`}
    >
      <h4>Subtitle runtime</h4>
      <p className="muted subtitle-runtime-note">{subtitle.safetyNote}</p>

      <div className="subtitle-runtime-head">
        <strong>{subtitle.category_key}</strong>
        <span className={subtitle.statusClassName}>{subtitle.statusLabel}</span>
      </div>

      <div className="kv-grid kv-grid-tight">
        <KeyValue label="Status" value={subtitle.status} />
        <KeyValue label="Provider" value={subtitle.provider} />
        <KeyValue label="Source type" value={subtitle.sourceType} />
        <KeyValue label="Source ready" value={subtitle.sourceReady} />
        {!compact && (
          <>
            <KeyValue label="Timing strategy" value={subtitle.timingStrategy} />
            <KeyValue label="Cue count" value={subtitle.cueCount} />
            <KeyValue label="Formats written" value={subtitle.formatsWritten} />
            <KeyValue label="Validation status" value={subtitle.validationStatus} />
            <KeyValue
              label="Manifest path"
              value={
                subtitle.manifestPath !== "—" ? (
                  <span className="mono" title={subtitle.manifestPath}>
                    {subtitle.manifestPath}
                  </span>
                ) : (
                  "—"
                )
              }
            />
            <KeyValue label="Started" value={subtitle.startedAt} />
            <KeyValue label="Completed" value={subtitle.completedAt} />
            <KeyValue label="Duration" value={subtitle.durationSeconds} />
            <KeyValue label="Executed" value={subtitle.executed} />
            <KeyValue label="Dry run" value={subtitle.dryRun} />
            <KeyValue label="Runtime notes" value={subtitle.runtimeNotes} />
            <KeyValue label="Error code" value={subtitle.errorCode} />
            <KeyValue label="Error message" value={subtitle.errorMessage} />
          </>
        )}
      </div>

      {!compact && subtitle.showArtifactSection && (
        <div className="subtitle-artifact-section">
          <h5>Subtitle artifacts</h5>
          {subtitle.status === "completed" || subtitle.artifacts.some((a) => a.file_path !== "—") ? (
            <div className="subtitle-artifact-list">
              {subtitle.artifacts.map((artifact) => (
                <article key={artifact.file_name} className="subtitle-artifact-card">
                  <div className="subtitle-artifact-head">
                    <strong>{artifact.file_name}</strong>
                    <span className="subtitle-format-badge">{artifact.format.toUpperCase()}</span>
                  </div>
                  <div className="kv-grid kv-grid-tight">
                    <KeyValue
                      label="Path"
                      value={
                        artifact.file_path !== "—" ? (
                          <span className="mono" title={artifact.file_path}>
                            {artifact.file_path}
                          </span>
                        ) : (
                          "—"
                        )
                      }
                    />
                    <KeyValue label="Validation" value={artifact.validation_status} />
                    <KeyValue
                      label="Size"
                      value={
                        artifact.size_bytes !== "—"
                          ? formatBytes(Number(artifact.size_bytes))
                          : "—"
                      }
                    />
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="muted subtitle-runtime-note">No subtitle files generated yet.</p>
          )}
        </div>
      )}

      {!compact && subtitle.errorCode !== "—" && (
        <div className="subtitle-error-block" role="status">
          <strong>Error</strong>: {subtitle.errorCode}
          {subtitle.errorMessage !== "—" ? ` — ${subtitle.errorMessage}` : ""}
        </div>
      )}
    </section>
  );
}
