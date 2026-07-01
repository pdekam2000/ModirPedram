"""Run first-time YouTube OAuth authorization (opens browser)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.upload.youtube_first_authorization import (  # noqa: E402
    discover_oauth_credentials,
    run_first_youtube_authorization,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="First-time YouTube OAuth authorization")
    parser.add_argument("--project-root", default=str(ROOT), help="ModirAgentOS project root")
    parser.add_argument("--port", type=int, default=8080, help="Local OAuth callback port")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser")
    parser.add_argument("--discover-only", action="store_true", help="Only locate OAuth credentials JSON")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    print("PHASE YT-2A — First YouTube OAuth Authorization", flush=True)
    print("=" * 60, flush=True)

    discovery = discover_oauth_credentials(root)
    print(f"Credentials path: {discovery.get('oauth_client_path') or 'NOT FOUND'}")
    print(f"Client ID: {discovery.get('client_id') or '—'}")
    if not discovery.get("ok"):
        print("ERROR: Place Google Desktop OAuth JSON in secrets/client_secret*.json")
        return 1
    if args.discover_only:
        print("Discovery OK.")
        return 0

    print("\nOpening browser for Google login…")
    print("Approve YouTube upload permissions for your channel.\n")
    result = run_first_youtube_authorization(
        root,
        open_browser=not args.no_browser,
        port=args.port,
        enable_upload=True,
    )
    print("=" * 60)
    if result.get("authorized"):
        print(f"AUTHORIZED — Channel: {result.get('channel_name')} ({result.get('channel_id')})")
        print(f"Token refresh verified: {result.get('token_refresh_verified')}")
        print(f"Result written: project_brain/upload/youtube_auth_result.json")
        return 0

    print(f"FAILED — {result.get('error') or 'unknown'}")
    if result.get("details"):
        print(result["details"])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
