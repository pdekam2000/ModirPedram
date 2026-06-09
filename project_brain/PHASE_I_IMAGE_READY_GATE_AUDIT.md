# Phase I — Image Ready Approval Gate Audit

**Date:** 2026-06-03  
**Mode:** Audit only — no code changes  
**Scope:** Why **Image Ready** stayed disabled while starter image appeared complete in Runway

---

## Executive summary

**Image Ready is not driven by image completion detection.** It enables only when the live smoke runtime is paused on step `wait_for_image_ready_manual` with `gate_type=manual_hold` and `waiting=true`.

There is **no** wiring from Runway DOM / latest image card scan → `gate_enabled` → Image Ready. Starter image card assignment runs **after** Image Ready, on step `use_starter_image_for_video`.

The most likely explanation when the operator sees a finished image but **Image Ready** is disabled:

1. **Runtime is not on the manual-hold step** (still on **Approve** for `image_generate_button`, run failed, or run ended), **or**
2. **Operator generated the image manually in Runway** before clicking **Approve**, so the browser shows output while the gate is still `approval`, **or**
3. **Approve** (not Image Ready) was disabled due to `gate_enabled=false` (`starter_settings_not_verified`) — a separate gate that does not block Image Ready but is easy to confuse in the UI.

**Image completion detection did not fail to enable Image Ready** — it was never designed to enable it.

---

## 1. Exact enable condition — Image Ready

### Web UI (`RunwayLiveSmokeApprovalPanel.tsx`)

```169:175:ui/web/src/components/RunwayLiveSmokeApprovalPanel.tsx
  const waitingApproval = Boolean(snapshot?.waiting && snapshot?.gate_type === "approval");
  const waitingImageReady = Boolean(snapshot?.waiting && snapshot?.gate_type === "manual_hold");
  const gateEnabled = snapshot?.gate_enabled !== false;
  const canApprove = waitingApproval && gateEnabled;
```

```374:375:ui/web/src/components/RunwayLiveSmokeApprovalPanel.tsx
            <button type="button" disabled={!waitingImageReady} onClick={() => void runAction("image_ready")}>
              Image Ready
```

| Button | Enabled when |
|--------|----------------|
| **Approve** | `waiting && gate_type === "approval" && gate_enabled !== false` |
| **Image Ready** | `waiting && gate_type === "manual_hold"` only |
| **Cancel** | `active \|\| waiting` |

**Important:** `gate_ready`, `gate_enabled`, and `gate_reason` are displayed in the panel but **do not** control Image Ready.

### Runtime accept condition (`submit_image_ready`)

```285:290:content_brain/execution/runway_live_smoke_approval_runtime.py
    def submit_image_ready(self, *, operator: str | None = None) -> dict[str, Any]:
        with self._lock:
            if self._cancelled:
                return self._action_result(False, "run already cancelled")
            if not self._waiting or self._gate_type != GATE_MANUAL_HOLD:
                return self._action_result(False, "not waiting for image ready")
```

### When `manual_hold` is entered

Semi-auto engine pauses on any step with `manual_required=True` and **no** approval control:

```190:203:content_brain/execution/runway_continuity_semi_auto.py
            if step.manual_required and not step.requires_operator_approval:
                if self.simulate:
                    result.status = SEMI_AUTO_STEP_DONE
                    ...
                    continue
                session.status = SEMI_AUTO_STATUS_MANUAL_HOLD
                session.awaiting_step_id = step.step_id
                result.status = SEMI_AUTO_STEP_BLOCKED
                result.notes = "manual operator action required"
                return session
```

Plan step (Phase I step **011**):

```220:226:content_brain/execution/runway_continuity_dry_run.py
    add(
        "wait_for_image_ready_manual",
        phase="starter_image",
        action="STOP — operator waits for generated image output",
        manual_required=True,
        notes="Use image_download_button or visual confirmation when mapped",
    )
```

**Sequence after operator approves image Generate:**

| Order | Step | Gate type | UI |
|-------|------|-----------|-----|
| 1 | `010_image_generate_manual_required` | `approval` | **Approve** |
| 2 | (engine clicks Generate) | — | — |
| 3 | `011_wait_for_image_ready_manual` | `manual_hold` | **Image Ready** |
| 4 | `012_clear_image_prompt_after_generation` | auto | — |
| 5 | `013_use_starter_image_for_video` | auto | scans/assigns image card |

Image Ready should become enabled **immediately** when step 011 is entered — **before** the image must be visually complete.

---

## 2. Which runtime condition controls it?

| Layer | Control |
|-------|---------|
| **Primary** | `RunwayLiveSmokeApprovalSnapshot.waiting === true` **and** `gate_type === "manual_hold"` |
| **Not used for Image Ready** | `gate_ready`, `gate_enabled`, `gate_reason` |
| **Not used** | `latest_image_card_found`, image DOM scan, generation progress |
| **Thread** | Background worker blocked in `manual_ack_callback()` → `_wait_for_gate_response()` until `submit_image_ready()` sets `_response_event` |

`set_gate_readiness()` is used for:

- **Image Generate Approve** — `enabled = settings_verified` (`_sync_non_download_gate_readiness`)
- **Download Approve** — `enabled = strict clip completion` (`_wait_for_download_gate_enabled`)

It is **never** called for the Image Ready manual hold.

---

## 3. Did starter image completion detection fire?

**No automatic completion → Image Ready path exists.**

- Step `wait_for_image_ready_manual` has **no** `_execute_step` body; it only blocks for operator ack.
- `select_latest_generated_image_card()` / `scan_generation_image_cards()` run later on **`use_starter_image_for_video`**, not during the manual hold.
- Report field `image_generation_result = "operator_confirmed_ready"` is set only **after** manual ack succeeds:

```1279:1280:content_brain/execution/runway_live_smoke_test.py
        if "wait_for_image_ready" in step.step_id:
            self.report.image_generation_result = "operator_confirmed_ready"
```

**Simulate mode:** manual hold is **auto-skipped** (never opens Image Ready in UI):

```191:197:content_brain/execution/runway_continuity_semi_auto.py
                if self.simulate:
                    result.status = SEMI_AUTO_STEP_DONE
                    result.executed = True
                    result.simulated = True
                    result.notes = "simulate: manual hold acknowledged"
                    session.current_step_index += 1
```

---

## 4. Did gate state update fail?

**Unlikely for Image Ready specifically.**

Entering manual hold sets:

- `waiting = true`
- `gate_type = "manual_hold"`
- `run_status = "waiting_image_ready"`

via `_wait_for_gate_response()` in `runway_live_smoke_approval_runtime.py`.

`gate_enabled` / `gate_ready` are cleared when the **previous** Approve succeeds (`_clear_waiting()`), and are **not** updated on manual hold entry. That leaves the status panel showing `gate_enabled: no` during Image Ready — **misleading but not disabling** the button.

**Failure modes that prevent reaching manual hold:**

| Failure | Symptom in UI |
|---------|----------------|
| Run dies on `001_image_generation_open` (navigation timeout) | `waiting=false`, all action buttons disabled |
| Operator never clicks **Approve** on image Generate | `gate_type=approval`, **Image Ready disabled** |
| `starter_settings_not_verified` before Generate | **Approve** disabled; Image Ready still disabled (not on step 011 yet) |
| UI run not active (`active=false`) | Stale snapshot; Image Ready disabled |

---

## 5. Was UI polling stale?

**Polling is unlikely to be the root cause for Image Ready.**

- Web panel polls `GET /runway-live-smoke/status` every **1.5s** (`RunwayLiveSmokeApprovalPanel.tsx`).
- Approval runtime updates snapshot under `threading.RLock`; worker blocks on `threading.Event` until Image Ready POST.
- On run start, service calls `runtime.mark_ui_connected(True)` and `fallback_to_terminal=False` — UI path is intended.

**Stale snapshot can occur if:**

- Run already **failed/completed** but operator still looks at Runway browser (image visible from session).
- Operator refreshed UI after crash — `snapshot` idle while Chrome still shows generated image.
- Last persisted report shows failure before any gate (see below).

Polling does **not** explain Image Ready staying disabled **while** `Current Gate` shows `Waiting: image ready` and `Status: waiting_image_ready`. If those fields were correct, the button would be enabled.

---

## 6. Was image card assigned correctly?

**At Image Ready gate time: assignment is not expected.**

| Phase | Image card state |
|-------|------------------|
| Before step 011 | Card may exist in Runway DOM; runtime has **not** assigned `starter_image_card` |
| Step 011 (Image Ready) | Operator visual confirm only |
| Step 013 (`use_starter_image_for_video`) | `select_latest_generated_image_card()` → `last_latest_image_card`, fingerprint, Use to Video |

From Phase I Clip 2 diagnostic (run that **did** pass starter chain):

- Starter card fingerprint: `554|296|476|853|…` (assigned during Use to Video, not at Image Ready)
- That run reached video; Image Ready was acknowledged implicitly (otherwise steps 012–013 could not run)

**Conclusion:** Missing card assignment does **not** disable Image Ready. Card detection is downstream.

---

## 7. Would runtime continue automatically if approvals were disabled?

| Mode | Image Ready | Generate / Download approvals |
|------|-------------|-------------------------------|
| **Live + default UI callbacks** | Blocks until Image Ready click | Blocks until Approve |
| **Live + `manual_ack_callback=lambda *_: True`** | Auto-continues past step 011 | Still needs Approve unless `approval_callback` also auto |
| **`simulate=True`** | Manual hold skipped in engine | Auto-approved in validators |
| **Terminal `READY`** | Works if UI not connected and terminal fallback enabled | UI service sets `fallback_to_terminal=False` — terminal READY **not** used from web-started runs |

There is **no** fully automatic live Phase I mode today without replacing both callbacks. Disabling only Image Ready (option B partial) would require new completion detection + `set_gate_readiness` or auto `submit_image_ready()` — **not implemented**.

---

## Actual runtime state (artifacts)

### Latest on-disk report — `runway_phase_i_3clip_last_report.json` (2026-06-07 20:20)

| Field | Value | Implication |
|-------|-------|-------------|
| `ok` | `false` | Run failed immediately |
| `stopped_reason` | `001_image_generation_open` Page.goto timeout | Never reached any approval gate |
| `approvals_requested` | `[]` | No Approve / Image Ready cycle |
| `manual_holds` | `[]` | Image Ready never opened |
| `image_generation_result` | `not_started` | |
| `latest_image_card_found` | `false` | |
| `settings_verified` | `false` | |

**This report does not document the operator’s “image visible” incident** — it failed before starter prep completed. Any image seen in Runway during that attempt was from the **browser session**, not from a gated runtime step.

### Prior Phase I live run (Clip 2 diagnostic, ~15:44–16:33 same day)

| Field | Value |
|-------|-------|
| Starter steps 001–012 | **Completed** (Use to Video OK, card `554|296|476|853|`) |
| Approvals granted | Image Generate + Clip 1 Video Generate |
| Failure | Clip 1 strict completion timeout — **after** starter chain |

That run **must** have passed Image Ready (step 011) to reach Use to Video. The failure mode there was **Clip 1 video** Approve/completion, not starter Image Ready.

---

## Why the button remained disabled (synthesis)

Given code behavior and artifacts:

| # | Cause | Likelihood | Evidence |
|---|--------|------------|----------|
| 1 | Runtime **not on step 011** — still on **Approve** for image Generate, or run dead | **High** | Image Ready requires `manual_hold`; visible Runway output can exist before Approve |
| 2 | Operator clicked **Generate in Runway** manually, not via approved runtime step | **High** | Common with CDP attached browser; gate state unchanged |
| 3 | **Approve** disabled (`gate_enabled=false`, settings not verified) — operator waits for image before approving | **Medium** | `gate_reason` would show `starter_settings_not_verified`; Image Ready still disabled because step 011 not reached |
| 4 | Run **failed early** (navigation timeout) while browser still shows content | **Medium** | Latest `runway_phase_i_3clip_last_report.json` |
| 5 | UI confusion: `gate_enabled: no` shown during manual hold | **Medium** | Display bug/UX; button logic ignores it |
| 6 | Stale UI after run ended | **Low–Medium** | `active=false`, `waiting=false` |
| 7 | Image completion detection failed to enable button | **Ruled out** | No such integration exists |
| 8 | Image card assignment failed | **Ruled out** for Image Ready | Assignment is post–Image Ready |

---

## Recommendations (audit only — do not implement here)

### Short term (operator)

1. Read **Current Gate** title: must say **“Waiting: image ready”** (not `image_generate_button`).
2. Flow: **Approve** Generate first → then **Image Ready** (can click Image Ready while image still generating).
3. Do not use Runway’s Generate button manually during a gated run unless intentionally overriding the pipeline.
4. If gate shows `starter_settings_not_verified`, fix chips (9:16 / count / quality) before Approve.

### Product options (decision)

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Keep approval gates** | Current design | Safe, explicit operator control | Manual hold decoupled from DOM; easy to desync from browser |
| **B. Auto-enable Image Ready when artifact detected** | Poll `scan_generation_image_cards()` during step 011; call `set_gate_readiness` + optional auto `submit_image_ready()` | Matches operator expectation when image visible | Needs stale-card filtering (same class of bugs as video gate); still need Approve on Generate |
| **C. Fully automatic mode** | Auto `approval_callback` + auto `manual_ack_callback` + optional headless | Fastest rehearsal | Violates Phase I safety model; not for live credit spend without explicit opt-in |

**Recommended direction:** **A** for production live runs; add **B** as an optional “detect image card → enable or auto-ack Image Ready” layer tied to step 011 only, reusing starter image card scan logic from step 013. Do **not** conflate with Clip 1 **Approve** gate (`gate_enabled` / strict completion).

### UX improvements (when implementing later)

- When `gate_type=manual_hold`, hide or gray out `gate_enabled` / `gate_reason` (they reflect the previous approval gate).
- Show explicit copy: “Image Ready unlocks after Generate is approved — not when Runway finishes rendering.”
- Surface `current_step_id` prominently (`011_wait_for_image_ready_manual`).
- Log manual holds to report even on success (today often empty in simulate; live should always append).

---

## Checklist answers

| # | Question | Answer |
|---|----------|--------|
| 1 | When does Image Ready become enabled? | When runtime is on `wait_for_image_ready_manual` with `waiting=true` and `gate_type=manual_hold`. |
| 2 | Which condition controls it? | Snapshot gate type + waiting flag only — **not** `gate_enabled` or image detection. |
| 3 | Did starter completion detection fire? | **No** — not connected to this gate. |
| 4 | Did gate state update fail? | **Unlikely** if step 011 was reached; **yes** if run never passed image Generate approval or failed earlier. |
| 5 | Was UI polling stale? | **Unlikely** during an active hold; **possible** after run failure. |
| 6 | Was image card assigned correctly? | **N/A at Image Ready**; assignment happens on step 013. |
| 7 | Auto-continue if approvals disabled? | Manual hold skippable only with auto ack or simulate; full auto needs both callbacks replaced. |

---

## Files reviewed

- `ui/web/src/components/RunwayLiveSmokeApprovalPanel.tsx`
- `content_brain/execution/runway_live_smoke_approval_runtime.py`
- `content_brain/execution/runway_live_smoke_test.py`
- `content_brain/execution/runway_continuity_semi_auto.py`
- `content_brain/execution/runway_continuity_dry_run.py`
- `content_brain/execution/runway_ui_navigator.py` (latest image card scan)
- `ui/api/runway_live_smoke_service.py`
- `project_brain/runway_phase_i_3clip_last_report.json`
- `project_brain/PHASE_I_CLIP2_FAILURE_DIAGNOSTIC.md`

**No code was modified in this audit.**
