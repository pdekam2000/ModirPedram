# Execution Flow

## Runtime Editing V1

Text Command
-> RuntimeCommandParser
-> FunctionExtractor
-> RuntimePatchGeneratorAgent
-> Diff Preview
-> Approval Gate
-> Real Apply
-> Backup
-> Verifier

## Brain + Backup Flow

Run:

`python -m project_brain.auto_handoff_backup`

Then:

Project Scan
-> Read Runtime State
-> Generate FULL_PROJECT_HANDOFF.md
-> Generate CHAT_HANDOFF.md
-> Update current_state.md
-> Update SYSTEM_MAP.md
-> Update EXECUTION_FLOW.md
-> Update ACTIVE_PIPELINE.md
-> Update next_steps.md
-> Append change_log.md
-> Create backup ZIP
-> Create backup_manifest.json
-> Create latest_backup_report.md
