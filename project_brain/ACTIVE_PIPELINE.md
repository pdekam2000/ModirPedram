# Active Pipeline

## Active Development Pipeline

Runtime Editing V1 is currently active.

## Working Flow

Text command -> Parser -> Extract Function -> Generate Patch -> Preview Diff -> Approve -> Apply -> Verify

## Maintenance Flow

After every major project change, run:

`python -m project_brain.auto_handoff_backup`

This refreshes the project brain and creates a backup.
