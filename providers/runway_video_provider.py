"""
Runway REST API video provider — Phase 11E-b hardened.

Uses unified config (11E-a), bounded polling, cancel checkpoints, error classifier.
Text-to-video only; browser mode unchanged elsewhere.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from content_brain.execution.runway_config import (
    RUNWAY_API_ROUTER_KEY,
    RunwayConfigResolver,
    RunwayConfigSnapshot,
)
from providers.runway_api_errors import (
    PROVIDER_VERSION,
    RunwayCancelledError,
    RunwayProviderError,
    raise_from_http,
)
from providers.runway_artifact_utils import (
    CAPABILITY_TEXT_TO_VIDEO,
    MIN_ARTIFACT_BYTES,
    MODE_API,
    finalize_download_artifact,
    mark_clip_results_partial,
    partial_artifact_bundle,
)
from providers.runway_error_classifier import classify_runway_error

TASK_STATUS_SUCCEEDED = "SUCCEEDED"
TASK_STATUS_FAILED = "FAILED"
TASK_STATUS_CANCELLED = "CANCELLED"
TASK_STATUS_PENDING = frozenset({"PENDING", "QUEUED", "IN_QUEUE"})
TASK_STATUS_RUNNING = frozenset({"RUNNING", "PROCESSING", "IN_PROGRESS"})

CancelCheck = Callable[[], bool]


class RunwayVideoProvider:
    """Runway API text-to-video provider with unified config and bounded polling."""

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        config_resolver: RunwayConfigResolver | None = None,
        config_snapshot: RunwayConfigSnapshot | None = None,
        cancel_check: CancelCheck | None = None,
        requests_module: Any | None = None,
        skip_config_guards: bool = False,
    ):
        load_dotenv()
        self._requests_module = requests_module
        self._cancel_check = cancel_check
        self._partial_paths: list[str] = []
        self.clip_results: list[dict[str, Any]] = []
        self.last_task_metadata: dict[str, Any] | None = None

        resolver = config_resolver or RunwayConfigResolver(project_root)
        self._config = config_snapshot or resolver.resolve()
        self.config_snapshot = self._config

        if not skip_config_guards:
            self._assert_api_ready()

        api_key_env = self._config.api_key_env
        self.api_key = os.getenv(api_key_env, "").strip()
        if not self.api_key and not skip_config_guards:
            raise RunwayProviderError(
                f"{api_key_env} not found in environment",
                code="CREDENTIALS_MISSING",
            )

        self.base_url = (self._config.api_base_url or "").rstrip("/")
        if not self.base_url and not skip_config_guards:
            raise RunwayProviderError(
                "Runway API base URL is not configured",
                code="API_ENDPOINT_NOT_CONFIGURED",
            )

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Runway-Version": os.getenv("RUNWAY_API_VERSION", "2024-11-06"),
            "Content-Type": "application/json",
        }

        self.model = os.getenv("RUNWAY_VIDEO_MODEL", "gen4.5")
        self.ratio = os.getenv("RUNWAY_VIDEO_RATIO", "1280:720")
        self.duration = int(os.getenv("RUNWAY_VIDEO_DURATION", "5"))

        self.poll_interval = max(1, int(os.getenv("RUNWAY_POLL_INTERVAL", "10")))
        self.max_attempts = max(1, int(os.getenv("RUNWAY_MAX_ATTEMPTS", "60")))
        default_max_poll = self.poll_interval * self.max_attempts
        self.max_poll_seconds = max(
            self.poll_interval,
            int(os.getenv("RUNWAY_MAX_POLL_SECONDS", str(default_max_poll))),
        )
        self.max_prompt_chars = int(os.getenv("RUNWAY_MAX_PROMPT_CHARS", "950"))

        family_entry = resolver.mode_catalog.get_family("runway") or {}
        browser_config = family_entry.get("browser_config") or {}
        download_dir = browser_config.get("download_dir") or "downloads/runway"
        self.output_dir = Path(str(download_dir))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _requests(self) -> Any:
        if self._requests_module is None:
            import requests as requests_lib

            self._requests_module = requests_lib
        return self._requests_module

    def _assert_api_ready(self) -> None:
        if not self._config.api_enabled_in_registry:
            raise RunwayProviderError(
                "Runway API mode is disabled in provider_registry.json",
                code="PROVIDER_DISABLED",
                details={"provider_disabled": True},
            )
        if not self._config.api_key_present:
            raise RunwayProviderError(
                f"Missing {self._config.api_key_env} for Runway API mode",
                code="CREDENTIALS_MISSING",
            )
        if not self._config.api_base_url_valid:
            raise RunwayProviderError(
                f"Invalid Runway API base URL ({self._config.api_base_url_source})",
                code="API_ENDPOINT_NOT_CONFIGURED",
            )

    def _check_cancel(self, phase: str) -> None:
        check = self._cancel_check
        if check and check():
            raise RunwayCancelledError(
                f"Runway API cancelled during {phase}",
                partial_paths=list(self._partial_paths),
                phase=phase,
            )

    @staticmethod
    def _wrap_error(exc: BaseException, *, http_status: int | None = None, details: dict | None = None) -> RunwayProviderError:
        if isinstance(exc, RunwayProviderError):
            return exc
        if isinstance(exc, RunwayCancelledError):
            return exc
        code = classify_runway_error(exc, http_status=http_status, context=details)
        return RunwayProviderError(str(exc), code=code, http_status=http_status, details=details, cause=exc)

    def clean_prompt(self, prompt: str) -> str:
        text = str(prompt).strip()
        text = " ".join(text.split())
        if len(text) <= self.max_prompt_chars:
            return text
        cut = text[: self.max_prompt_chars]
        split_at = max(cut.rfind("."), cut.rfind(","))
        if split_at > 300:
            cut = cut[: split_at + 1]
        print(f"[Runway] Prompt shortened: {len(text)} -> {len(cut)} chars")
        return cut.strip()

    def generate_single_clip(
        self,
        prompt: str,
        index: int,
        *,
        cancel_check: CancelCheck | None = None,
    ) -> str:
        record = self._generate_single_clip(prompt, index, cancel_check=cancel_check)
        return record["file_path"]

    def _generate_single_clip(
        self,
        prompt: str,
        index: int,
        *,
        cancel_check: CancelCheck | None = None,
    ) -> dict[str, Any]:
        prior_cancel = self._cancel_check
        if cancel_check is not None:
            self._cancel_check = cancel_check
        try:
            return self._generate_single_clip_inner(prompt, index)
        finally:
            self._cancel_check = prior_cancel

    def _generate_single_clip_inner(self, prompt: str, index: int) -> dict[str, Any]:
        self._check_cancel("before_api_request")

        prompt_text = self.clean_prompt(prompt)
        output_path = self.output_dir / f"runway_clip_{int(time.time())}_{index}.mp4"
        endpoint = f"{self.base_url}/text_to_video"
        payload = {
            "model": self.model,
            "promptText": prompt_text,
            "ratio": self.ratio,
            "duration": self.duration,
        }

        print("\n" + "=" * 60)
        print(f"[Runway] GENERATING CLIP {index}")
        print("=" * 60)
        print(f"[Runway] Base URL: {self.base_url}")
        print(f"[Runway] Model: {self.model}")
        print("[Runway] Sending REST text_to_video request...")

        try:
            response = self._requests.post(
                endpoint,
                headers=self.headers,
                json=payload,
                timeout=120,
            )
        except Exception as exc:
            raise self._wrap_error(exc) from exc

        if response.status_code not in (200, 201):
            raise_from_http(
                f"Runway API Error: {response.status_code} {response.text}",
                http_status=response.status_code,
            )

        try:
            task_data = response.json()
        except ValueError as exc:
            raise RunwayProviderError(
                "Runway API returned invalid JSON response",
                code="PROVIDER_RUNTIME_ERROR",
                details={"invalid_response": True},
                cause=exc,
            ) from exc

        task_id = task_data.get("id")
        if not task_id:
            raise RunwayProviderError(
                f"Runway task id missing: {task_data}",
                code="PROVIDER_RUNTIME_ERROR",
                details={"invalid_response": True, "task_data": task_data},
            )

        print(f"[Runway] Task created: {task_id}")
        self._check_cancel("after_task_creation")

        clip_meta = self.wait_for_task(task_id, output_path, clip_index=index)
        self.last_task_metadata = clip_meta
        return clip_meta

    def wait_for_task(self, task_id: str, output_path: Path, *, clip_index: int | None = None) -> dict[str, Any]:
        task_url = f"{self.base_url}/tasks/{task_id}"
        deadline = time.monotonic() + float(self.max_poll_seconds)
        attempt = 0
        last_status: str | None = None

        while attempt < self.max_attempts and time.monotonic() < deadline:
            attempt += 1
            self._check_cancel("polling")

            try:
                response = self._requests.get(
                    task_url,
                    headers=self.headers,
                    timeout=60,
                )
            except Exception as exc:
                raise self._wrap_error(exc) from exc

            if response.status_code != 200:
                raise_from_http(
                    f"Runway polling failed: {response.status_code} {response.text}",
                    http_status=response.status_code,
                    details={"task_id": task_id, "attempt": attempt},
                )

            try:
                data = response.json()
            except ValueError as exc:
                raise RunwayProviderError(
                    "Runway task poll returned invalid JSON",
                    code="PROVIDER_RUNTIME_ERROR",
                    details={"task_id": task_id, "invalid_response": True},
                    cause=exc,
                ) from exc

            status = str(data.get("status") or "UNKNOWN").upper()
            last_status = status
            elapsed = int(time.monotonic() - (deadline - self.max_poll_seconds))
            print(
                f"[Runway] Status: {status} "
                f"(attempt {attempt}/{self.max_attempts}, elapsed ~{elapsed}s)"
            )

            if status == TASK_STATUS_SUCCEEDED:
                output = data.get("output") or []
                if not output:
                    raise RunwayProviderError(
                        f"No Runway output URL returned: {data}",
                        code="PROVIDER_TASK_FAILED",
                        details={"task_id": task_id, "task_status": status},
                    )
                video_url = output[0]
                self._check_cancel("before_download")
                file_path = self.download_video(video_url, output_path, task_id=task_id)
                self._check_cancel("after_download")
                record = finalize_download_artifact(
                    file_path,
                    mode=MODE_API,
                    provider_id=RUNWAY_API_ROUTER_KEY,
                    capability=CAPABILITY_TEXT_TO_VIDEO,
                    clip_index=clip_index,
                    task_id=task_id,
                    source_url=video_url,
                    metadata={"task_status": status, "poll_attempts": attempt},
                    provider_version=PROVIDER_VERSION,
                )
                return record

            if status in {TASK_STATUS_FAILED, TASK_STATUS_CANCELLED}:
                raise RunwayProviderError(
                    f"Runway task failed: {data}",
                    code="PROVIDER_TASK_FAILED",
                    details={"task_id": task_id, "task_status": status},
                )

            if status not in TASK_STATUS_PENDING | TASK_STATUS_RUNNING | {"UNKNOWN"}:
                raise RunwayProviderError(
                    f"Runway task ended with unexpected status: {status}",
                    code="PROVIDER_TASK_FAILED",
                    details={"task_id": task_id, "task_status": status},
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(self.poll_interval, max(0.0, remaining)))

        raise RunwayProviderError(
            f"Timeout waiting for Runway task {task_id} (last_status={last_status})",
            code="PROVIDER_TIMEOUT",
            details={
                "task_id": task_id,
                "last_status": last_status,
                "attempts": attempt,
                "max_poll_seconds": self.max_poll_seconds,
            },
        )

    def download_video(
        self,
        video_url: str,
        output_path: Path,
        *,
        task_id: str | None = None,
    ) -> str:
        print("[Runway] Downloading video...")
        try:
            response = self._requests.get(
                video_url,
                stream=True,
                allow_redirects=True,
                timeout=300,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "video/mp4,*/*",
                },
            )
        except Exception as exc:
            raise RunwayProviderError(
                f"Failed to download Runway video: {exc}",
                code="DOWNLOAD_FAILED",
                details={"task_id": task_id, "video_url": video_url},
                cause=exc,
            ) from exc

        if response.status_code != 200:
            raise RunwayProviderError(
                f"Failed to download Runway video: {response.status_code} {response.text}",
                code="DOWNLOAD_FAILED",
                http_status=response.status_code,
                details={"task_id": task_id, "video_url": video_url},
            )

        total_bytes = 0
        with open(output_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                self._check_cancel("download_stream")
                if chunk:
                    handle.write(chunk)
                    total_bytes += len(chunk)

        final_size = output_path.stat().st_size
        print(f"[Runway] Saved: {output_path}")
        print(f"[Runway] Downloaded bytes: {total_bytes}")

        if final_size < MIN_ARTIFACT_BYTES:
            raise RunwayProviderError(
                f"Downloaded file too small, probably invalid: {final_size} bytes",
                code="ARTIFACT_TOO_SMALL",
                details={
                    "task_id": task_id,
                    "file_path": str(output_path),
                    "size_bytes": final_size,
                    "min_artifact_bytes": MIN_ARTIFACT_BYTES,
                    "artifact_preserved": True,
                },
            )

        return str(output_path)

    def generate_clips(
        self,
        prompts: list[str],
        *,
        capability: str = "text_to_video",
        cancel_check: CancelCheck | None = None,
    ) -> list[str]:
        capability_key = str(capability or "text_to_video").strip().lower()
        if capability_key == "image_to_video":
            raise RunwayProviderError(
                "image_to_video is not runtime-supported for Runway API",
                code="CAPABILITY_RUNTIME_UNSUPPORTED",
                details={"capability": capability_key, "runtime_supported": False},
            )
        if capability_key not in {"text_to_video", "video", ""}:
            raise RunwayProviderError(
                f"Unsupported capability for Runway API: {capability_key}",
                code="CAPABILITY_RUNTIME_UNSUPPORTED",
                details={"capability": capability_key},
            )

        print("\n[Runway] Runway REST API selected.")
        print(f"[Runway] Provider version: {PROVIDER_VERSION}")
        print(f"[Runway] Active default (unchanged): {self._config.active_video_provider}")

        self._partial_paths = []
        self.clip_results = []
        effective_cancel = cancel_check or self._cancel_check

        downloaded_files: list[str] = []
        try:
            for index, prompt in enumerate(prompts, start=1):
                self._check_cancel("between_clips")
                record = self._generate_single_clip_record(
                    prompt,
                    index,
                    cancel_check=effective_cancel,
                )
                file_path = record["file_path"]
                downloaded_files.append(file_path)
                self._partial_paths.append(file_path)
                self.clip_results.append(record)
        except RunwayCancelledError as exc:
            exc.details.update(
                partial_artifact_bundle(
                    mark_clip_results_partial(self.clip_results),
                    self._partial_paths,
                )
            )
            raise

        print("[Runway] All clips generated.")
        return downloaded_files

    def _generate_single_clip_record(
        self,
        prompt: str,
        index: int,
        *,
        cancel_check: CancelCheck | None = None,
    ) -> dict[str, Any]:
        return self._generate_single_clip(prompt, index, cancel_check=cancel_check)


def retry_generation(operation, retries=3):
    """Intentionally unimplemented — no automatic retry in 11E-b."""
    pass


def timeout_wrapper(operation, timeout_seconds=60):
    return operation()


__all__ = [
    "MIN_ARTIFACT_BYTES",
    "RunwayVideoProvider",
    "retry_generation",
    "timeout_wrapper",
]
