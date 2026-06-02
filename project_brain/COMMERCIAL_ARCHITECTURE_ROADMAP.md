# Commercial & Security Architecture Roadmap

**Status:** Architectural requirement — **not implemented**  
**Created:** 2026-05-28  
**Related:** Modern GUI Architecture (dual deployment: local desktop / SaaS / hybrid local-agent)

This document defines long-term layers required before **public SaaS release** or **sellable desktop release**. Core product logic remains UI-independent and deployment-agnostic until these phases are scheduled.

---

## Deployment Context (Reminder)

| Mode | Description |
|---|---|
| **A — Local Desktop** | Sellable package; backend + browser automation on user PC |
| **B — SaaS Cloud** | Hosted dashboard; multi-user; server-managed jobs |
| **C — Hybrid** | SaaS dashboard + local execution agent for browser providers |

All layers below must respect:

- No hardcoded localhost in core
- No single-user assumptions in core (`TenantContext`: `user_id`, `workspace_id`, `project_id`, `channel_id`, `execution_id`)
- Clean API boundary; no secrets in frontend
- UI logic separate from backend logic

---

## 1. SaaS Security Layer

**Phase:** Pre-public SaaS (after multi-tenant API + auth foundation)  
**Status:** Planned — do not implement until SaaS Mode B is in scope

### Requirements

| Capability | Specification |
|---|---|
| **MFA** | TOTP and/or WebAuthn; enforce per workspace policy; recovery codes stored hashed |
| **Password hashing** | **Argon2id** (not bcrypt/scrypt defaults); per-user salt; work-factor configurable |
| **Session security** | HttpOnly secure cookies or short-lived JWT + refresh rotation; device/session list; revoke all sessions |
| **Tenant isolation** | Row-level + storage-prefix isolation by `workspace_id`; no cross-tenant reads in Session Explorer, budget, or provider config |
| **Encrypted secrets** | Provider API keys and OAuth tokens in server vault (KMS/envelope encryption); never returned to frontend except masked status |
| **Audit logs** | Append-only audit trail: auth events, approval actions, budget blocks, execution start/cancel, admin changes; retention policy per tier |

### Architectural placement

```
Frontend → API Gateway (auth, MFA, session) → TenantContext → Core Backend
                    ↓
              AuditLogService
              SecretsVault (encrypted)
```

### Non-goals (V1 SaaS security)

- Custom password rules beyond NIST baseline
- SOC2 certification (process, not code — track as business milestone)

---

## 2. Desktop Licensing Layer

**Phase:** Pre-desktop product release (Mode A sellable package)  
**Status:** Planned — do not implement until desktop packaging path is active

### Requirements

| Capability | Specification |
|---|---|
| **Online license validation** | Activate against license server; signed license payload; optional air-gapped enterprise path later |
| **Machine binding** | Stable machine fingerprint (OS + hardware hash); limit activations per license |
| **Activation limits** | Configurable seats per tier (e.g. 1 / 3 / unlimited enterprise) |
| **License tiers** | Feature flags by tier: channels, executions/month, providers, cloud sync, support level |
| **Heartbeat validation** | Periodic online check (configurable interval); degrade gracefully on failure |
| **Offline grace period** | Allow N days offline after last successful validation; read-only or limited execution when expired |

### Architectural placement

```
Desktop Launcher → LicenseService (local) ↔ License API (online)
                        ↓
              TenantContext.license_mode + tier
                        ↓
              FeatureGate (core, not UI)
```

### Design rules

- License checks in **core/API**, not React components
- `license_mode`: `perpetual | subscription | trial | none`
- No secrets in license file — signed claims only
- Heartbeat must not block local read-only Session Explorer during grace period (policy TBD)

---

## 3. Creator Identity Layer

**Phase:** Parallel with first public-facing release (desktop or SaaS)  
**Status:** Planned — attribution and branding requirements

### Requirements

| Surface | Requirement |
|---|---|
| **Visible branding** | Product name, logo, theme tokens consistent across web + desktop shell |
| **About dialog** | Version, build date, creator attribution (Pedram Kamangar / ModirAgent OS) |
| **License attribution** | Third-party OSS notices; provider terms references |
| **Metadata attribution** | Exported briefs, videos, session JSON optional `generator` / `creator` / `software_version` fields |
| **Build signatures** | Signed desktop binaries (Windows Authenticode / macOS notarization roadmap); reproducible build metadata in `BUILD_INFO.json` |

### Architectural placement

```
config/branding.json (or env) → API GET /meta/product → Frontend About + footer
build pipeline → embed VERSION, GIT_SHA, BUILD_DATE
export adapters → inject metadata blocks
```

### Non-goals

- White-label multi-brand SaaS in V1 (design hooks only via `workspace_id` branding later)

---

## 4. Security Review Gates

**Mandatory audits before release.** No public SaaS or sellable desktop without passing the relevant gate.

### Phase Security Audit (before public SaaS release)

| Area | Review items |
|---|---|
| Auth | MFA, session fixation, CSRF, rate limiting, Argon2id params |
| Tenancy | Cross-tenant IDOR tests; storage path traversal |
| Secrets | Vault encryption, rotation, no logs leakage |
| API | Input validation, authorization on every mutating endpoint |
| WebSocket | Auth on connect; workspace scope on subscriptions |
| Agent (Mode C) | Token scope, job injection, upload integrity |
| Audit | Immutable audit log; admin access logged |
| Dependencies | CVE scan; pinned supply chain |

**Exit criteria:** Documented findings remediated or accepted with sign-off; penetration test recommended for B2B tier.

### Phase License & Protection Audit (before desktop release)

| Area | Review items |
|---|---|
| License | Forgery resistance; clock tampering; VM cloning abuse |
| Machine binding | Privacy (GDPR-friendly fingerprint); false positive rate |
| Offline grace | No indefinite bypass; clear UX when expired |
| Binary | Code signing; tamper detection |
| Secrets | Local `.env` / keychain; no keys in installer |
| Update channel | Signed updates; downgrade protection |

**Exit criteria:** License bypass attempts documented; tier gates enforced in core; legal review of EULA alignment.

---

## Implementation Order (Future — Not Now)

| Order | Layer | Depends on |
|---|---|---|
| 1 | `TenantContext` + storage adapter | Core refactor (10A foundation) |
| 2 | Creator Identity (metadata + About) | Web UI shell |
| 3 | Desktop Licensing Layer | Mode A packaging |
| 4 | SaaS Security Layer | Mode B auth + Postgres |
| 5 | **License & Protection Audit** | Desktop GA |
| 6 | **Security Audit** | SaaS GA |
| 7 | Hybrid agent security hardening | Mode C |

---

## Explicit Non-Actions (Current Phase)

- Do **not** implement MFA, Argon2id, or license server now
- Do **not** add auth to local Session Explorer V1
- Do **not** store user secrets in frontend or session JSON
- Do **not** skip audit gates for “soft launch”

---

## Cross-References

- Dual deployment GUI architecture: Phase 10A Modern GUI report (local / SaaS / hybrid)
- Execution session store: `content_brain/execution/session_store.py` — must gain `workspace_id` before SaaS
- Patch approval (`execution/approval_engine.py`) remains separate from execution approval gate (9F)

---

*Architectural requirement only. Implementation tracked in future phases.*
