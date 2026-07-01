# Global Credit Safety Rule — Free-Credit-First Testing

**Version:** `credit_safety_guard_v1`  
**Module:** `content_brain/execution/credit_safety_guard.py`  
**Default:** `free_credit_first = true`

---

## Rule

All live/provider tests must start with free credits, free quota, free mode, trial credits, or the cheapest non-paid-safe path whenever available.

Do **not** spend paid credits until the full chain is validated.

---

## Test order (mandatory)

1. **A** — dry-run / validation only  
2. **B** — UI/runtime simulation  
3. **C** — free-credit live test  
4. **D** — cheapest short live test  
5. **E** — full paid/provider test (explicit operator approval only)

---

## Before any provider live run — record

- provider  
- model  
- credit_mode (`free` / `trial` / `paid` / `unknown` / `dry_run`)  
- available free credits / quota (if detectable)  
- whether run may spend paid credits  
- operator confirmation state  

---

## Runtime metadata (every run report)

- `credit_mode`  
- `paid_credit_risk`  
- `free_credit_checked`  
- `operator_paid_approval`  
- `estimated_credit_cost` (if known)  

---

## Block condition

If `paid_credit_risk` is true and `operator_paid_approval` is false:

```
Paid credit execution blocked. Free-credit-first rule requires explicit approval.
```

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MODIR_FREE_CREDIT_FIRST` | `true` | Block paid unless approved |
| `MODIR_OPERATOR_PAID_APPROVAL` | `false` | Global paid override |
| `MODIR_FREE_CREDITS_AVAILABLE` | unset | `true` / `false` / count — free quota signal |
| `MODIR_RUNWAY_FREE_CREDITS_AVAILABLE` | unset | Provider-specific override |

---

## Payload flags

| Field | Default | Purpose |
|-------|---------|---------|
| `free_credit_first` | `true` | Enforce rule |
| `free_credit_mode` | `false` | Explicit free-credit live test |
| `operator_paid_approval` | `false` | Allow paid execution |
| `credit_mode` | `""` | `free` / `trial` / `paid` |
| `dry_run` | `false` | Step A — no credits |
| `live_retest` | `false` | 30s retest — stricter free-first |

Paid approval also accepted via legacy: `confirm_credit_spend` + `approved_by`.

---

## Applied to

- pwmap runner (`pwmap_runway_agent_adapter.py`)  
- Product Studio generate (`product_studio_service.py`, `product_multiclip_orchestrator.py`)  
- Kling product run (`kling_product_run.py`)  
- Operations policy (`operations_policy.py`)  
- Future Runway/Kling/Hailuo live tests  

---

## Validation

```bash
python project_brain/validate_credit_safety_guard.py
```
