"""
MICRO TEST 6 — Direct download without browser UI.

Detects latest_video_card, inspects media URLs, attempts CDP/requests fetch only.
Never clicks Runway Download. No UI fallback when direct download is not possible.
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
from content_brain.execution.runway_phase_i_artifact_tracker import PhaseIArtifactTracker
from content_brain.execution.runway_phase_i_cdp_download import RunwayPhaseICdpDownloader
from content_brain.execution.runway_ui_map_loader import resolve_runway_ui_controls
from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator
from project_brain.run_phase_i_micro_tests import _pick_runway_page, _safe_http_urls

DEFAULT_REPORT = ROOT / "project_brain" / "runway_direct_download_test.json"
DEFAULT_MAP = ROOT / "project_brain" / "runway_ui_mapping" / "runway_ui_map.json"
DEFAULT_DEST = ROOT / "downloads" / "runway" / "test_direct_download.mp4"

MEDIA_INSPECT_SCRIPT = """({ cardFingerprint }) => {
    const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
    const buildFp = (root) => {
        const r = root.getBoundingClientRect();
        const t = normalize(root.innerText || root.textContent || '');
        const video = root.querySelector('video');
        const img = root.querySelector('img, canvas, picture');
        const cardType = video ? 'video' : (img ? 'image' : 'unknown');
        return [
            Math.round(r.left + window.scrollX),
            Math.round(r.top + window.scrollY),
            Math.round(r.width),
            Math.round(r.height),
            cardType,
            t.slice(0, 120),
        ].join('|');
    };
    let targetCard = null;
    const actionButtons = Array.from(document.querySelectorAll('[aria-label*="Actions"]'));
    for (const btn of actionButtons) {
        let card = btn;
        for (let depth = 0; depth < 12 && card; depth++) {
            if (card.querySelector && card.querySelector('img, canvas, video, picture')) break;
            card = card.parentElement;
        }
        if (!card) card = btn.parentElement || btn;
        if (buildFp(card) === cardFingerprint) {
            targetCard = card;
            break;
        }
    }
    if (!targetCard) {
        return { cardFound: false, videoCurrentSrc: '', videoSrc: '', sourceSrcs: [], hrefLinks: [], networkUrls: [], allUrls: [] };
    }
    const video = targetCard.querySelector('video');
    const videoCurrentSrc = video ? (video.currentSrc || '') : '';
    const videoSrc = video ? (video.src || '') : '';
    const sourceSrcs = [];
    if (video) {
        for (const source of video.querySelectorAll('source')) {
            const src = source.src || source.getAttribute('src') || '';
            if (src) sourceSrcs.push(src);
        }
    }
    const hrefLinks = [];
    for (const anchor of targetCard.querySelectorAll('a[href]')) {
        const href = anchor.href || '';
        if (href) hrefLinks.push(href);
    }
    const networkUrls = [];
    try {
        const entries = performance.getEntriesByType('resource') || [];
        const cardRect = targetCard.getBoundingClientRect();
        for (const entry of entries) {
            const name = String(entry.name || '');
            if (!name) continue;
            if (/\\.(mp4|m3u8|webm|mov)(\\?|$)/i.test(name) || /video|media|cdn|stream/i.test(name)) {
                networkUrls.push(name);
            }
        }
    } catch (_) {}
    const allUrls = Array.from(new Set(
        [videoCurrentSrc, videoSrc, ...sourceSrcs, ...hrefLinks, ...networkUrls].filter(Boolean)
    ));
    return {
        cardFound: true,
        videoCurrentSrc,
        videoSrc,
        sourceSrcs,
        hrefLinks,
        networkUrls: Array.from(new Set(networkUrls)).slice(0, 20),
        allUrls,
    };
}"""


def _classify_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    scheme = (parsed.scheme or "").lower()
    if scheme == "blob":
        return "blob"
    if scheme in {"http", "https"}:
        return scheme
    if scheme == "data":
        return "data"
    return scheme or "unknown"


def _pick_best_safe_url(urls: list[str]) -> str:
    safe = _safe_http_urls(urls)
    if not safe:
        return ""
    for url in safe:
        lowered = url.lower()
        if ".mp4" in lowered or "video" in lowered or "media" in lowered:
            return url
    return safe[0]


def _verify_media_signature(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "file_missing"
    size = path.stat().st_size
    if size <= 0:
        return False, "empty_file"
    header = path.read_bytes()[:32]
    if len(header) < 12:
        return False, "header_too_small"
    if header[4:8] == b"ftyp":
        return True, "mp4_ftyp"
    if header[:4] == b"\x1a\x45\xdf\xa3":
        return True, "webm_ebml"
    if header[8:12] == b"ftyp":
        return True, "mp4_ftyp_alt"
    if header[:3] == b"ID3":
        return True, "id3_prefixed_audio"
    return False, f"unknown_signature_hex={header[:8].hex()}"


def run_test(
    *,
    cdp_url: str,
    map_path: Path,
    dest_path: Path,
    clip_index: int = 1,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "test": "micro_test_6_direct_download",
        "latest_video_card_detected": False,
        "direct_download_possible": False,
        "detected_media_url": "",
        "url_type": "none",
        "downloaded_file_path": "",
        "file_size": 0,
        "verification_passed": False,
        "fallback_required": True,
        "safe_http_url_found": False,
        "blob_url_found": False,
        "browser_download_clicked": False,
        "ui_fallback_executed": False,
    }

    ok_socket, socket_msg = probe_cdp_socket(cdp_url)
    if not ok_socket:
        result["error"] = socket_msg
        return result
    ok_pw, pw_msg = probe_playwright_attach(cdp_url)
    if not ok_pw:
        result["error"] = pw_msg
        return result

    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    browser = None
    try:
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=15000)
        page, page_url, page_catalog = _pick_runway_page(browser)
        result["page_url"] = page_url
        result["page_catalog"] = page_catalog

        snap = resolve_runway_ui_controls(map_path=map_path)
        nav = MappedRunwayUINavigator(snapshot=snap, page=page, simulate=False)
        nav.configure_phase_i_artifact_tracking(
            project_id="micro_test_6",
            session_id="direct_dl",
            fallback_to_ui_download=False,
        )
        tracker = nav.phase_i_artifact_tracker()

        latest = nav.ensure_clip_video_card_assigned(clip_index)
        result["latest_video_card_detected"] = latest is not None and bool(
            latest and latest.card_fingerprint
        )
        if not result["latest_video_card_detected"]:
            result["error"] = (
                "No latest_video_card — open Runway video tool with a completed video card."
            )
            return result

        fp = latest.card_fingerprint
        result["latest_video_card"] = latest.to_dict()

        inspection: dict[str, Any] = {}
        try:
            raw = page.evaluate(MEDIA_INSPECT_SCRIPT, {"cardFingerprint": fp})
            inspection = raw if isinstance(raw, dict) else {}
        except Exception as exc:
            inspection = {"error": str(exc)}

        tracker_urls = tracker.extract_media_urls_for_role(
            PhaseIArtifactTracker.clip_video_role(clip_index)
        )
        all_urls: list[str] = []
        for key in (
            "videoCurrentSrc",
            "videoSrc",
            "sourceSrcs",
            "hrefLinks",
            "networkUrls",
            "allUrls",
        ):
            value = inspection.get(key)
            if isinstance(value, list):
                all_urls.extend(str(u) for u in value if u)
            elif isinstance(value, str) and value:
                all_urls.append(value)
        all_urls.extend(tracker_urls)
        unique_urls = list(dict.fromkeys(u for u in all_urls if u))

        result["inspection"] = {
            **inspection,
            "tracker_media_urls": tracker_urls,
            "unique_urls_collected": unique_urls,
        }

        blob_urls = [u for u in unique_urls if _classify_url(u) == "blob"]
        safe_urls = _safe_http_urls(unique_urls)
        result["blob_url_found"] = len(blob_urls) > 0
        result["safe_http_url_found"] = len(safe_urls) > 0
        result["direct_download_possible"] = result["safe_http_url_found"]

        if not result["direct_download_possible"]:
            result["fallback_required"] = True
            result["url_type"] = "blob" if result["blob_url_found"] else "none"
            return result

        chosen = _pick_best_safe_url(unique_urls)
        result["detected_media_url"] = chosen
        result["url_type"] = _classify_url(chosen)
        result["fallback_required"] = False

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_path.exists():
            dest_path.unlink()

        downloader = RunwayPhaseICdpDownloader(
            download_dir=dest_path.parent,
            tracker=tracker,
            simulate=False,
            project_id="micro_test_6",
            page=page,
            ui_download_click=None,
        )
        size = downloader._fetch_via_page(chosen, dest_path)
        method = "cdp_page_fetch"
        if size <= 0:
            size = downloader._fetch_via_requests(chosen, dest_path)
            method = "requests"
        result["download_method"] = method
        result["downloaded_file_path"] = str(dest_path.resolve()) if dest_path.is_file() else ""
        result["file_size"] = int(dest_path.stat().st_size) if dest_path.is_file() else 0

        verified, sig = _verify_media_signature(dest_path)
        result["verification_passed"] = verified and result["file_size"] > 0
        result["media_signature"] = sig
        result["pass"] = result["verification_passed"]
        if not result["verification_passed"]:
            result["fallback_required"] = True
            result["direct_download_possible"] = False
        return result
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
    parser = argparse.ArgumentParser(description="Micro Test 6 — direct download without browser UI")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    parser.add_argument("--map-path", default=str(DEFAULT_MAP))
    parser.add_argument("--out", default=str(DEFAULT_REPORT))
    parser.add_argument("--dest", default=str(DEFAULT_DEST))
    parser.add_argument("--clip-index", type=int, default=1)
    args = parser.parse_args()

    print("[micro_test_6] Direct download without browser UI")
    report = run_test(
        cdp_url=args.cdp_url,
        map_path=Path(args.map_path),
        dest_path=Path(args.dest),
        clip_index=max(1, args.clip_index),
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"latest_video_card_detected: {report.get('latest_video_card_detected')}")
    print(f"safe_http_url_found: {report.get('safe_http_url_found')}")
    print(f"blob_url_found: {report.get('blob_url_found')}")
    print(f"direct_download_possible: {report.get('direct_download_possible')}")
    print(f"detected_media_url: {str(report.get('detected_media_url', ''))[:100]}")
    print(f"downloaded_file_path: {report.get('downloaded_file_path')}")
    print(f"file_size: {report.get('file_size')}")
    print(f"verification_passed: {report.get('verification_passed')}")
    print(f"fallback_required: {report.get('fallback_required')}")
    print(f"report: {out_path}")
    if report.get("error"):
        print(f"error: {report['error']}")
    return 0 if report.get("verification_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
