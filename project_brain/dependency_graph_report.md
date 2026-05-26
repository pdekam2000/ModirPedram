# DEPENDENCY GRAPH REPORT

Generated at: 2026-05-26 22:34:41

Target input: `providers.runway_video_provider`
Resolved target file: `providers/runway_video_provider.py`

Estimated change risk: **CRITICAL**

## Direct Dependencies

Files/modules that the target file directly or indirectly uses.

### Dependency Level 1

- None

## Reverse Dependencies / Impact Chain

Files that depend on the target file and may be affected by changes.

### Impact Level 1

- core/video_provider_router.py

### Impact Level 2

- engines/video_generation_engine.py
- pipelines/full_video_pipeline.py
- test_full_ai_video_pipeline.py

### Impact Level 3

- None

## Safe Upgrade Recommendation

1. Review target file first
2. Review Level 1 impact files
3. Create backup before edits
4. Apply minimal change
5. Run verifier
6. Run related tests if available
7. Update project_brain

## Approval Status

WAITING FOR USER APPROVAL

No file was modified by this engine.