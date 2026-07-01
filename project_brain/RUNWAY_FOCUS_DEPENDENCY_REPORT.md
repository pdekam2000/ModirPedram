# RUNWAY FOCUS DEPENDENCY REPORT

Generated: 2026-06-20T21:42:52.569959+00:00
Probe version: runway_focus_dependency_probe_v1

## Conclusion

- **focus dependent:** likely_yes
- **generate queued before operator click:** likely_yes
- **delay cause:** background_tab_or_hidden_document_no_activation
- **recommended fix:** Before Generate: call page.bring_to_front() + CDP Page.bringToFront, wait until document.visibilityState==='visible' && document.hasFocus(), log focus_probe (now instrumented), retry click with force=true only if probe still blocked.

## Static code forensic

- **bring_to_front_used:** False
- **cdp_page_bring_to_front_used:** False
- **visibility_state_checked:** False
- **connect_over_cdp:** True
- **ensure_generate_page_navigates:** True
- **generate_click_instrumented:** True
- **find_page_no_activation:** True

## Live CDP snapshot

- **timestamp:** 2026-06-20T21:42:52.528020+00:00
- **page_url:** https://app.runwayml.com/video-tools/teams/kamangarpedram/ai-tools/generate?tool=video&mode=tools&sessionId=4b91f4d1-3dfe-4cbd-85f8-ea2d4957c4da
- **visibility_state:** visible
- **document_hidden:** False
- **has_focus:** True
- **ready_state:** complete
- **overlay_count:** 0
- **overlays:** 0 item(s)
- **generate_button:** {'label': 'Generate', 'disabled': False, 'ariaDisabled': None, 'visible': True, 'pointerEvents': 'auto', 'opacity': '1', 'inViewport': True}
- **tab_active_hint:** foreground
- **errors:** []

## Artifact focus probes

- No instrumented live_run_result.json files found yet (re-run live engine after probe wiring)

## Operator observation (reported)

Sometimes automation appears idle until the operator clicks the Chrome window; Generate then executes immediately. This matches a focus/visibility-triggered UI wake-up: CDP attaches to an existing tab without `bring_to_front`, Chrome may keep `document.visibilityState='hidden'` while unfocused, and React handlers or rAF-throttled render can defer the Generate effect until the window is activated.

## Instrumentation added

- `content_brain/execution/runway_focus_dependency_probe.py`
- Before every Generate: logs `visibilityState`, `hasFocus`, overlays, Generate interactability
- Timestamps: `queued_at`, `click_started_at`, `click_finished_at` in `live_run_result.json` → `focus_probe`
- Forensic runner: `python project_brain/run_runway_focus_dependency_forensic.py`

## Notes

- no_page_activation_before_generate_in_code
- runtime_attaches_via_cdp_to_existing_chrome_tab
- generate_tab_selected_without_foreground_activation
