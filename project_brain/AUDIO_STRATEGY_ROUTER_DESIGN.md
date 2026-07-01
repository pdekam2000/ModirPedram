# Audio Strategy Router — Design

Design-only document for the Audio Strategy Router decision layer.

**Full report:** [PHASE_AUDIO_STRATEGY_ROUTER_DESIGN_REPORT.md](./PHASE_AUDIO_STRATEGY_ROUTER_DESIGN_REPORT.md)

## Summary

Three audio classes:

| ID | Class | Pipeline |
|----|-------|----------|
| `music_only` | A — Music Driven | Video → Music → Subtitle → Publish |
| `narrator` | B — Narrator Driven | Video → Narrator → Music → Subtitle → Publish |
| `cinematic` | C — Cinematic Audio | Video → Character Director → Voice → Environment → Music → Subtitle → Publish |

The router scores topic, niche, platform, style, character/dialogue counts, story type, and duration **before Runway** and **before post-processing**, outputting `audio_strategy`.

See the full report for strategy matrix, routing rules, platform recommendations, provider mapping, and implementation roadmap.

**Status:** Design complete — no code changes in this phase.
