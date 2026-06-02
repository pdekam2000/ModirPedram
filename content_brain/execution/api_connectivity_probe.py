"""
Phase 10J-b — API readiness probes (env, endpoint, connectivity) without provider rewrites.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ApiProbeResult:
    passed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    reject_code: str | None = None
    message: str = ""


def _check(check_id: str, passed: bool, message: str = "") -> dict[str, Any]:
    return {"id": check_id, "passed": passed, "message": message}


def resolve_api_endpoint(api_config: dict[str, Any]) -> tuple[str | None, str]:
    endpoint_env = str(api_config.get("endpoint_env") or "").strip()
    if endpoint_env:
        value = os.getenv(endpoint_env, "").strip()
        if value:
            return value.rstrip("/"), f"{endpoint_env}={value}"
    default_endpoint = str(api_config.get("default_endpoint") or "").strip()
    if default_endpoint:
        return default_endpoint.rstrip("/"), "catalog.default_endpoint"
    return None, "No API endpoint configured"


def probe_api_key(api_config: dict[str, Any]) -> tuple[bool, str, str | None]:
    key_env = str(api_config.get("api_key_env") or "").strip()
    if not key_env:
        return False, "API key env not configured in catalog", None
    value = os.getenv(key_env, "").strip()
    if not value:
        return False, f"Missing environment variable: {key_env}", key_env
    return True, f"API key present ({key_env})", key_env


def probe_api_connectivity(endpoint: str, *, timeout_seconds: float = 5.0) -> tuple[bool, str]:
    try:
        import requests
    except ImportError:
        return False, "requests package is not installed"

    try:
        response = requests.get(
            endpoint,
            timeout=timeout_seconds,
            allow_redirects=True,
            headers={"User-Agent": "ModirAgentOS-Preflight/10j"},
        )
        if response.status_code < 500:
            return True, f"Endpoint reachable ({response.status_code})"
        return False, f"Endpoint returned server error: {response.status_code}"
    except Exception as exc:
        return False, f"API connectivity probe failed: {exc}"


def run_api_probes(
    api_config: dict[str, Any],
    *,
    skip_connectivity: bool = False,
) -> ApiProbeResult:
    checks: list[dict[str, Any]] = []
    status = str(api_config.get("implementation_status") or "").strip().lower()
    if status in {"planned", "stub"}:
        msg = f"API implementation status is {status}"
        checks.append(_check("ROUTER_IMPLEMENTED", False, msg))
        return ApiProbeResult(False, checks, "PROVIDER_NOT_IMPLEMENTED", msg)

    ok, msg, _key_env = probe_api_key(api_config)
    checks.append(_check("API_KEY_PRESENT", ok, msg))
    if not ok:
        return ApiProbeResult(False, checks, "CREDENTIALS_MISSING", msg)

    endpoint, endpoint_source = resolve_api_endpoint(api_config)
    if not endpoint:
        checks.append(_check("API_ENDPOINT_CONFIGURED", False, endpoint_source))
        return ApiProbeResult(False, checks, "API_ENDPOINT_NOT_CONFIGURED", endpoint_source)
    checks.append(_check("API_ENDPOINT_CONFIGURED", True, f"{endpoint_source}: {endpoint}"))

    polling_supported = api_config.get("polling_supported")
    if polling_supported is False:
        checks.append(_check("API_POLLING_SUPPORTED", False, "Catalog marks polling_supported=false"))
        return ApiProbeResult(False, checks, "API_POLLING_NOT_SUPPORTED", "Polling not supported for this provider")
    checks.append(_check("API_POLLING_SUPPORTED", True, "Task polling supported"))

    if not skip_connectivity:
        ok, msg = probe_api_connectivity(endpoint)
        checks.append(_check("API_CONNECTIVITY_PROBE", ok, msg))
        if not ok:
            return ApiProbeResult(False, checks, "API_CONNECTIVITY_FAILED", msg)

    return ApiProbeResult(True, checks)


__all__ = [
    "ApiProbeResult",
    "resolve_api_endpoint",
    "probe_api_key",
    "probe_api_connectivity",
    "run_api_probes",
]
