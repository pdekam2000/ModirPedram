import { RunwayBrowserPanel } from "../components/RunwayBrowserPanel";

export function ProductDashboardPage() {
  return (
    <div className="product-page">
      <header className="header">
        <div>
          <p className="eyebrow">ModirAgent OS · Product</p>
          <h1>Dashboard</h1>
          <p className="subtitle">Create videos, plan schedules, and review publish packages — without debug noise.</p>
        </div>
      </header>
      <RunwayBrowserPanel compact showRunwayDetails={false} />
      <div className="product-grid">
        <section className="card">
          <h2>Create Video</h2>
          <p className="muted">Professional create flow with duration, topic source, director, and critic options.</p>
        </section>
        <section className="card">
          <h2>Schedule Planner</h2>
          <p className="muted">Plan daily, weekly, or monthly video jobs. Planning only — no background auto-upload.</p>
        </section>
        <section className="card">
          <h2>Results</h2>
          <p className="muted">Latest generated video, publish package, prompts, and platform targets.</p>
        </section>
        <section className="card">
          <h2>Upgrade Center</h2>
          <p className="muted">Install future features as patch packages without rewriting core runtime.</p>
        </section>
      </div>
    </div>
  );
}
