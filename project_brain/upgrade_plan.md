# PROJECT UPGRADE AGENT PLAN

Version: V2 - Targeted Analyze Mode
Generated at: 2026-05-26 22:24:58

## Mode

ANALYZE ONLY

- Automatic editing: DISABLED
- Backup before edit: REQUIRED
- User approval before edit: REQUIRED
- Existing pipeline must be preserved
- Runway / Hailuo / Provider Router must not be broken

## User Goal

Add retry mechanism to Runway provider

## Extracted Keywords

- mechanism
- provider
- retry
- runway

## Scan Target

providers

## Scan Summary

- Files scanned: 10
- Raw keyword matches: 10
- Dependency related files: 12
- Core files: 14
- Related files: 8
- Context files: 0
- Estimated risk: CRITICAL

## Project Brain Context

- current_state.md: FOUND (6016 chars)
- dependency_map.md: FOUND (11132 chars)
- pipeline_map.md: FOUND (2760 chars)
- file_ownership.md: FOUND (1473 chars)
- impact_report.md: FOUND (177 chars)
- CHAT_HANDOFF.md: FOUND (35602 chars)
- FULL_PROJECT_HANDOFF.md: FOUND (35602 chars)
- FULL_PROJECT_HANDOFF_NEW.md: FOUND (36493 chars)
- ACTIVE_PIPELINE.md: FOUND (1495 chars)
- SYSTEM_MAP.md: FOUND (5789 chars)
- EXECUTION_FLOW.md: FOUND (3962 chars)
- verification_report.md: FOUND (578 chars)
- change_log.md: FOUND (7294 chars)

## Core Files

- providers/runway_video_provider.py | score=12 | reason=Keyword / structure match
- providers/runway_browser_provider.py | score=11 | reason=Keyword / structure match
- providers/runway_download_provider.py | score=11 | reason=Keyword / structure match
- providers/elevenlabs_voice_provider.py | score=6 | reason=Keyword / structure match
- providers/hailuo_browser_provider.py | score=6 | reason=Keyword / structure match
- providers/hailuo_download_provider.py | score=6 | reason=Keyword / structure match
- providers/minimax_video_provider.py | score=6 | reason=Keyword / structure match
- providers/openai_provider.py | score=6 | reason=Keyword / structure match
- providers/openai_trend_provider.py | score=6 | reason=Keyword / structure match
- providers/__init__.py | score=5 | reason=Keyword / structure match
- core/video_provider_router.py | score=1 | reason=Imports affected module: providers.runway_video_provider
- engines/narration_engine.py | score=1 | reason=Imports affected module: providers.elevenlabs_voice_provider
- orchestrators/hailuo_multi_clip_orchestrator.py | score=1 | reason=Imports affected module: providers.hailuo_download_provider
- orchestrators/runway_browser_orchestrator.py | score=1 | reason=Imports affected module: providers.runway_download_provider

## Related Files

- full_selfcare_factory.py | score=1 | reason=Imports affected module: providers.elevenlabs_voice_provider
- test_download.py | score=1 | reason=Imports affected module: providers.hailuo_download_provider
- test_elevenlabs_voice.py | score=1 | reason=Imports affected module: providers.elevenlabs_voice_provider
- test_full_ai_video_pipeline.py | score=1 | reason=Imports affected module: providers.elevenlabs_voice_provider
- test_hailuo.py | score=1 | reason=Imports affected module: providers.hailuo_browser_provider
- test_openai_trends.py | score=1 | reason=Imports affected module: providers.openai_trend_provider
- test_selfcare_voice.py | score=1 | reason=Imports affected module: providers.elevenlabs_voice_provider
- test_timeline_voice.py | score=1 | reason=Imports affected module: providers.elevenlabs_voice_provider

## Context Files

- None

## Suggested Improvements

1. Start with targeted analysis
2. Confirm affected files
3. Create backup before any edit
4. Apply minimal changes only
5. Run verifier after change

## Recommended Safe Workflow

1. Review this upgrade plan
2. Confirm core files
3. Create project backup
4. Apply changes only after explicit user approval
5. Run verifier agent
6. Run project scanner
7. Update project_brain/current_state.md
8. Generate new CHAT_HANDOFF.md

## Approval Status

WAITING FOR USER APPROVAL

No file should be modified until user explicitly approves.