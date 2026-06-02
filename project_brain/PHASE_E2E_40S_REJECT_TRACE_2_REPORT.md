# PHASE E2E-40S — REJECT Trace 2 (Audit Only)

**Audit date:** 2026-06-02  
**Session:** `exec_uat_20260602_185125`  
**User topic:** `lonely girl running through neon rain street`  
**Scope:** Evidence trace only — no code or rule changes.

**Evidence file:** `storage/content_brain/execution/sessions/exec_uat_20260602_185125.json`  
**Uniqueness memory:** `storage/content_brain/memory/uniqueness/content_history.json` (1 record at audit time)

---

## Executive conclusion

| Question | Answer |
|----------|--------|
| **11. Still uniqueness-based?** | **Yes** — same root class as Trace 1 |
| **12. New blocker?** | **No** — no alternate gate (SI, retention, confidence, missing fields all pass) |

Topic **text** changed and **`topic_similarity` passed** (0.25 &lt; 0.72). REJECT is driven by **structural fingerprint collision** with the single persisted record (`Girl in Rain`, 2026-06-02 18:16:43): identical **beat sequence**, same **hook class** + template boilerplate, same **reveal_type** + loop-seed template → `beat_sequence_fingerprint` **1.0**, `max_similarity` **1.0**, `uniqueness_score` **0.0**.

---

## 1. Complete `story_quality` JSON

```json
{
  "composite_score": 88.6,
  "score": 88.6,
  "decision": "REJECT",
  "critical_failures": [
    "Uniqueness failed with critically high similarity or very low uniqueness score."
  ],
  "warnings": [
    "uniqueness",
    "Keep topic; change hook class and opening.",
    "Packaging skipped: brief decision is REJECT.",
    "Resolve upstream scoring or uniqueness issues before generating titles.",
    "Memory: Switch reveal_type to the least-used twist in recent channel history.",
    "Memory: Flatten mid-section tension and spike payoff later in the arc.",
    "Viral score gate not passed."
  ],
  "cost_risk_score": 0.11,
  "metadata": {
    "viral_composite": 67.23,
    "production_tier": "B",
    "memory_decision": "SAFE",
    "story_intelligence_applied": true,
    "source_engines": [
      "story_intelligence",
      "story_memory",
      "content_decision",
      "viral_scoring"
    ]
  },
  "originality_score": 92.0,
  "cinematic_score": 100.0,
  "emotional_tension_score": 53.2,
  "visual_diversity_score": 100.0,
  "scene_necessity_score": 100.0,
  "visual_note_count": 5
}
```

Session root also sets `story_quality_score`: **88.6** (duplicate of composite).

---

## 2. Complete readiness report

`execution_readiness` (session root):

```json
{
  "decision": "NOT_READY",
  "readiness_score": 49.0,
  "readiness_failures": [
    "Story quality decision is REJECT.",
    "Story quality has critical failures."
  ],
  "readiness_warnings": [
    "Simulation stitch_complexity is high.",
    "Browser provider selected — runtime variability expected.",
    "uniqueness",
    "Keep topic; change hook class and opening.",
    "Packaging skipped: brief decision is REJECT.",
    "Resolve upstream scoring or uniqueness issues before generating titles.",
    "Memory: Switch reveal_type to the least-used twist in recent channel history.",
    "Memory: Flatten mid-section tension and spike payoff later in the arc.",
    "Viral score gate not passed."
  ],
  "checks": {
    "simulation_exists": {
      "passed": true,
      "score": 90.0,
      "failures": [],
      "warnings": ["Simulation stitch_complexity is high."]
    },
    "governance_exists": {
      "passed": true,
      "score": 100.0,
      "failures": [],
      "warnings": []
    },
    "provider_selection_exists": {
      "passed": true,
      "score": 92.0,
      "failures": [],
      "warnings": ["Browser provider selected — runtime variability expected."]
    },
    "story_quality_exists": {
      "passed": false,
      "score": 0.0,
      "failures": [
        "Story quality decision is REJECT.",
        "Story quality has critical failures."
      ],
      "warnings": [
        "uniqueness",
        "Keep topic; change hook class and opening.",
        "Packaging skipped: brief decision is REJECT.",
        "Resolve upstream scoring or uniqueness issues before generating titles.",
        "Memory: Switch reveal_type to the least-used twist in recent channel history.",
        "Memory: Flatten mid-section tension and spike payoff later in the arc.",
        "Viral score gate not passed."
      ]
    },
    "required_fields_completeness": {
      "passed": true,
      "score": 100.0,
      "failures": [],
      "warnings": []
    },
    "fingerprint_consistency": {
      "passed": true,
      "score": 100.0,
      "failures": [],
      "warnings": []
    },
    "valid_session_state": {
      "passed": true,
      "score": 100.0,
      "failures": [],
      "warnings": []
    }
  },
  "metadata": {
    "readiness_provenance": {
      "engine": "ExecutionReadinessGate",
      "engine_version": "10g_v1",
      "policy_version": "10g_v1",
      "evaluated_at": "2026-06-02 18:51:27"
    },
    "simulation_report_uuid": "21652f9d-da08-4170-9183-947487b11e8f",
    "governance_decision_ids": {
      "approval": "appr_c0f77298a26c",
      "budget": "bdgt_92dd26faa0b7"
    }
  }
}
```

**State history (readiness-related):**

| At | State | Reason |
|----|-------|--------|
| 18:51:26 | REJECTED | populated from content brief |
| 18:51:26 | REJECTED | governance: approval=REJECTED |
| 18:51:26 | NOT_READY | readiness gate score=47.7 |
| 18:51:27 | NOT_READY | readiness gate score=49.0 (after UAT approval override) |

UAT bridge set `approval_decision.status` = `APPROVED_FOR_EXECUTION` but **did not** clear `story_quality` REJECT → readiness stays **NOT_READY**.

---

## 3. All critical failures

| Source | Critical failures |
|--------|-------------------|
| `story_quality.critical_failures` | `Uniqueness failed with critically high similarity or very low uniqueness score.` |
| `execution_readiness.readiness_failures` | `Story quality decision is REJECT.`; `Story quality has critical failures.` |
| `brief_snapshot.decision_package.reasons` | Same uniqueness string (upstream) |
| `approval_decision.blockers` | `Content gate: REJECT` (governance mirror, not a separate engine veto) |

**Count of distinct root messages:** **1** (uniqueness hard fail propagated).

---

## 4. Complete uniqueness report

From `brief_snapshot.uniqueness_report`:

```json
{
  "passed": false,
  "layers": [
    {
      "layer_name": "topic_similarity",
      "similarity_score": 0.25,
      "threshold": 0.72,
      "passed": true,
      "detail": "Compared topic against 1 prior records."
    },
    {
      "layer_name": "hook_fingerprint",
      "similarity_score": 0.8452,
      "threshold": 0.68,
      "passed": false,
      "detail": "Compared hook fingerprint against 1 prior records."
    },
    {
      "layer_name": "beat_sequence_fingerprint",
      "similarity_score": 1.0,
      "threshold": 0.7,
      "passed": false,
      "detail": "Compared beat sequence against 1 prior records."
    },
    {
      "layer_name": "generic_pattern_detection",
      "similarity_score": 0.0,
      "threshold": 0.0,
      "passed": true,
      "detail": "No generic patterns detected."
    },
    {
      "layer_name": "twist_type_collision",
      "similarity_score": 0.892,
      "threshold": 0.65,
      "passed": false,
      "detail": "Compared reveal/loop fingerprint against 1 prior records."
    },
    {
      "layer_name": "niche_banned_patterns",
      "similarity_score": 0.0,
      "threshold": 0.0,
      "passed": true,
      "detail": "No niche banned phrases detected."
    }
  ],
  "max_similarity": 1.0,
  "uniqueness_score": 0.0,
  "regeneration_directive": "Keep topic; change hook class and opening."
}
```

---

## 5. Similarity layers (tabular)

| Layer | Score | Threshold | Pass | vs prior count |
|-------|-------|-----------|------|----------------|
| topic_similarity | 0.25 | 0.72 | yes | 1 |
| hook_fingerprint | 0.8452 | 0.68 | **no** | 1 |
| beat_sequence_fingerprint | **1.0** | 0.7 | **no** | 1 |
| generic_pattern_detection | 0.0 | 0.0 | yes | — |
| twist_type_collision | 0.892 | 0.65 | **no** | 1 |
| niche_banned_patterns | 0.0 | 0.0 | yes | — |

**Aggregate:** `max_similarity = 1.0` → `uniqueness_score = 100 - (1.0 × 100) = 0.0` (engine formula).

---

## 6. Engine that produced REJECT

```mermaid
flowchart LR
  UE[UniquenessEngine] -->|passed=false| CDE[ContentDecisionEngine]
  CDE -->|REJECT 0.9| DP[decision_package]
  DP --> SPB[SessionPopulationBuilder]
  SPB --> SQ[story_quality.decision=REJECT]
  SQ --> ERG[ExecutionReadinessGate NOT_READY]
```

| Step | Engine | Output |
|------|--------|--------|
| 1 | **UniquenessEngine** | `passed: false`, `uniqueness_score: 0.0` |
| 2 | **ContentDecisionEngine** | `_decide_uniqueness_failure()` → **REJECT**, confidence **0.9** |
| 3 | **SessionPopulationBuilder** | Copies decision + reasons → `story_quality` |
| 4 | **ApprovalBudgetGovernanceEngine** | Blocker `Content gate: REJECT` |
| 5 | **ExecutionReadinessGate** | `story_quality_exists` failed |

**Not REJECT producers:** StoryIntelligence (88.6), StoryMemory (SAFE), retention map (100), execution confidence (80.6).

---

## 7. Exact score values

| Metric | Value | Location | Gate / notes |
|--------|-------|----------|----------------|
| **uniqueness_score** | **0.0** | `uniqueness_report` | REJECT if ≤ 40 |
| **max_similarity** | **1.0** | `uniqueness_report` | REJECT if ≥ 0.85 |
| **story_quality_score** | **88.6** | `story_quality` / `story_quality_score` | min 70 — **passes** |
| **confidence_score** | **80.6** | `execution_confidence_score`, `simulation_report.execution_confidence_estimate` | min 60 — **passes** |
| **retention_score** | **100.0** | `brief_snapshot.retention_map.retention_score_estimate` | viral dim 100 — **passes** |
| viral_composite | 67.23 | `story_quality.metadata` | gate 65 — fails mainly on uniqueness dim 0.0 |
| story_memory_risk | 0.11 | run_context | SAFE |

---

## 8. Memory entries that matched

**Store:** `storage/content_brain/memory/uniqueness/content_history.json`  
**Records at audit time:** **1**

| Field | Prior record (`uniq_e792a4abf5`) | Current session (`185125`) |
|-------|----------------------------------|----------------------------|
| created_at | 2026-06-02 18:16:43 | — |
| topic | Girl in Rain | lonely girl running through neon rain street |
| hook_class | moral_discomfort | moral_discomfort |
| hook_text (template) | `{topic} worked — and that is exactly why it feels wrong in General Short-Form Content.` | Same template, topic substituted |
| story_mode | psychological_unraveling | psychological_unraveling |
| reveal_type | comparison_reveal | comparison_reveal |
| beat_sequence | HOOK→CONTEXT→ESCALATION→PATTERN_BREAK→PAYOFF→LOOP_SEED | **Identical** |
| mechanic_sequence | pattern_interrupt→curiosity_gap→stakes_increase→perspective_shift→peak_moment→open_loop | **Identical** |
| hook_fingerprint | moral_discomfort:74b3a30f54 | Different digest (topic tokens in first 8 words differ) |
| beat_fingerprint | abdde4490f43 | **Same** (identical beat+mechanic payload) |
| twist_fingerprint | eb89e5166d29 | Different (loop_seed text differs) |
| topic_tokens | girl, in, rain | lonely, girl, running, through, neon, rain, street |

**Layer match summary vs this record:**

- **topic_similarity:** partial token overlap (girl, rain) → 0.25 — **below** threshold  
- **hook_fingerprint:** same class + high Jaccard on boilerplate → 0.8452 — **fail**  
- **beat_sequence_fingerprint:** identical `beat_fingerprint` → **1.0** — **fail**  
- **twist_type_collision:** same `reveal_type` + similar loop_seed template → 0.892 — **fail**

---

## 9. Top 10 nearest fingerprints

Only **one** prior record exists in production uniqueness memory. Ranked by layer contribution (highest similarity first):

| Rank | record_id | topic | hook_class | beat_fp | twist_fp | topic_sim | hook_sim | beat_sim | twist_sim | max |
|------|-----------|-------|------------|---------|----------|-----------|----------|----------|-----------|-----|
| 1 | uniq_e792a4abf5 | Girl in Rain | moral_discomfort | abdde4490f43 | eb89e5166d29 | 0.25 | 0.8452 | **1.0** | 0.892 | **1.0** |

*(Ranks 2–10: none — memory contains a single record.)*

---

## 10. Why this topic still collides

The operator changed **surface topic words** (neon, running, lonely, street) but the **Content Brain pipeline** still emitted the **same canonical short-form skeleton** as the stored `Girl in Rain` brief:

1. **Same six-beat arc** (`StoryArchitectureEngine` / profile defaults) → `beat_fingerprint` hash **unchanged** → layer score **1.0** (hard REJECT via `max_similarity >= 0.85`).

2. **Same hook class** (`moral_discomfort`) and **same sentence mold** (`{topic} worked — and that is exactly why it feels wrong in General Short-Form Content.`) → large shared token set with prior hook → **0.8452** (> 0.68).

3. **Same reveal** (`comparison_reveal`) and **same loop-seed mold** (`Leave one unanswered detail about {topic} so … viewers comment…`) → twist layer **0.892** (> 0.65).

4. **Topic layer alone** does not save the brief: Jaccard on topic tokens is only **0.25** (passes), but `UniquenessEngine` uses **max** across layers, so one **1.0** beat match caps `uniqueness_score` at **0.0**.

**Interpretation:** Uniqueness is doing **structural / template** deduplication, not **literal topic string** deduplication. “Completely different topic” in natural language is **not** “completely different fingerprint” under current rules.

**Persisted pollutant:** The lone memory row is still the **18:16:43** `Girl in Rain` entry (likely from pre-isolation E2E planning probe per Trace 1 audit). This session did not add a new row (UAT uses `record_uniqueness_on_success=False`).

---

## 11. Is rejection still uniqueness-based?

**Yes.**

- `decision_package.decision`: **REJECT**  
- `decision_package.reasons`: uniqueness hard-fail string only  
- `decision_package.weak_dimensions`: `["uniqueness"]`  
- `uniqueness_report.passed`: **false**  
- ContentDecisionEngine path: `not uniqueness_report.passed` → `_decide_uniqueness_failure()` (thresholds 40 / 0.85 crossed)

---

## 12. If not uniqueness — new blocker?

**N/A — no new blocker identified.**

| Check | Result |
|-------|--------|
| Story Intelligence composite | 88.6 — not blocking |
| Story memory | SAFE |
| Retention | 100.0 |
| Execution confidence | 80.6 |
| Required fields | readiness check passed |
| Budget | WITHIN_LIMIT |
| Alternate content decision reason | None besides uniqueness |

Secondary **symptoms** (not root blockers): viral `passed_gate: false` (uniqueness dimension 0.0); packaging skipped; UAT approval override ineffective for readiness.

---

## Upstream `decision_package` (reference)

```json
{
  "decision": "REJECT",
  "confidence": 0.9,
  "reasons": [
    "Uniqueness failed with critically high similarity or very low uniqueness score."
  ],
  "weak_dimensions": ["uniqueness"],
  "revision_targets": ["hook", "story_beats", "trend_context"],
  "regeneration_required": false,
  "priority_fixes": ["Keep topic; change hook class and opening."],
  "production_ready": false
}
```

---

## Related documents

- Trace 1 root cause: `project_brain/PHASE_E2E_40S_REJECT_ROOT_CAUSE_AUDIT.md`  
- Memory isolation fix (probes only): `project_brain/PHASE_E2E_40S_UNIQUENESS_MEMORY_ISOLATION_FIX_REPORT.md`

---

## Audit conclusion

Session `exec_uat_20260602_185125` REJECT is **still 100% uniqueness-gated**, with the **same production memory record** and **same story template** as earlier rain/girl runs. Changing the topic string reduced **topic_similarity** only; **beat**, **hook-class + template**, and **twist/loop** layers still exceed thresholds. Until hook class, beat sequence, and/or reveal/loop structure diverge—or the test-only memory row is explicitly cleared—a “new” topical phrase will keep colliding under current rules.
