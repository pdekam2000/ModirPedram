"""
Phase I — CDP/network-preferred clip download with UI fallback.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

from content_brain.execution.kling_real_mp4_download_extractor import is_rejected_placeholder_url
from content_brain.execution.runway_phase_i_artifact_tracker import (
    DOWNLOAD_LABELS,
    PhaseIArtifactTracker,
)
from content_brain.execution.runway_phase_i_download_tracker import (
    RunwayPhaseIDownloadTracker,
    default_runway_download_dir,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOWNLOAD_DIAGNOSTICS = ROOT / "project_brain" / "runway_phase_i_download_diagnostics.json"

DOWNLOAD_STRATEGY_CDP_PREFERRED = "cdp_preferred"
STRATEGY_CDP_URL = "cdp_url"
STRATEGY_CDP_FETCH = "cdp_fetch"
STRATEGY_UI_FALLBACK = "ui_fallback"
STRATEGY_DIR_VERIFY = "dir_verify"

_BLOB_URL_RE = re.compile(r"^blob:", re.I)


class PageLike(Protocol):
    def evaluate(self, script: str, arg: Any = None) -> Any: ...


@dataclass
class ClipDownloadAttempt:
    clip_index: int
    strategy: str = ""
    scoped_to_card: bool = False
    card_fingerprint: str = ""
    detected_media_urls: list[str] = field(default_factory=list)
    file_path: str = ""
    file_size_bytes: int = 0
    downloaded: bool = False
    fallback_reason: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "strategy": self.strategy,
            "scoped_to_card": self.scoped_to_card,
            "card_fingerprint": self.card_fingerprint,
            "detected_media_urls": list(self.detected_media_urls),
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "downloaded": self.downloaded,
            "fallback_reason": self.fallback_reason,
            "notes": list(self.notes),
        }


@dataclass
class RunwayPhaseICdpDownloadConfig:
    download_strategy: str = DOWNLOAD_STRATEGY_CDP_PREFERRED
    fallback_to_ui_download: bool = True
    session_id: str = ""


class RunwayPhaseICdpDownloader:
    def __init__(
        self,
        *,
        download_dir: Path | str,
        tracker: PhaseIArtifactTracker,
        simulate: bool = False,
        project_id: str = "phase_i",
        config: RunwayPhaseICdpDownloadConfig | None = None,
        page: PageLike | None = None,
        ui_download_click: Callable[[], None] | None = None,
    ) -> None:
        self.download_dir = Path(download_dir).resolve()
        self.tracker = tracker
        self.simulate = simulate
        self.project_id = project_id
        self.config = config or RunwayPhaseICdpDownloadConfig()
        self.page = page
        self.ui_download_click = ui_download_click
        self.dir_tracker = RunwayPhaseIDownloadTracker(
            self.download_dir,
            simulate=simulate,
            project_id=project_id,
        )
        self.attempts: dict[int, ClipDownloadAttempt] = {}

    def _session_slug(self) -> str:
        sid = str(self.config.session_id or "").strip()
        if not sid:
            return "session"
        return sid.replace(":", "-")[:24]

    def _target_filename(self, clip_index: int) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = (
            f"runway_clip_{clip_index}_{self._session_slug()}_{stamp}.mp4"
        )
        return self.download_dir / name

    @staticmethod
    def _is_downloadable_url(url: str) -> bool:
        cleaned = str(url or "").strip()
        if not cleaned or _BLOB_URL_RE.match(cleaned):
            return False
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"}:
            return False
        return True

    def _fetch_via_page(self, url: str, dest: Path) -> int:
        if self.page is None:
            return 0
        payload = self.page.evaluate(
            """async (mediaUrl) => {
                try {
                    const response = await fetch(mediaUrl);
                    if (!response.ok) {
                        return { ok: false, error: `http_${response.status}` };
                    }
                    const blob = await response.blob();
                    const buffer = await blob.arrayBuffer();
                    const bytes = new Uint8Array(buffer);
                    let binary = '';
                    const chunk = 0x8000;
                    for (let i = 0; i < bytes.length; i += chunk) {
                        binary += String.fromCharCode.apply(
                            null,
                            bytes.subarray(i, i + chunk)
                        );
                    }
                    return { ok: true, data: btoa(binary), size: bytes.length };
                } catch (err) {
                    return { ok: false, error: String(err) };
                }
            }""",
            url,
        )
        if not isinstance(payload, dict) or not payload.get("ok"):
            return 0
        import base64

        raw = base64.b64decode(str(payload.get("data") or ""))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        return int(payload.get("size") or len(raw))

    def _fetch_via_requests(self, url: str, dest: Path) -> int:
        try:
            import requests
        except ImportError:
            return 0
        response = requests.get(
            url,
            stream=True,
            timeout=300,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "video/mp4,*/*"},
        )
        if response.status_code != 200:
            return 0
        total = 0
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
                    total += len(chunk)
        return total

    def download_clip(
        self,
        clip_index: int,
        *,
        role: str | None = None,
    ) -> ClipDownloadAttempt:
        index = max(1, int(clip_index))
        clip_role = role or PhaseIArtifactTracker.clip_video_role(index)
        card = self.tracker.assign_latest_video_card_for_clip(index)
        if card is None:
            card = self.tracker.get_assigned(clip_role)
        attempt = ClipDownloadAttempt(clip_index=index)
        if card is not None:
            attempt.scoped_to_card = True
            attempt.card_fingerprint = card.card_fingerprint
            self.tracker.ensure_starter_not_used_for_clip_ops(index)

        urls = self.tracker.extract_media_urls_for_role(clip_role)
        attempt.detected_media_urls = list(urls)
        dest = self._target_filename(index)

        for url in urls:
            if not self._is_downloadable_url(url):
                attempt.notes.append(f"skip_non_http_url:{url[:40]}")
                continue
            if is_rejected_placeholder_url(url):
                attempt.notes.append(f"skip_placeholder_url:{url[:80]}")
                continue
            if self.simulate:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b"simulate-phase-i-clip")
                size = dest.stat().st_size
            else:
                size = self._fetch_via_page(url, dest)
                if size <= 0:
                    size = self._fetch_via_requests(url, dest)
            if size > 0 and dest.is_file() and dest.stat().st_size > 0:
                attempt.strategy = STRATEGY_CDP_FETCH if not self.simulate else STRATEGY_CDP_URL
                attempt.file_path = str(dest.resolve())
                attempt.file_size_bytes = int(dest.stat().st_size)
                attempt.downloaded = True
                attempt.notes.append(
                    "simulate_cdp_url" if self.simulate else f"cdp_fetch_ok:{url[:80]}"
                )
                self.attempts[index] = attempt
                self._register_dir_record(index, attempt)
                self.write_diagnostics(attempt)
                return attempt
            attempt.notes.append(f"cdp_fetch_failed:{url[:80]}")

        if self.config.fallback_to_ui_download:
            attempt.fallback_reason = "no_safe_direct_url"
            clicked = False
            if card is not None:
                clicked = self.tracker.click_label_on_latest_video_card(DOWNLOAD_LABELS)
            if clicked:
                attempt.notes.append("scoped_ui_download_click")
            elif self.ui_download_click is not None:
                self.ui_download_click()
                attempt.notes.append("scoped_ui_download_delegate")
            else:
                attempt.notes.append("scoped_ui_download_failed_no_global_fallback")
            record = self.dir_tracker.verify_clip_download(index)
            if record.downloaded and record.file_size_bytes > 0:
                attempt.strategy = STRATEGY_UI_FALLBACK
                attempt.file_path = record.file_path
                attempt.file_size_bytes = record.file_size_bytes
                attempt.downloaded = True
            else:
                attempt.strategy = STRATEGY_DIR_VERIFY
                attempt.notes.extend(record.notes)
        else:
            record = self.dir_tracker.verify_clip_download(index)
            if record.downloaded:
                attempt.strategy = STRATEGY_DIR_VERIFY
                attempt.file_path = record.file_path
                attempt.file_size_bytes = record.file_size_bytes
                attempt.downloaded = True

        self.attempts[index] = attempt
        self.write_diagnostics(attempt)
        return attempt

    def _register_dir_record(self, clip_index: int, attempt: ClipDownloadAttempt) -> None:
        from content_brain.execution.runway_phase_i_download_tracker import ClipDownloadRecord

        record = ClipDownloadRecord(
            clip_index=clip_index,
            downloaded=attempt.downloaded,
            file_path=attempt.file_path,
            file_size_bytes=attempt.file_size_bytes,
            verified_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            notes=list(attempt.notes),
        )
        self.dir_tracker.records.append(record)
        if attempt.file_path:
            self.dir_tracker._assigned_paths.add(attempt.file_path)

    def write_diagnostics(self, attempt: ClipDownloadAttempt) -> None:
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "clip_index": attempt.clip_index,
            "download_strategy_config": self.config.download_strategy,
            "fallback_to_ui_download": self.config.fallback_to_ui_download,
            "chosen_download_strategy": attempt.strategy,
            "scoped_to_card": attempt.scoped_to_card,
            "card_fingerprint": attempt.card_fingerprint,
            "detected_media_urls": attempt.detected_media_urls,
            "fallback_reason": attempt.fallback_reason,
            "file_verification": {
                "path": attempt.file_path,
                "size_bytes": attempt.file_size_bytes,
                "downloaded": attempt.downloaded,
            },
            "tracker_assignments": self.tracker.to_report_summary(),
            "notes": attempt.notes,
        }
        DEFAULT_DOWNLOAD_DIAGNOSTICS.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_DOWNLOAD_DIAGNOSTICS.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def report_fields(self, clip_count: int = 3) -> dict[str, Any]:
        base = self.dir_tracker.report_fields(clip_count)
        for index in range(1, clip_count + 1):
            attempt = self.attempts.get(index)
            if attempt is None:
                continue
            base[f"clip_{index}_download_strategy"] = attempt.strategy
            base[f"clip_{index}_download_scoped_to_card"] = attempt.scoped_to_card
        return base


__all__ = [
    "ClipDownloadAttempt",
    "DEFAULT_DOWNLOAD_DIAGNOSTICS",
    "DOWNLOAD_STRATEGY_CDP_PREFERRED",
    "RunwayPhaseICdpDownloadConfig",
    "RunwayPhaseICdpDownloader",
    "STRATEGY_CDP_FETCH",
    "STRATEGY_UI_FALLBACK",
]
