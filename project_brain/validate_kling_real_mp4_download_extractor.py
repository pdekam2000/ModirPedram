"""Validate KLING-REAL-MP4-DOWNLOAD-EXTRACTOR."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_real_mp4_download_extractor import (  # noqa: E402
    EXTRACTOR_VERSION,
    extract_real_kling_mp4,
    inspect_file_candidate,
    is_rejected_placeholder_url,
    quarantine_invalid_candidate,
    verify_extracted_kling_mp4,
)
from content_brain.execution.kling_multishot_live_engine import MIN_REAL_MP4_BYTES  # noqa: E402


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg"))


def _make_test_mp4(path: Path, *, seconds: float = 60.0) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg required")
    path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=green:s=720x1280:d={seconds}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={seconds}",
            "-c:v",
            "libx264",
            "-b:v",
            "900k",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0 or not path.is_file():
        raise RuntimeError(proc.stderr or proc.stdout or "ffmpeg failed")
    if path.stat().st_size < MIN_REAL_MP4_BYTES:
        raise RuntimeError(f"test mp4 too small: {path.stat().st_size}")


def test_placeholder_url_rejected() -> None:
    bad = "https://d3phaj0sisr2ct.cloudfront.net/app/empty-state/studio-empty-state.webm"
    _pass("empty_state_url_rejected", is_rejected_placeholder_url(bad))
    good = "https://dnznrvs05pmza.cloudfront.net/kling-3-0-pro/123/untitled.mp4"
    _pass("kling_url_not_rejected", not is_rejected_placeholder_url(good))


def test_fake_small_file_rejected(tmp: Path) -> None:
    tiny = tmp / "tiny.mp4"
    tiny.write_bytes(b"not-a-real-mp4")
    verify = verify_extracted_kling_mp4(tiny)
    _pass("fake_small_rejected", not verify.get("is_real_mp4"))
    _pass("ffprobe_required", verify.get("ffprobe_ok") is False)


def test_html_placeholder_rejected(tmp: Path) -> None:
    html = tmp / "fake.mp4"
    html.write_text("<html><body>placeholder</body></html>", encoding="utf-8")
    inspect = inspect_file_candidate(html)
    _pass("html_container", inspect.get("container") == "html")
    verify = verify_extracted_kling_mp4(html)
    _pass("html_rejected", not verify.get("is_real_mp4"))


def test_webm_quarantined_not_registered(tmp: Path) -> None:
    webm = tmp / "clip.webm"
    webm.write_bytes(b"\x1a\x45\xdf\xa3" + b"\x00" * 500_000)
    clip_dir = tmp / "c1"
    clip_dir.mkdir(parents=True, exist_ok=True)
    dest = clip_dir / "clip_1.mp4"
    quarantined = quarantine_invalid_candidate(webm, clip_dir)
    _pass("webm_quarantined", bool(quarantined))
    _pass("webm_not_at_dest", not dest.is_file())
    verify = verify_extracted_kling_mp4(webm if webm.is_file() else Path(quarantined))
    if webm.is_file():
        _pass("webm_not_real_mp4", not verify.get("is_real_mp4"))


def test_real_mp4_accepted(tmp: Path) -> None:
    if not _ffmpeg_available():
        print("[SKIP] real_mp4_accepted — ffmpeg unavailable")
        return
    mp4 = tmp / "real.mp4"
    _make_test_mp4(mp4, seconds=60.0)
    verify = verify_extracted_kling_mp4(mp4)
    _pass("real_mp4_exists", verify.get("exists") is True)
    _pass("real_mp4_size", int(verify.get("size_bytes") or 0) > MIN_REAL_MP4_BYTES)
    _pass("real_mp4_ffprobe", verify.get("ffprobe_ok") is True)
    _pass("real_mp4_duration", float(verify.get("duration_seconds") or 0) >= 5.0)
    _pass("real_mp4_accepted", verify.get("is_real_mp4") is True)


def test_recovery_does_not_click_generate() -> None:
    frame_src = (ROOT / "content_brain/execution/kling_frame_to_video_live_engine.py").read_text(encoding="utf-8")
    recover_block = frame_src.split("def recover_kling_frame_output", 1)[1].split("\n\n__all__", 1)[0]
    extractor_src = (ROOT / "content_brain/execution/kling_real_mp4_download_extractor.py").read_text(encoding="utf-8")
    _pass("recover_no_generate", "generate.locator.click" not in recover_block)
    _pass("extractor_no_generate", "generate.locator.click" not in extractor_src)
    _pass("extractor_declares_no_generate", "Never clicks Generate" in extractor_src)


def test_recovery_report_includes_attempted_methods(tmp: Path) -> None:
    class _FakePage:
        pass

    result = extract_real_kling_mp4(
        _FakePage(),
        tmp / "out.mp4",
        run_id="validate_extract",
        clip_index=1,
        clip_dir=tmp,
        recovery_mode=True,
    )
    _pass("attempted_methods_present", bool(result.attempted_methods))
    _pass("method_attempts_present", bool(result.method_attempts))
    report = tmp / "mp4_extract_report.json"
    _pass("extract_report_written", report.is_file())
    payload = report.read_text(encoding="utf-8")
    _pass("report_lists_methods", "attempted_methods" in payload)


def test_extractor_version() -> None:
    _pass("extractor_version", EXTRACTOR_VERSION == "kling_real_mp4_download_extractor_v2")


def main() -> None:
    test_placeholder_url_rejected()
    test_extractor_version()
    test_recovery_does_not_click_generate()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        test_fake_small_file_rejected(tmp)
        test_html_placeholder_rejected(tmp)
        test_webm_quarantined_not_registered(tmp)
        test_real_mp4_accepted(tmp)
        test_recovery_report_includes_attempted_methods(tmp)
    print("validate_kling_real_mp4_download_extractor: all checks passed")


if __name__ == "__main__":
    main()
