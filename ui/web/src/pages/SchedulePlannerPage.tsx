import { useState } from "react";
import { generateScheduleJobs, previewSchedule, saveSchedule } from "../api/productClient";
import { PLATFORM_OPTIONS } from "../product/constants";

const today = new Date().toISOString().slice(0, 10);
const weekLater = new Date(Date.now() + 6 * 86400000).toISOString().slice(0, 10);

export function SchedulePlannerPage() {
  const [title, setTitle] = useState("Daily Channel Plan");
  const [mode, setMode] = useState("daily");
  const [videosPerDay, setVideosPerDay] = useState(1);
  const [durationSeconds, setDurationSeconds] = useState(30);
  const [topicSource, setTopicSource] = useState("channel");
  const [customTopic, setCustomTopic] = useState("");
  const [topicList, setTopicList] = useState("idea 1\nidea 2\nidea 3");
  const [platforms, setPlatforms] = useState<string[]>(["tiktok", "instagram_reels", "youtube_shorts"]);
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(weekLater);
  const [runTime, setRunTime] = useState("09:00");
  const [enabled, setEnabled] = useState(true);
  const [scheduleId, setScheduleId] = useState("");
  const [preview, setPreview] = useState<{ job_count: number; jobs_preview: Record<string, unknown>[] } | null>(null);
  const [jobs, setJobs] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState<string | null>(null);

  function body() {
    return {
      schedule_id: scheduleId,
      title,
      mode,
      videos_per_day: videosPerDay,
      duration_seconds: durationSeconds,
      topic_source: topicSource,
      custom_topic: customTopic,
      topic_list: topicList.split("\n").map((line) => line.trim()).filter(Boolean),
      platforms,
      provider: "runway",
      start_date: startDate,
      end_date: endDate,
      run_time: runTime,
      enabled,
    };
  }

  function togglePlatform(id: string) {
    setPlatforms((current) => (current.includes(id) ? current.filter((p) => p !== id) : [...current, id]));
  }

  async function handlePreview() {
    setError(null);
    try {
      const result = await previewSchedule(body());
      setPreview(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    }
  }

  async function handleSave() {
    setError(null);
    try {
      const saved = await saveSchedule(body());
      setScheduleId(String(saved.schedule_id || ""));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  async function handleGenerateToday() {
    if (!scheduleId) {
      setError("Save schedule first");
      return;
    }
    setError(null);
    try {
      const result = await generateScheduleJobs(scheduleId, today);
      setJobs(result.jobs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generate jobs failed");
    }
  }

  async function handleDisable() {
    if (!scheduleId) return;
    setEnabled(false);
  }

  return (
    <div className="product-page">
      <header className="header">
        <div>
          <p className="eyebrow">Schedule Planner</p>
          <h1>Automatic Video Schedule</h1>
          <p className="subtitle">Planning foundation only — creates planned jobs, not background generation.</p>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <div className="product-form-grid">
        <section className="card">
          <h2>Plan</h2>
          <input className="filter-input full-width" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Plan name" />
          <select className="filter-input full-width" value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly (Mon–Fri)</option>
            <option value="monthly">Monthly</option>
            <option value="custom">Custom range</option>
          </select>
          <label className="field-row">Videos per day<input className="filter-input" type="number" min={1} value={videosPerDay} onChange={(e) => setVideosPerDay(Number(e.target.value))} /></label>
          <label className="field-row">Duration (seconds)<input className="filter-input" type="number" min={6} value={durationSeconds} onChange={(e) => setDurationSeconds(Number(e.target.value))} /></label>
        </section>

        <section className="card">
          <h2>Topic Source</h2>
          <select className="filter-input full-width" value={topicSource} onChange={(e) => setTopicSource(e.target.value)}>
            <option value="channel">Channel niche/topic</option>
            <option value="custom">Custom topic</option>
            <option value="topic_list">Topic list</option>
          </select>
          {topicSource === "custom" && (
            <input className="filter-input full-width" value={customTopic} onChange={(e) => setCustomTopic(e.target.value)} placeholder="Custom topic" />
          )}
          {topicSource === "topic_list" && (
            <textarea className="filter-input full-width" rows={4} value={topicList} onChange={(e) => setTopicList(e.target.value)} />
          )}
        </section>

        <section className="card">
          <h2>Platforms & Dates</h2>
          <div className="chip-row">
            {PLATFORM_OPTIONS.filter((p) => p.id !== "multi").map((item) => (
              <button key={item.id} type="button" className={`chip-btn ${platforms.includes(item.id) ? "active" : ""}`} onClick={() => togglePlatform(item.id)}>
                {item.label}
              </button>
            ))}
          </div>
          <label className="field-row">Start<input className="filter-input" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></label>
          <label className="field-row">End<input className="filter-input" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></label>
          <label className="field-row">Time<input className="filter-input" type="time" value={runTime} onChange={(e) => setRunTime(e.target.value)} /></label>
          <label className="field-row"><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Enabled</label>
        </section>
      </div>

      <div className="action-row">
        <button type="button" onClick={() => void handlePreview()}>Preview Schedule</button>
        <button type="button" onClick={() => void handleSave()}>Save Schedule</button>
        <button type="button" onClick={() => void handleGenerateToday()}>Generate Today&apos;s Jobs</button>
        <button type="button" onClick={() => void handleDisable()}>Disable Schedule</button>
      </div>

      {preview && (
        <section className="card detail-card">
          <h2>Preview ({preview.job_count} jobs)</h2>
          <pre className="json-block">{JSON.stringify(preview.jobs_preview.slice(0, 5), null, 2)}</pre>
        </section>
      )}

      {jobs.length > 0 && (
        <section className="card detail-card">
          <h2>Today&apos;s Planned Jobs ({jobs.length})</h2>
          <pre className="json-block">{JSON.stringify(jobs, null, 2)}</pre>
        </section>
      )}
    </div>
  );
}
