import { useEffect, useMemo, useState } from "react";
import {
  postTopicUniverseGenerate,
  postTopicUniverseHandoffE2E,
  postTopicUniverseOpenExport,
  fetchTopicUniversePreflight,
  TopicUniversePreflightResponse,
  TopicUniverseResult,
  TopicUniverseTitleEntry,
} from "../api/topicUniverseClient";

type FormState = {
  topic: string;
  language_code: string;
  platform: string;
  audience_level: string;
  niche_style: string;
  title_target: number;
  use_live_trends: boolean;
  suggested_duration: number;
};

const DEFAULT_FORM: FormState = {
  topic: "fishing",
  language_code: "",
  platform: "youtube_shorts",
  audience_level: "general",
  niche_style: "general",
  title_target: 100,
  use_live_trends: true,
  suggested_duration: 30,
};

function copyText(value: string) {
  void navigator.clipboard.writeText(value);
}

export function TopicUniverseStudioPage() {
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [running, setRunning] = useState(false);
  const [handoffRunning, setHandoffRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [handoffMessage, setHandoffMessage] = useState<string | null>(null);
  const [result, setResult] = useState<TopicUniverseResult | null>(null);
  const [selectedTitleId, setSelectedTitleId] = useState<string>("");
  const [preflight, setPreflight] = useState<TopicUniversePreflightResponse | null>(null);
  const [filterSubtopic, setFilterSubtopic] = useState("");
  const [copiedId, setCopiedId] = useState<string>("");

  const titles = useMemo(() => result?.title_bank?.titles || [], [result]);
  const subtopics = useMemo(
    () => [...new Set(titles.map((item) => item.subtopic))].sort(),
    [titles],
  );
  const filteredTitles = useMemo(() => {
    if (!filterSubtopic) {
      return titles;
    }
    return titles.filter((item) => item.subtopic === filterSubtopic);
  }, [titles, filterSubtopic]);

  const selectedTitle = titles.find((item) => item.title_id === selectedTitleId) || null;

  useEffect(() => {
    void fetchTopicUniversePreflight().then(setPreflight).catch(() => setPreflight(null));
  }, []);

  async function generateBank() {
    setRunning(true);
    setError(null);
    setHandoffMessage(null);
    try {
      const response = await postTopicUniverseGenerate({
        topic: form.topic.trim(),
        language_code: form.language_code.trim() || null,
        platform: form.platform,
        audience_level: form.audience_level,
        niche_style: form.niche_style,
        title_target: Number(form.title_target),
        use_live_trends: form.use_live_trends,
        suggested_duration: Number(form.suggested_duration),
      });
      setResult(response.result);
      setSelectedTitleId(response.result.title_bank.titles[0]?.title_id || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
      setResult(null);
    } finally {
      setRunning(false);
    }
  }

  async function sendSelectedToE2E(title?: TopicUniverseTitleEntry) {
    const entry = title || selectedTitle;
    if (!entry || !result) {
      return;
    }
    setHandoffRunning(true);
    setHandoffMessage(null);
    setError(null);
    try {
      const response = await postTopicUniverseHandoffE2E({
        selected_title: entry.title,
        source_run_id: result.run_id,
        duration_seconds: entry.suggested_duration || form.suggested_duration,
        platform: form.platform,
        niche: form.niche_style,
        mood: "instructional",
      });
      setHandoffMessage(
        `${response.message} Run ID: ${String((response.result as Record<string, unknown>).run_id || "—")}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Handoff failed");
    } finally {
      setHandoffRunning(false);
    }
  }

  async function openExportFolder() {
    try {
      const exportPath = result?.export_paths?.json
        ? result.export_paths.json.replace(/[/\\][^/\\]+$/, "")
        : undefined;
      const response = await postTopicUniverseOpenExport(exportPath || null);
      setHandoffMessage(response.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open export folder.");
    }
  }

  function handleCopy(entry: TopicUniverseTitleEntry) {
    copyText(entry.title);
    setCopiedId(entry.title_id);
    window.setTimeout(() => setCopiedId(""), 1500);
  }

  return (
    <div className="cb-test-studio">
      <section className="card cb-test-preflight">
        <div className="card-header">
          <h2>Topic Universe Preflight</h2>
          {preflight && (
            <span className={`pill ${preflight.trend_mode === "live" ? "pill-live" : ""}`}>
              Trend: {preflight.trend_mode}
            </span>
          )}
        </div>
        <p className="muted">
          Broad topics expand into SEO title banks. Specific topics return one detailed video plan.
        </p>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Topic Universe / SEO Title Bank</h2>
          <span className="muted">Planning only · No Runway · No media</span>
        </div>
        <div className="cb-test-form-grid">
          <label>
            Topic / Category
            <textarea
              rows={2}
              value={form.topic}
              onChange={(event) => setForm({ ...form, topic: event.target.value })}
            />
          </label>
          <label>
            Language code (optional)
            <input
              placeholder="auto-detect"
              value={form.language_code}
              onChange={(event) => setForm({ ...form, language_code: event.target.value })}
            />
          </label>
          <label>
            Platform
            <select value={form.platform} onChange={(event) => setForm({ ...form, platform: event.target.value })}>
              <option value="youtube_shorts">youtube_shorts</option>
              <option value="tiktok">tiktok</option>
              <option value="instagram_reels">instagram_reels</option>
            </select>
          </label>
          <label>
            Title count target
            <input
              type="number"
              min={1}
              max={200}
              value={form.title_target}
              onChange={(event) => setForm({ ...form, title_target: Number(event.target.value) })}
            />
          </label>
          <label>
            Audience level
            <select
              value={form.audience_level}
              onChange={(event) => setForm({ ...form, audience_level: event.target.value })}
            >
              <option value="general">general</option>
              <option value="beginner">beginner</option>
              <option value="intermediate">intermediate</option>
              <option value="advanced">advanced</option>
            </select>
          </label>
          <label>
            Niche style
            <input
              value={form.niche_style}
              onChange={(event) => setForm({ ...form, niche_style: event.target.value })}
            />
          </label>
          <label>
            Suggested duration (seconds)
            <input
              type="number"
              min={5}
              max={600}
              value={form.suggested_duration}
              onChange={(event) => setForm({ ...form, suggested_duration: Number(event.target.value) })}
            />
          </label>
          <label className="cb-test-checkbox-row">
            <input
              type="checkbox"
              checked={form.use_live_trends}
              onChange={(event) => setForm({ ...form, use_live_trends: event.target.checked })}
            />
            Use live trends when configured
          </label>
        </div>
        <div className="cb-test-actions">
          <button type="button" disabled={running || !form.topic.trim()} onClick={() => void generateBank()}>
            {running ? "Generating title bank…" : "Generate Title Bank"}
          </button>
          <button type="button" onClick={() => void openExportFolder()}>
            Open Export Folder
          </button>
          <button
            type="button"
            disabled={!selectedTitle || handoffRunning}
            onClick={() => void sendSelectedToE2E()}
          >
            {handoffRunning ? "Running E2E…" : "Send Selected Title to E2E Test"}
          </button>
        </div>
        {error && <div className="error-banner">{error}</div>}
        {handoffMessage && <p className="muted success-text">{handoffMessage}</p>}
      </section>

      {result && (
        <>
          <section className="card">
            <div className="card-header">
              <h2>Title Bank Summary</h2>
              <span className="muted mono">{result.run_id}</span>
            </div>
            <div className="cb-test-meta-row">
              <span className="cb-test-meta-chip">Scope: {String(result.title_bank.scope?.scope || "—")}</span>
              <span className="cb-test-meta-chip">Mode: {result.title_bank.mode}</span>
              <span className="cb-test-meta-chip">Trend: {result.title_bank.trend_mode}</span>
              <span className="cb-test-meta-chip">
                Titles: {result.title_bank.title_count} / {result.title_bank.title_target}
              </span>
            </div>
            {(result.title_bank.notes || []).map((note) => (
              <p key={note} className="muted">
                {note}
              </p>
            ))}
            {result.export_paths?.latest_json && (
              <p className="muted export-path">Export: {result.export_paths.latest_json}</p>
            )}
          </section>

          <section className="card">
            <div className="card-header">
              <h2>Title Table</h2>
              <label className="cb-test-filter">
                Subtopic
                <select value={filterSubtopic} onChange={(event) => setFilterSubtopic(event.target.value)}>
                  <option value="">All subtopics</option>
                  {subtopics.map((subtopic) => (
                    <option key={subtopic} value={subtopic}>
                      {subtopic}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="cb-test-title-table-wrap">
              <table className="cb-test-title-table">
                <thead>
                  <tr>
                    <th>Select</th>
                    <th>Title</th>
                    <th>Subtopic</th>
                    <th>Intent</th>
                    <th>Trend</th>
                    <th>Source</th>
                    <th>Strategy</th>
                    <th>Duplicate</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTitles.map((entry) => (
                    <tr key={entry.title_id} className={selectedTitleId === entry.title_id ? "selected" : ""}>
                      <td>
                        <input
                          type="radio"
                          name="selected-title"
                          checked={selectedTitleId === entry.title_id}
                          onChange={() => setSelectedTitleId(entry.title_id)}
                        />
                      </td>
                      <td>{entry.title}</td>
                      <td>{entry.subtopic}</td>
                      <td>{entry.intent}</td>
                      <td>{entry.trend_score.toFixed(2)}</td>
                      <td>{entry.source_provider}</td>
                      <td>{entry.content_strategy}</td>
                      <td>{entry.duplicate_status}</td>
                      <td className="cb-test-title-actions">
                        <button type="button" onClick={() => handleCopy(entry)}>
                          {copiedId === entry.title_id ? "Copied" : "Copy"}
                        </button>
                        <button type="button" onClick={() => void sendSelectedToE2E(entry)}>
                          E2E
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
