"""
Phase I micro-tests on the current Runway CDP page (read-only + direct fetch).

Does NOT run full Phase I, does NOT click Use Frame, does NOT click browser Download UI.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.browser_connectivity_probe import probe_cdp_socket, probe_playwright_attach
from content_brain.execution.runway_phase_i_artifact_tracker import (
    DOWNLOAD_LABELS,
    PLAYBACK_LABELS,
    ROLE_LATEST_VIDEO,
    USE_FRAME_LABELS,
    PhaseIArtifactTracker,
)
from content_brain.execution.runway_phase_i_cdp_download import (
    RunwayPhaseICdpDownloadConfig,
    RunwayPhaseICdpDownloader,
)
from content_brain.execution.runway_phase_i_download_tracker import default_runway_download_dir
from content_brain.execution.runway_ui_map_loader import resolve_runway_ui_controls
from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator

DEFAULT_REPORT = ROOT / "project_brain" / "runway_phase_i_micro_test_report.json"
DEFAULT_MAP = ROOT / "project_brain" / "runway_ui_mapping" / "runway_ui_map.json"

def _is_runway_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return "runwayml.com" in host or "runway.ml" in host


def _page_card_stats(page: Any) -> dict[str, int]:
    try:
        payload = page.evaluate(
            """() => {
                const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
                const actionButtons = Array.from(document.querySelectorAll('[aria-label*="Actions"]'));
                let image = 0;
                let video = 0;
                for (const btn of actionButtons) {
                    let card = btn;
                    for (let depth = 0; depth < 12 && card; depth++) {
                        if (card.querySelector && card.querySelector('img, canvas, video, picture')) break;
                        card = card.parentElement;
                    }
                    if (!card) card = btn.parentElement || btn;
                    if (card.querySelector('video')) video += 1;
                    else if (card.querySelector('img, canvas, picture')) image += 1;
                }
                return { actions: actionButtons.length, image, video };
            }"""
        )
    except Exception:
        return {"actions": 0, "image": 0, "video": 0}
    if not isinstance(payload, dict):
        return {"actions": 0, "image": 0, "video": 0}
    return {
        "actions": int(payload.get("actions") or 0),
        "image": int(payload.get("image") or 0),
        "video": int(payload.get("video") or 0),
    }


def _pick_runway_page(browser: Any) -> tuple[Any, str, list[dict[str, Any]]]:
    catalog: list[dict[str, Any]] = []
    best_page = None
    best_url = ""
    best_score = -1
    for context in browser.contexts:
        for page in context.pages:
            url = str(getattr(page, "url", "") or "")
            if not _is_runway_url(url):
                continue
            stats = _page_card_stats(page)
            entry = {"url": url, **stats}
            catalog.append(entry)
            score = stats["actions"] + stats["image"] * 2 + stats["video"] * 10
            lowered = url.lower()
            if "tool=video" in lowered or "&tool=video" in lowered:
                score += 25
            if "generate" in lowered:
                score += 5
            if "sessionid" in lowered:
                score += 2
            entry["score"] = score
            if score > best_score:
                best_score = score
                best_page = page
                best_url = url
    if best_page is None:
        for context in browser.contexts:
            for page in context.pages:
                url = str(getattr(page, "url", "") or "")
                if page and url and "chrome://" not in url and "devtools://" not in url:
                    return page, url, catalog
    if best_page is None:
        raise RuntimeError("No usable browser page found on CDP session")
    return best_page, best_url, catalog


def _safe_http_urls(urls: list[str]) -> list[str]:
    safe: list[str] = []
    for url in urls:
        parsed = urlparse(str(url or "").strip())
        if parsed.scheme in {"http", "https"}:
            safe.append(str(url).strip())
    return safe


def run_micro_tests(*, cdp_url: str, map_path: Path, clip_index: int = 1) -> dict[str, Any]:
    report: dict[str, Any] = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "phase_i_micro_tests",
        "cdp_url": cdp_url,
        "full_phase_i_run": False,
        "use_frame_clicked": False,
        "browser_ui_download_clicked": False,
        "tests": {},
        "pass": False,
    }

    ok_socket, socket_msg = probe_cdp_socket(cdp_url)
    report["cdp_socket"] = {"ok": ok_socket, "message": socket_msg}
    if not ok_socket:
        report["error"] = socket_msg
        return report

    ok_pw, pw_msg = probe_playwright_attach(cdp_url)
    report["cdp_playwright"] = {"ok": ok_pw, "message": pw_msg}
    if not ok_pw:
        report["error"] = pw_msg
        return report

    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    browser = None
    try:
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=15000)
        page, page_url, page_catalog = _pick_runway_page(browser)
        report["page_url"] = page_url
        report["page_catalog"] = page_catalog

        snap = resolve_runway_ui_controls(map_path=map_path)
        nav = MappedRunwayUINavigator(snapshot=snap, page=page, simulate=False)
        nav.configure_phase_i_artifact_tracking(
            project_id="phase_i_micro_test",
            session_id=f"micro_{datetime.now().strftime('%H%M%S')}",
            fallback_to_ui_download=False,
        )
        tracker = nav.phase_i_artifact_tracker()
        tracker.page = page

        candidates = tracker.scan_artifact_cards()
        report["candidates"] = {
            "total": len(candidates),
            "image": [
                {
                    "index": c.get("cardIndex"),
                    "fingerprint": c.get("cardFingerprint"),
                    "bottom": c.get("cardBottom"),
                    "buttons": (c.get("buttonsVisible") or [])[:8],
                }
                for c in candidates
                if str(c.get("cardType") or "") == "image"
            ],
            "video": [
                {
                    "index": c.get("cardIndex"),
                    "fingerprint": c.get("cardFingerprint"),
                    "bottom": c.get("cardBottom"),
                    "buttons": (c.get("buttonsVisible") or [])[:8],
                    "media_src": str(c.get("mediaSrc") or "")[:120],
                }
                for c in candidates
                if str(c.get("cardType") or "") == "video"
            ],
            "unknown": [
                {
                    "index": c.get("cardIndex"),
                    "fingerprint": c.get("cardFingerprint"),
                    "card_type": c.get("cardType"),
                }
                for c in candidates
                if str(c.get("cardType") or "") not in {"image", "video"}
            ],
        }

        latest = nav.ensure_clip_video_card_assigned(clip_index)
        latest_mirror = tracker.get_latest_video_card()
        report["latest_video_card"] = {
            "detected": latest is not None,
            "role": ROLE_LATEST_VIDEO,
            "clip_index": clip_index,
            "card": latest.to_dict() if latest else None,
            "mirror_matches_clip": bool(
                latest
                and latest_mirror
                and latest.card_fingerprint == latest_mirror.card_fingerprint
            ),
        }

        if latest is None or not latest.card_fingerprint:
            report["error"] = (
                "latest_video_card not detected — no video cards on selected page. "
                "Open Runway generate with tool=video and at least one completed video card."
            )
            report["tests"]["detect_latest_video_card"] = False
            report["tests"]["list_candidates"] = len(candidates) > 0
            report["pass"] = False
            return report

        report["tests"]["detect_latest_video_card"] = True
        fp = latest.card_fingerprint

        download_scope = tracker.audit_control_scope(fp, label_kind="download")
        playback_scope = tracker.audit_control_scope(fp, label_kind="playback")
        use_frame_scope = tracker.audit_control_scope(fp, label_kind="use_frame")

        scoped_download_visible = tracker.label_visible_on_latest_video_card(DOWNLOAD_LABELS)
        scoped_playback_visible = tracker.label_visible_on_latest_video_card(PLAYBACK_LABELS)
        scoped_use_frame_visible = tracker.label_visible_on_latest_video_card(USE_FRAME_LABELS)

        controls_scoped = bool(
            download_scope.get("scopedOk")
            and playback_scope.get("scopedOk")
            and use_frame_scope.get("scopedOk")
        )
        report["controls_scoped_in_latest_video_card"] = {
            "summary": {
                "global_vs_in_card": {
                    "download": {
                        "global": download_scope.get("globalMatches"),
                        "in_card": download_scope.get("inCardMatches"),
                        "leaked_outside_card": download_scope.get("leakedGlobalMatches"),
                    },
                    "playback": {
                        "global": playback_scope.get("globalMatches"),
                        "in_card": playback_scope.get("inCardMatches"),
                        "leaked_outside_card": playback_scope.get("leakedGlobalMatches"),
                    },
                    "use_frame": {
                        "global": use_frame_scope.get("globalMatches"),
                        "in_card": use_frame_scope.get("inCardMatches"),
                        "leaked_outside_card": use_frame_scope.get("leakedGlobalMatches"),
                    },
                },
                "leaked_controls_outside_latest_video_card": {
                    "download": download_scope.get("leakedSamples") or [],
                    "playback": playback_scope.get("leakedSamples") or [],
                    "use_frame": use_frame_scope.get("leakedSamples") or [],
                },
            },
            "download": {
                "tracker_visible": scoped_download_visible,
                "audit": download_scope,
            },
            "playback": {
                "tracker_visible": scoped_playback_visible,
                "audit": playback_scope,
            },
            "use_frame": {
                "read_only_visibility": scoped_use_frame_visible,
                "clicked": False,
                "audit": use_frame_scope,
            },
            "pass": controls_scoped,
        }
        report["tests"]["controls_scoped_in_latest_video_card"] = controls_scoped

        media_urls = tracker.extract_media_urls_for_role(PhaseIArtifactTracker.clip_video_role(clip_index))
        safe_urls = _safe_http_urls(media_urls)
        report["media_urls"] = {
            "all_detected": media_urls,
            "safe_http_https": safe_urls,
        }

        config = RunwayPhaseICdpDownloadConfig(
            download_strategy="cdp_preferred",
            fallback_to_ui_download=False,
            session_id=report.get("latest_video_card", {}).get("card", {}).get("role", "micro"),
        )
        downloader = RunwayPhaseICdpDownloader(
            download_dir=default_runway_download_dir(ROOT),
            tracker=tracker,
            simulate=False,
            project_id="phase_i_micro_test",
            config=config,
            page=page,
            ui_download_click=None,
        )
        attempt = downloader.download_clip(clip_index)
        report["direct_download"] = attempt.to_dict()
        report["fallback_required"] = not attempt.downloaded and not safe_urls
        report["tests"]["direct_download_without_ui"] = bool(attempt.downloaded)
        report["tests"]["fallback_required_when_no_safe_url"] = (
            True if not safe_urls else not report["fallback_required"]
        )

        tracker.write_diagnostics(
            context="phase_i_micro_test",
            extra={"report_path": str(DEFAULT_REPORT)},
        )
        downloader.write_diagnostics(attempt)

        required = [
            "detect_latest_video_card",
            "controls_scoped_in_latest_video_card",
        ]
        if safe_urls:
            required.append("direct_download_without_ui")
        else:
            required.append("fallback_required_when_no_safe_url")

        report["pass"] = all(report["tests"].get(key) for key in required)
        return report
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass
        try:
            playwright.stop()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase I micro-tests on live Runway CDP page")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    parser.add_argument("--map-path", default=str(DEFAULT_MAP))
    parser.add_argument("--clip-index", type=int, default=1)
    parser.add_argument("--out", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    print("[run_phase_i_micro_tests] Phase I micro-tests (no full run, no Use Frame click)")
    report = run_micro_tests(
        cdp_url=args.cdp_url,
        map_path=Path(args.map_path),
        clip_index=max(1, args.clip_index),
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"page_url: {report.get('page_url', '')}")
    for entry in report.get("page_catalog") or []:
        print(
            f"  tab: video={entry.get('video')} image={entry.get('image')} "
            f"actions={entry.get('actions')} score={entry.get('score', '?')} "
            f"{str(entry.get('url', ''))[:90]}"
        )
    print(f"candidates: total={report.get('candidates', {}).get('total', 0)} "
          f"video={len(report.get('candidates', {}).get('video', []))} "
          f"image={len(report.get('candidates', {}).get('image', []))}")
    latest = report.get("latest_video_card") or {}
    print(f"latest_video_card: detected={latest.get('detected')} "
          f"fp={(latest.get('card') or {}).get('card_fingerprint', '')[:60]}")
    scoped = report.get("controls_scoped_in_latest_video_card") or {}
    print(f"controls_scoped: pass={scoped.get('pass')}")
    print(f"direct_download: downloaded={report.get('direct_download', {}).get('downloaded')} "
          f"strategy={report.get('direct_download', {}).get('strategy')}")
    print(f"fallback_required: {report.get('fallback_required')}")
    print(f"safe_urls: {len((report.get('media_urls') or {}).get('safe_http_https') or [])}")
    print(f"overall_pass: {report.get('pass')}")
    print(f"report: {out_path}")

    for name, ok in sorted((report.get("tests") or {}).items()):
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

    if report.get("error"):
        print(f"error: {report['error']}")
        return 1
    return 0 if report.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
