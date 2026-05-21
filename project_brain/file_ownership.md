# FILE OWNERSHIP

## CORE RULES

- No agent may rewrite unrelated files.
- No agent may edit files outside project root.
- All code changes must pass safety_guard.py.
- main.py must stay minimal.
- Every module should have one responsibility.
- Every important change should be logged.
- Project brain files must always stay readable.

---

# FILE RESPONSIBILITIES

## main.py
Owner:
- System Coordinator

Responsibilities:
- CLI menu
- connect modules
- minimal orchestration only

Must NOT:
- contain business logic
- contain huge functions
- contain provider logic

---

## core/project_scanner.py
Owner:
- Scanner Agent

Responsibilities:
- scan folders/files
- ignore protected folders
- generate current_state.md

Must NOT:
- edit unrelated files
- execute commands

---

## core/project_reader.py
Owner:
- Reader Agent

Responsibilities:
- load project brain
- build summaries
- prepare context for agents

Must NOT:
- modify code files

---

## core/task_router.py
Owner:
- Router Agent

Responsibilities:
- detect project stage
- suggest next steps
- later dispatch agents

Must NOT:
- directly edit project files

---

## core/safety_guard.py
Owner:
- Safety Agent

Responsibilities:
- validate file edits
- protect sensitive paths
- enforce safety rules

Must NOT:
- bypass protections

---

## project_brain/*
Owner:
- QA/Memory Agent

Responsibilities:
- documentation
- memory
- state tracking
- decisions
- next steps

Must NOT:
- contain secrets or API keys