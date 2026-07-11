# AUDIT — Runway Videos Per Day & 24/7 Non-Stop Generation

**Date:** 2026-07-10

---

## 1. Pwmap runs per day (actual Runway generations)

| Date | Total runs | YouTube | Instagram | Unknown |
|------|------------|---------|-----------|---------|
| 2026-07-04 | 25 | 13 | 11 | 1 |
| 2026-07-05 | 21 | — | 17 | 4 |
| 2026-07-06 | 25 | 6 | 13 | 6 |
| **2026-07-07** | **157** | 74 | 82 | 1 |
| 2026-07-08 | 48 | 24 | 23 | 1 |
| 2026-07-09 | 27 | 4 | 23 | — |
| **2026-07-10** | **19** | 2 | 16 | 1 |

**Total runs in folder:** 322

Configured daily cap: **6 videos/day** (YouTube 3 + Instagram 3).

Actual runs are **far above cap** — especially Jul 7 (157×) and today (19× with only 2 completed automation jobs).

---

## 2. automation_jobs.json — today (2026-07-10)

| Status | Count (updated today) |
|--------|----------------------|
| completed | 2 |
| failed | 18 |
| planned | 2 (+2 more planned scheduled today) |
| running | 1 |

**Completed per platform (by `updated_at`):**

| Date | youtube_shorts | instagram_reels |
|------|----------------|-----------------|
| 2026-07-07 | 3 | 3 |
| 2026-07-08 | 1 | — |
| 2026-07-09 | 4 | — |
| 2026-07-10 | 2 | 0 |

---

## 3. Is daily cap (6) respected?

**Partially — with a critical gap.**

| Check | Result |
|-------|--------|
| `max_jobs_per_day` in queue | 6 |
| `enabled_daily_cap` (scheduler) | 6 (3+3) |
| `completed_today` (queue) | 2 |
| `background_scheduler` stops when `completed_today >= 6` | Yes (logic exists) |

**Gap:** Cap counts only **`completed`** jobs. **`failed` jobs do not count**, but each failure still runs a full pwmap generation (45s / 3 clips).

Today: **2 completed, 18 failed, 19 pwmap runs** — scheduler kept starting jobs because `2 < 6`.

---

## 4. background_scheduler.py behavior

- Polls every **30 seconds** while automation enabled and not paused.
- On each tick: `sync_platform_daily_jobs()` → may import new planned jobs.
- Starts next due planned job if `completed_today < daily_cap`.
- **Before fix:** When cap reached, it logged and returned but **left planned jobs in queue**.
- **After fix:** Cancels all remaining **planned** jobs for today when cap is hit.

---

## 5. Root cause — why 24/7 non-stop

### Bug A — Failed jobs ignored in per-platform slot counting

`active_jobs_today_for_platform()` excluded `failed` jobs. After a failure, `import_scheduled_jobs()` thought the platform still had free slots and could add more planned jobs → **unlimited retry storm**.

Example today (Instagram): **15 failed + 1 running + 2 planned** vs cap of **3/day**.

### Bug B — Stale planned jobs could replay after midnight

`due_planned_jobs()` treats any job with `scheduled_time` in the past as **due**. Old `planned` jobs from prior days would run again when `completed_today` reset at midnight.

### Bug C — Jul 7 spike (157 runs)

Combination of: many platforms enabled, failures not counting toward slots, manual `/automation/start` resetting failed→planned, and 45s/3-clip runs taking multiple pwmap attempts per job.

### Bug D — Cap reached but queue not drained

Scheduler stopped starting jobs at cap but **did not cancel** remaining planned jobs — they stayed queued for the next tick/day.

---

## 6. Fixes applied

| File | Change |
|------|--------|
| `automation_queue.py` | `active_jobs_today_for_platform()` now counts **completed + failed + planned + running** |
| `automation_queue.py` | `cancel_remaining_planned_jobs_for_today()` — cancel planned when cap hit |
| `automation_queue.py` | `cancel_stale_planned_jobs()` — cancel planned from prior days |
| `background_scheduler.py` | Call cancel when daily cap reached (3 code paths) |
| `automation_job_runner.py` | Cancel planned on `daily_job_cap_reached` preflight |
| `platform_daily_scheduler.py` | Cancel stale planned on each daily sync |

---

## 7. Recommended operator actions

1. **Restart API** to load scheduler fixes.
2. **Pause automation** if you want to stop the current run immediately.
3. Review today's **18 failed** Instagram jobs — likely upload/block errors, not generation.
4. Consider lowering `videos_per_day` per platform until failure rate is under control.

---

*Audit complete. Fixes applied 2026-07-10.*
