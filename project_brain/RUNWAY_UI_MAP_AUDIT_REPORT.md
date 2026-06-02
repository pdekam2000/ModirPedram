# RUNWAY UI MAP AUDIT REPORT

**Source:** `project_brain/runway_ui_mapping/runway_ui_map.json`
**Version:** runway_ui_mapper_v2
**Scanned at:** 2026-06-02T19:48:07Z
**Page:** https://app.runwayml.com/video-tools/teams/kamangarpedram/ai-tools/generate
**Title:** Generative Session | Runway AI

## Executive summary

| Metric | Value |
|---|---|
| Total scanned elements | **72** |
| Operator-confirmed labels (`labels`) | **0** |
| Observe-mode actions (`actions`) | **0** |
| CONFIRMED (this audit) | **0** |
| LIKELY (text/aria inference) | **12** |
| UNKNOWN | **60** |

**Learning state:** Only `--scan` was persisted. `labels` and `actions` are empty. Semantics in LIKELY are **audit inference**, not operator-taught mappings.

## Answers to audit questions

1. **How many controls were mapped?** — **72** visible DOM candidates with stable `element_id`s.
2. **Which have confirmed labels?** — **None** (`labels: {}`).
3. **Which are unlabeled?** — **All 72** at operator level; **60** lack text-based inference.
4. **Which are only inferred from text?** — **12** (LIKELY table).
5. **Which were observed changing UI?** — **None** (`actions: {}`).
6. **First Video Frame?** — **Scan yes:** `btn_010`. Not operator-confirmed.
7. **Reference Image Upload?** — **No** matching element in scan.
8. **Download button?** — **Partial:** `btn_016` (Download all). Not per-clip export.
9. **Gen-4.5?** — **Scan yes:** `btn_053`. Not operator-confirmed.
10. **Duration 10s?** — **Scan yes:** `btn_048` (preferred). Also native `select_002`.
11. **Aspect Ratio 16:9?** — **Scan yes:** `btn_047` (preferred). Also `el_001`, `select_001`.
12. **Generate?** — **Scan yes:** `btn_054`, `click_blocked: true`. Not operator-confirmed.
13. **Proven vs guessed?** — **All guessed**; no observe records; no operator labels.

## Priority controls

| Control | element_id | Status | Functionality |
|---|---|---|---|
| prompt_box | input_004 | LIKELY | Guessed — contenteditable; body shows 413/5000 chars |
| generate_button | btn_054 | LIKELY | Guessed — submit button; auto-click blocked |
| duration_10s | btn_048 | LIKELY | Guessed — text 10s + aria Duration |
| aspect_ratio_16_9 | btn_047 | LIKELY | Guessed — text 16:9 + aria Aspect ratio |
| gen45_option | btn_053 | LIKELY | Guessed — text Gen-4.5 + aria Video models |
| first_video_frame_upload | btn_010 | LIKELY | Guessed — upload region |
| download_button | btn_016 | LIKELY | Guessed — Download all (history UI) |
| reference_image_upload | — | NOT FOUND | — |
| try_it_now_button | — | NOT FOUND | Editor page; CTA not present |

## CONFIRMED CONTROLS

*None.* Run `python tools/runway_ui_mapper.py --label` to confirm semantics.

## LIKELY CONTROLS

*12 elements — identified from visible text / aria-label during scan only.*

| element_id | label | visible text | aria-label | selector | confidence | click_blocked | safe_click_allowed | how identified | behavior |
|---||---||---||---||---||---||---||---||---||---|
| btn_010 | first_video_frame_upload (inferred) | First Video Frame Upload |  | `div` | medium-high | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_016 | download_button (inferred) |  | Download all | `#react-aria9124564547-\:rmv\:` | medium | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_021 | prompt_view (inferred) |  | See full prompt | `#react-aria9124564547-\:rn6\:` | medium | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_025 | generated_video_card (inferred) |  |  | `video` | low-medium | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_046 | prompt_helper (inferred) |  | Enhance prompt | `#react-aria9124564547-\:rkg\:` | medium | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_047 | aspect_ratio_16_9 (inferred) | 16:9 | Aspect ratio | `#react-aria9124564547-\:rkk\:` | medium-high | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_048 | duration_10s (inferred) | 10s | Duration | `#react-aria9124564547-\:rku\:` | medium-high | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_053 | gen45_option (inferred) | Gen-4.5 | Video models | `#react-aria9124564547-\:rll\:` | medium-high | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_054 | generate_button (inferred) | Generate |  | `#react-aria9124564547-\:rlo\:` | medium-high | True | False | CDP scan text/aria inference | guessed (not observed) |
| el_001 | aspect_ratio_16_9 (inferred) | 16:9 |  | `label` | medium-high | False | True | CDP scan text/aria inference | guessed (not observed) |
| input_004 | prompt_box (inferred) | contrasting before/after frame highlighting runer  | Prompt | `div[aria-label="Prompt"]` | medium | False | True | CDP scan text/aria inference | guessed (not observed) |
| select_001 | aspect_ratio_16_9 (inferred) | 16:9 |  | `select` | medium-high | False | True | CDP scan text/aria inference | guessed (not observed) |

## UNKNOWN CONTROLS

*60 elements — no confident semantic label from text alone.*

| element_id | label | visible text | aria-label | selector | confidence | click_blocked | safe_click_allowed | how identified | behavior |
|---||---||---||---||---||---||---||---||---||---|
| btn_001 | (unlabeled) | Girl Runner Evidence Reveal |  | `button` | low | False | True | CDP scan DOM only | unknown |
| btn_002 | (unlabeled) |  | Open session switcher | `#react-aria9124564547-\:rj5\:` | low | False | True | CDP scan DOM only | unknown |
| btn_003 | (unlabeled) | Unlimited |  | `#credit-info-button` | low | False | True | CDP scan DOM only | unknown |
| btn_004 | (unlabeled) | 0/3 Quests |  | `#react-aria9124564547-\:rah\:` | low | False | True | CDP scan DOM only | unknown |
| btn_005 | (unlabeled) |  | Share session | `#react-aria9124564547-\:rjb\:` | low | False | True | CDP scan DOM only | unknown |
| btn_006 | (unlabeled) |  |  | `#react-aria9124564547-\:rjd\:` | low | False | True | CDP scan DOM only | unknown |
| btn_007 | (unlabeled) |  | Help | `#react-aria9124564547-\:rjf\:` | low | False | True | CDP scan DOM only | unknown |
| btn_008 | (unlabeled) |  | Reset settings | `#react-aria9124564547-\:rjq\:` | low | False | True | CDP scan DOM only | unknown |
| btn_009 | (unlabeled) |  | Sessions | `#react-aria9124564547-\:ri4\:` | low | False | True | CDP scan DOM only | unknown |
| btn_011 | (unlabeled) | Later |  | `#react-aria9124564547-\:rmg\:` | low | False | True | CDP scan DOM only | unknown |
| btn_012 | (unlabeled) | Enable |  | `#react-aria9124564547-\:rmi\:` | low | False | True | CDP scan DOM only | unknown |
| btn_013 | (unlabeled) | Don't show again |  | `#react-aria9124564547-\:rme\:` | low | False | True | CDP scan DOM only | unknown |
| btn_014 | (unlabeled) | Apps | Apps | `#react-aria9124564547-\:ri7\:` | low | False | True | CDP scan DOM only | unknown |
| btn_015 | (unlabeled) |  | Filter by media type: All media | `#react-aria9124564547-\:rmq\:` | low | False | True | CDP scan DOM only | unknown |
| btn_017 | (unlabeled) |  | Feed view | `button[aria-label="Feed view"]` | low | False | True | CDP scan DOM only | unknown |
| btn_018 | (unlabeled) |  | Grid view | `button[aria-label="Grid view"]` | low | False | True | CDP scan DOM only | unknown |
| btn_019 | (unlabeled) | Custom | Custom | `#react-aria9124564547-\:ri9\:` | low | False | True | CDP scan DOM only | unknown |
| btn_020 | (unlabeled) |  | Reuse settings | `#react-aria9124564547-\:rn3\:` | low | False | True | CDP scan DOM only | unknown |
| btn_022 | (unlabeled) |  | feedback | `#react-aria9124564547-\:rpc\:` | low | False | True | CDP scan DOM only | unknown |
| btn_023 | (unlabeled) |  | Hide output | `#react-aria9124564547-\:rn9\:` | low | False | True | CDP scan DOM only | unknown |
| btn_024 | (unlabeled) | Agent | Agent | `#react-aria9124564547-\:rib\:` | low | False | True | CDP scan DOM only | unknown |
| btn_026 | (unlabeled) | Recents | Recents | `#react-aria9124564547-\:rif\:` | low | False | True | CDP scan DOM only | unknown |
| btn_027 | (unlabeled) | Workflow | Workflow | `#react-aria9124564547-\:rih\:` | low | False | True | CDP scan DOM only | unknown |
| btn_028 | (unlabeled) | Upload | Upload | `#react-aria9124564547-\:rk2\:` | low | False | True | CDP scan DOM only | unknown |
| btn_029 | (unlabeled) |  | Select | `#react-aria9124564547-\:rk5\:` | low | False | True | CDP scan DOM only | unknown |
| btn_030 | (unlabeled) | Characters | Characters | `#react-aria9124564547-\:rij\:` | low | False | True | CDP scan DOM only | unknown |
| btn_031 | (unlabeled) |  | playback time | `media-time-display[aria-label="playback time"` | low | False | True | CDP scan DOM only | unknown |
| btn_032 | (unlabeled) |  | play | `media-play-button[aria-label="play"]` | low | False | True | CDP scan DOM only | unknown |
| btn_033 | (unlabeled) |  | mute | `media-mute-button[aria-label="mute"]` | low | False | True | CDP scan DOM only | unknown |
| btn_034 | (unlabeled) |  | Playback rate 1 | `media-playback-rate-menu-button[aria-label="P` | low | False | True | CDP scan DOM only | unknown |
| btn_035 | (unlabeled) |  | enter fullscreen mode | `media-fullscreen-button[aria-label="enter ful` | low | False | True | CDP scan DOM only | unknown |
| btn_036 | (unlabeled) | Apps | Actions | `#react-aria9124564547-\:rs9\:` | low | False | True | CDP scan DOM only | unknown |
| btn_037 | (unlabeled) | Use frame |  | `#react-aria9124564547-\:rsh\:` | low | False | True | CDP scan DOM only | unknown |
| btn_038 | (unlabeled) |  | Use frame options | `#react-aria9124564547-\:rsj\:` | low | False | True | CDP scan DOM only | unknown |
| btn_039 | (unlabeled) | Edit |  | `#react-aria9124564547-\:rsn\:` | low | False | True | CDP scan DOM only | unknown |

*… plus 25 additional UNKNOWN rows.*

## Full element inventory (all 72)

| element_id | label | visible text | aria-label | selector | confidence | click_blocked | safe_click_allowed | how identified | behavior |
|---||---||---||---||---||---||---||---||---||---|
| btn_001 | (unlabeled) | Girl Runner Evidence Reveal |  | `button` | low | False | True | CDP scan DOM only | unknown |
| btn_002 | (unlabeled) |  | Open session switcher | `#react-aria9124564547-\:rj5\:` | low | False | True | CDP scan DOM only | unknown |
| btn_003 | (unlabeled) | Unlimited |  | `#credit-info-button` | low | False | True | CDP scan DOM only | unknown |
| btn_004 | (unlabeled) | 0/3 Quests |  | `#react-aria9124564547-\:rah\:` | low | False | True | CDP scan DOM only | unknown |
| btn_005 | (unlabeled) |  | Share session | `#react-aria9124564547-\:rjb\:` | low | False | True | CDP scan DOM only | unknown |
| btn_006 | (unlabeled) |  |  | `#react-aria9124564547-\:rjd\:` | low | False | True | CDP scan DOM only | unknown |
| btn_007 | (unlabeled) |  | Help | `#react-aria9124564547-\:rjf\:` | low | False | True | CDP scan DOM only | unknown |
| btn_008 | (unlabeled) |  | Reset settings | `#react-aria9124564547-\:rjq\:` | low | False | True | CDP scan DOM only | unknown |
| btn_009 | (unlabeled) |  | Sessions | `#react-aria9124564547-\:ri4\:` | low | False | True | CDP scan DOM only | unknown |
| btn_010 | first_video_frame_upload (inferred) | First Video Frame Upload |  | `div` | medium-high | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_011 | (unlabeled) | Later |  | `#react-aria9124564547-\:rmg\:` | low | False | True | CDP scan DOM only | unknown |
| btn_012 | (unlabeled) | Enable |  | `#react-aria9124564547-\:rmi\:` | low | False | True | CDP scan DOM only | unknown |
| btn_013 | (unlabeled) | Don't show again |  | `#react-aria9124564547-\:rme\:` | low | False | True | CDP scan DOM only | unknown |
| btn_014 | (unlabeled) | Apps | Apps | `#react-aria9124564547-\:ri7\:` | low | False | True | CDP scan DOM only | unknown |
| btn_015 | (unlabeled) |  | Filter by media type: All media | `#react-aria9124564547-\:rmq\:` | low | False | True | CDP scan DOM only | unknown |
| btn_016 | download_button (inferred) |  | Download all | `#react-aria9124564547-\:rmv\:` | medium | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_017 | (unlabeled) |  | Feed view | `button[aria-label="Feed view"]` | low | False | True | CDP scan DOM only | unknown |
| btn_018 | (unlabeled) |  | Grid view | `button[aria-label="Grid view"]` | low | False | True | CDP scan DOM only | unknown |
| btn_019 | (unlabeled) | Custom | Custom | `#react-aria9124564547-\:ri9\:` | low | False | True | CDP scan DOM only | unknown |
| btn_020 | (unlabeled) |  | Reuse settings | `#react-aria9124564547-\:rn3\:` | low | False | True | CDP scan DOM only | unknown |
| btn_021 | prompt_view (inferred) |  | See full prompt | `#react-aria9124564547-\:rn6\:` | medium | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_022 | (unlabeled) |  | feedback | `#react-aria9124564547-\:rpc\:` | low | False | True | CDP scan DOM only | unknown |
| btn_023 | (unlabeled) |  | Hide output | `#react-aria9124564547-\:rn9\:` | low | False | True | CDP scan DOM only | unknown |
| btn_024 | (unlabeled) | Agent | Agent | `#react-aria9124564547-\:rib\:` | low | False | True | CDP scan DOM only | unknown |
| btn_025 | generated_video_card (inferred) |  |  | `video` | low-medium | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_026 | (unlabeled) | Recents | Recents | `#react-aria9124564547-\:rif\:` | low | False | True | CDP scan DOM only | unknown |
| btn_027 | (unlabeled) | Workflow | Workflow | `#react-aria9124564547-\:rih\:` | low | False | True | CDP scan DOM only | unknown |
| btn_028 | (unlabeled) | Upload | Upload | `#react-aria9124564547-\:rk2\:` | low | False | True | CDP scan DOM only | unknown |
| btn_029 | (unlabeled) |  | Select | `#react-aria9124564547-\:rk5\:` | low | False | True | CDP scan DOM only | unknown |
| btn_030 | (unlabeled) | Characters | Characters | `#react-aria9124564547-\:rij\:` | low | False | True | CDP scan DOM only | unknown |
| btn_031 | (unlabeled) |  | playback time | `media-time-display[aria-label="playback time"` | low | False | True | CDP scan DOM only | unknown |
| btn_032 | (unlabeled) |  | play | `media-play-button[aria-label="play"]` | low | False | True | CDP scan DOM only | unknown |
| btn_033 | (unlabeled) |  | mute | `media-mute-button[aria-label="mute"]` | low | False | True | CDP scan DOM only | unknown |
| btn_034 | (unlabeled) |  | Playback rate 1 | `media-playback-rate-menu-button[aria-label="P` | low | False | True | CDP scan DOM only | unknown |
| btn_035 | (unlabeled) |  | enter fullscreen mode | `media-fullscreen-button[aria-label="enter ful` | low | False | True | CDP scan DOM only | unknown |
| btn_036 | (unlabeled) | Apps | Actions | `#react-aria9124564547-\:rs9\:` | low | False | True | CDP scan DOM only | unknown |
| btn_037 | (unlabeled) | Use frame |  | `#react-aria9124564547-\:rsh\:` | low | False | True | CDP scan DOM only | unknown |
| btn_038 | (unlabeled) |  | Use frame options | `#react-aria9124564547-\:rsj\:` | low | False | True | CDP scan DOM only | unknown |
| btn_039 | (unlabeled) | Edit |  | `#react-aria9124564547-\:rsn\:` | low | False | True | CDP scan DOM only | unknown |
| btn_040 | (unlabeled) |  | Share | `#react-aria9124564547-\:rt6\:` | low | False | True | CDP scan DOM only | unknown |
| btn_041 | (unlabeled) |  | Favorite | `#react-aria9124564547-\:rt9\:` | low | False | True | CDP scan DOM only | unknown |
| btn_042 | (unlabeled) | 4K |  | `#react-aria9124564547-\:rtc\:` | low | False | True | CDP scan DOM only | unknown |
| btn_043 | (unlabeled) |  |  | `#react-aria9124564547-\:rth\:` | low | False | True | CDP scan DOM only | unknown |
| btn_044 | (unlabeled) |  |  | `#react-aria9124564547-\:rtf\:` | low | False | True | CDP scan DOM only | unknown |
| btn_045 | (unlabeled) |  | Presets | `#react-aria9124564547-\:rkb\:` | low | False | True | CDP scan DOM only | unknown |
| btn_046 | prompt_helper (inferred) |  | Enhance prompt | `#react-aria9124564547-\:rkg\:` | medium | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_047 | aspect_ratio_16_9 (inferred) | 16:9 | Aspect ratio | `#react-aria9124564547-\:rkk\:` | medium-high | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_048 | duration_10s (inferred) | 10s | Duration | `#react-aria9124564547-\:rku\:` | medium-high | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_049 | (unlabeled) |  | Advanced Settings | `#react-aria9124564547-\:rl7\:` | low | False | True | CDP scan DOM only | unknown |
| btn_050 | (unlabeled) |  | View generation cost | `#react-aria9124564547-\:rlc\:` | low | False | True | CDP scan DOM only | unknown |
| btn_051 | (unlabeled) |  | Dashboard | `a[aria-label="Dashboard"]` | low | False | True | CDP scan DOM only | unknown |
| btn_052 | (unlabeled) | Apps | Helpful Apps when generating videos | `#related-apps-trigger` | low | False | True | CDP scan DOM only | unknown |
| btn_053 | gen45_option (inferred) | Gen-4.5 | Video models | `#react-aria9124564547-\:rll\:` | medium-high | False | True | CDP scan text/aria inference | guessed (not observed) |
| btn_054 | generate_button (inferred) | Generate |  | `#react-aria9124564547-\:rlo\:` | medium-high | True | False | CDP scan text/aria inference | guessed (not observed) |
| btn_055 | (unlabeled) |  |  | `#react-aria9124564547-\:rim\:` | low | False | True | CDP scan DOM only | unknown |
| el_001 | aspect_ratio_16_9 (inferred) | 16:9 |  | `label` | medium-high | False | True | CDP scan text/aria inference | guessed (not observed) |
| el_002 | (unlabeled) | 2 seconds 3 seconds 4 seconds 5 seconds 6 seconds  |  | `label` | low | False | True | CDP scan DOM only | unknown |
| el_003 | (unlabeled) |  |  | `label` | low | False | True | CDP scan DOM only | unknown |
| el_004 | (unlabeled) | Image |  | `label:nth-of-type(1)` | low | False | True | CDP scan DOM only | unknown |
| el_005 | (unlabeled) | Video |  | `label:nth-of-type(2)` | low | False | True | CDP scan DOM only | unknown |
| el_006 | (unlabeled) | Audio |  | `label:nth-of-type(3)` | low | False | True | CDP scan DOM only | unknown |
| el_007 | (unlabeled) | All |  | `label:nth-of-type(1)` | low | False | True | CDP scan DOM only | unknown |
| el_008 | (unlabeled) | Favorited |  | `label:nth-of-type(2)` | low | False | True | CDP scan DOM only | unknown |
| el_009 | (unlabeled) | Downloaded |  | `label:nth-of-type(3)` | low | False | True | CDP scan DOM only | unknown |
| el_010 | (unlabeled) | 4K |  | `label:nth-of-type(4)` | low | False | True | CDP scan DOM only | unknown |
| input_001 | (unlabeled) |  |  | `input` | low | False | True | CDP scan DOM only | unknown |
| input_002 | (unlabeled) |  |  | `input` | low | False | True | CDP scan DOM only | unknown |
| input_003 | (unlabeled) |  |  | `input` | low | False | True | CDP scan DOM only | unknown |
| input_004 | prompt_box (inferred) | contrasting before/after frame highlighting runer  | Prompt | `div[aria-label="Prompt"]` | medium | False | True | CDP scan text/aria inference | guessed (not observed) |
| select_001 | aspect_ratio_16_9 (inferred) | 16:9 |  | `select` | medium-high | False | True | CDP scan text/aria inference | guessed (not observed) |
| select_002 | (unlabeled) | 2 seconds 3 seconds 4 seconds 5 seconds 6 seconds  |  | `select` | low | False | True | CDP scan DOM only | unknown |
| select_003 | (unlabeled) |  |  | `select` | low | False | True | CDP scan DOM only | unknown |

## Observe / actions

*Empty.* No before/after action records in JSON.

## Recommendations

1. `--label` key bindings: prompt→input_004, generate→btn_054, 10s→btn_048, 16:9→btn_047, gen45→btn_053, first frame→btn_010.
2. `--observe` while toggling duration/aspect menus to prove behavior.
3. Re-scan landing page for `try_it_now_button` if needed.
4. Prefer `btn_047`/`btn_048` over native `<select>` nodes (negative bbox).