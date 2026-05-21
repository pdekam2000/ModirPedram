# PIPELINE MAP

## MODIRAGENT OS - CURRENT MODULE FLOW

### 1. User Interface Layer

File:
- main.py

Role:
- Shows CLI menu
- Receives user choice
- Calls the correct module
- Must stay minimal

---

### 2. Project Brain Layer

Folder:
- project_brain/

Files:
- current_state.md
- roadmap.md
- decisions.md
- known_issues.md
- pipeline_map.md
- file_ownership.md
- change_log.md
- next_steps.md
- CHAT_HANDOFF.md

Role:
- Stores long-term project memory
- Stores current status
- Stores architecture decisions
- Stores next steps
- Provides handoff context for new chats

---

### 3. Core Intelligence Layer

Folder:
- core/

Files:
- project_scanner.py
- state_writer.py
- project_reader.py
- task_router.py
- safety_guard.py
- handoff_generator.py

Role:
- Scan project files
- Create/update project brain
- Read project memory
- Detect current project stage
- Suggest next steps
- Protect unsafe file changes
- Generate chat handoff context

---

### 4. Execution Layer

Folder:
- execution/

Files:
- command_runner.py
- rollback_manager.py

Role:
- Run safe terminal commands
- Block dangerous commands
- Create backups before risky changes
- Restore backups when needed

---

### 5. Provider Layer

Folder:
- providers/

Files:
- openai_provider.py

Role:
- Keep AI provider logic isolated
- Avoid hardcoding provider logic into main.py
- Prepare for future provider switching

Future providers:
- anthropic_provider.py
- gemini_provider.py
- local_llm_provider.py
- deepseek_provider.py

---

### 6. Agent Layer

Folder:
- agents/

Files:
- architect_agent.py

Role:
- Analyze architecture
- Write architecture decisions
- Keep project structure stable

Future agents:
- coder_agent.py
- verifier_agent.py
- refactor_agent.py
- qa_agent.py
- memory_agent.py
- planner_agent.py

---

# CURRENT EXECUTION FLOW

## Scan Project

main.py
-> core/project_scanner.py
-> project_brain/current_state.md

---

## Initialize Brain

main.py
-> core/state_writer.py
-> project_brain/*.md

---

## Read Project Summary

main.py
-> core/project_reader.py
-> reads project_brain/*.md
-> prints summary

---

## Analyze Project

main.py
-> core/task_router.py
-> project_brain/next_steps.md

---

## Generate Handoff

main.py
-> core/handoff_generator.py
-> project_brain/CHAT_HANDOFF.md

---

## Run Architect Agent

main.py
-> agents/architect_agent.py
-> project_brain/decisions.md
-> project_brain/change_log.md

---

# DESIGN RULES

- main.py must stay small.
- Core logic stays inside core/.
- Execution logic stays inside execution/.
- Provider logic stays inside providers/.
- Agent logic stays inside agents/.
- Project memory stays inside project_brain/.
- Every future edit should respect file_ownership.md.
- Every risky edit should create a backup first.