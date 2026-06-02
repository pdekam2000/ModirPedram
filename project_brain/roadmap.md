# MODIRAGENT OS ROADMAP

## CURRENT STATUS

V1 FOUNDATION COMPLETED

Completed systems:
- Project Scanner
- Project Reader
- State Writer
- Task Router
- Safety Guard
- Command Runner
- Rollback Manager
- OpenAI Provider
- Architect Agent
- CHAT_HANDOFF Generator
- Project Brain System

Architecture status:
- Stable
- Modular
- Local-first
- Provider-agnostic
- Safety-first

---

# DEVELOPMENT ROADMAP

## PHASE 1 — FOUNDATION HARDENING

### STEP 21
Add "Run Architect Agent" option into main.py

Status:
- Done

Goal:
- Run architect agent directly from CLI.

---

### STEP 22
Improve task_router.py stage detection logic

Status:
- Done

Goal:
- Prevent false AUTOMATION_READY state detection.

---

### STEP 23
Improve current_state.md generation

Status:
- Done

Goal:
- Detect all new files and folders automatically.
- Improve reporting quality.

---

### STEP 24
Improve CHAT_HANDOFF.md generator

Status:
- Done

Goal:
- Add latest modules automatically.
- Add execution status.
- Add architecture summary.

---

### STEP 25
Fill pipeline_map.md

Status:
- Done

Goal:
- Document how modules communicate.

---

## PHASE 2 — ORCHESTRATION CORE

### STEP 26
Create core/orchestrator.py

Status:
- Done

Goal:
- Build central project orchestration system.

Features:
- load_project_brain()
- analyze_goal()
- build_execution_plan()
- execute_agents()
- write_updates()

---

### STEP 27
Create dependency_mapper.py

Status:
- Done

Goal:
- Detect imports and file relationships.

---

### STEP 28
Create impact_analyzer.py

Status:
- Done

Goal:
- Detect which files may break after edits.

---

### STEP 29
Create memory_agent.py

Status:
-  Done

Goal:
- Build long-term project memory system.

---

### STEP 30
Connect orchestrator to main.py

Status:
-  Done

Goal:
- Run orchestration from CLI.

---

## PHASE 3 — INTELLIGENT AGENTS

### STEP 31
Create coder_agent.py

### STEP 32
Create verifier_agent.py

### STEP 33
Create refactor_agent.py

### STEP 34
Create qa_agent.py

### STEP 35
Create planner_agent.py

---

## PHASE 4 — ADVANCED MEMORY

### STEP 36
Create semantic project memory

### STEP 37
Create vector memory

### STEP 38
Create project snapshots

### STEP 39
Create semantic search system

---

## PHASE 5 — FULL AI PROJECT OS

### STEP 40
Autonomous multi-agent execution

### STEP 41
Automatic project planning

### STEP 42
Automatic bug detection

### STEP 43
Automatic architecture optimization

### STEP 44
Automatic code refactoring

### STEP 45
Cross-LLM orchestration

---

# LONG TERM GOAL

Build a professional AI Project Operating System capable of:
- managing large AI/software projects
- orchestrating multiple agents
- preventing architecture collapse
- preserving long-term project memory
- supporting multiple providers
- enabling autonomous software development
---

# PHASE 2 - AI CONTENT FACTORY

## Goal

Transform ModirAgent OS from a general AI project management system into an AI Content Factory that can create short-form video content pipelines for TikTok, Instagram Reels, and YouTube Shorts.

## Target Workflow

1. User provides a niche, topic, or content direction.
2. System researches or generates daily/trending content ideas.
3. System creates:
   - SEO title
   - SEO description
   - SEO hashtags
   - Keywords
4. System writes a short story/script.
5. System creates 3 connected video clip prompts.
6. Each video prompt must visually continue from the previous clip.
7. Later: send prompts to Hailuo AI API.
8. Later: generate video clips.
9. Later: add voiceover/audio.
10. Later: stitch/merge clips into one final vertical video.

## Core Agents Planned

### 1. Trend Agent

Status: NEXT

Purpose:
- Accept a niche/topic from the user.
- Generate daily/trending short-form video ideas.
- Focus on viral potential, audience interest, hooks, and platform suitability.

Output:
- Content idea
- Hook
- Viral angle
- Target audience
- Platform fit
- SEO keywords

### 2. SEO Agent

Status: PLANNED

Purpose:
- Create SEO title, description, hashtags, and keywords.

### 3. Story Agent

Status: PLANNED

Purpose:
- Turn selected content idea into a short cinematic script.

### 4. Video Prompt Agent

Status: PLANNED

Purpose:
- Create 3 connected video prompts for AI video generation.
- Each clip must continue visually from the previous clip.

### 5. Hailuo Provider

Status: PLANNED

Purpose:
- Connect to Hailuo AI API later.
- Send video prompts.
- Retrieve generated clips.

### 6. Voiceover Agent

Status: PLANNED

Purpose:
- Generate or prepare voiceover/audio instructions.

### 7. Stitching Agent

Status: PLANNED

Purpose:
- Merge 3 clips into one final vertical video.
- Prepare output for TikTok, Instagram Reels, and YouTube Shorts.

## Safety Rules

- No auto-editing yet.
- Every risky code change requires backup.
- main.py must stay small.
- Agents should write plans and outputs, not modify project files automatically.
- Project Brain remains the source of truth.
- Preserve previous settings and architecture.
## Important Architecture Decisions

### Hailuo Video Length Rule

Hailuo AI generates 10-second video clips.

Therefore, one complete final short video must be created from:

- Clip 1: 10 seconds
- Clip 2: 10 seconds
- Clip 3: 10 seconds

Total final video length:

- 30 seconds

Important rule:

The 3 clips must visually continue each other so the viewer does not feel they are watching 3 separate videos.

### API-First Architecture

From this phase forward, the system must be designed as API-first.

Required providers:

- OpenAI Provider
- Hailuo Video Provider
- Future Voice Provider
- Future Stitching Provider

Agents should be built so they can later use APIs without rewriting the whole system.

### Content Modes

The AI Content Factory must support more than one output type.

Planned modes:

1. AI Video Mode
   - 3 connected 10-second Hailuo clips
   - stitched into one final short video

2. Slide Video Mode
   - educational slide-style video
   - text + visuals + voiceover
   - useful for skincare, beauty, facts, tutorials, and explainers

### Updated Build Order

1. Content Factory Profile
2. Trend Agent
3. SEO Agent
4. API Provider Structure
5. OpenAI Provider upgrade
6. Hailuo Provider placeholder
7. Story Agent
8. Clip Prompt Agent
9. Slide Video Agent
10. Voiceover Agent
11. Stitching Agent

---

# COMMERCIAL & SECURITY ROADMAP (FUTURE — NOT IMPLEMENTED)

**Full specification:** `project_brain/COMMERCIAL_ARCHITECTURE_ROADMAP.md`

Long-term layers required before public SaaS or sellable desktop release. Aligns with dual deployment (local desktop / SaaS / hybrid local-agent).

## Planned Layers

### SaaS Security Layer (before public SaaS)
- MFA
- Argon2id password hashing
- Session security
- Tenant isolation
- Encrypted secrets vault
- Audit logs

### Desktop Licensing Layer (before desktop product release)
- Online license validation
- Machine binding
- Activation limits
- License tiers
- Heartbeat validation
- Offline grace period

### Creator Identity Layer (first public-facing release)
- Visible branding
- About dialog attribution
- License attribution
- Metadata attribution
- Build signatures

## Mandatory Review Gates

| Gate | Before |
|---|---|
| **Phase Security Audit** | Public SaaS release |
| **Phase License & Protection Audit** | Sellable desktop release |

**Do not implement these layers until their deployment mode is in active development.**