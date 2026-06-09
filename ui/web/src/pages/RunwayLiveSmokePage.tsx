import { useState } from "react";
import { RunwayLiveSmokeApprovalPanel } from "../components/RunwayLiveSmokeApprovalPanel";

type RunwaySmokeTab = "phase_h" | "phase_i";

export function RunwayLiveSmokePage() {
  const [tab, setTab] = useState<RunwaySmokeTab>("phase_h");

  return (
    <div className="runway-live-smoke-page">
      <div className="uat-center-tabs execution-center-tabs runway-smoke-subtabs">
        <button
          type="button"
          className={`uat-center-tab ${tab === "phase_h" ? "active" : ""}`}
          onClick={() => setTab("phase_h")}
        >
          1-Clip Smoke (Phase H)
        </button>
        <button
          type="button"
          className={`uat-center-tab ${tab === "phase_i" ? "active" : ""}`}
          onClick={() => setTab("phase_i")}
        >
          3-Clip Continuity (Phase I)
        </button>
      </div>
      <RunwayLiveSmokeApprovalPanel mode={tab} />
    </div>
  );
}
