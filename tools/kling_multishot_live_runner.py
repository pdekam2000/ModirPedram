#!/usr/bin/env python3

"""

Kling Multishot live runner — approval-gated Generate.



Default: prepare UI + show approval checklist, stop before Generate.

Generate only with --approve-generate --approved-by NAME --confirm-credit-spend

Recover download only with --recover-latest-output --run-id RUN_ID

"""



from __future__ import annotations



import argparse

import json

import sys

from pathlib import Path



ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:

    sys.path.insert(0, str(ROOT))



from content_brain.execution.kling_multishot_live_engine import (  # noqa: E402

    BENCHMARK_SHOT_1,

    BENCHMARK_SHOT_2,

    OUTPUT_ROOT,

    run_kling_multishot_live,

)

from content_brain.execution.kling_product_run import (  # noqa: E402

    recover_kling_product_run,

    resolve_kling_parent_run_id,

)

from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH  # noqa: E402



DEFAULT_CDP_URL = "http://127.0.0.1:9222"





def main() -> int:

    parser = argparse.ArgumentParser(description="Kling Multishot live runner (approval-gated Generate)")

    parser.add_argument("--shot-1-prompt", default=BENCHMARK_SHOT_1)

    parser.add_argument("--shot-2-prompt", default=BENCHMARK_SHOT_2)

    parser.add_argument("--first-frame-path", default="")

    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)

    parser.add_argument("--map-path", default=str(DEFAULT_MAP_PATH))

    parser.add_argument("--max-wait-minutes", type=int, default=20)

    parser.add_argument("--run-id", default="")

    parser.add_argument("--clip-index", type=int, default=1)

    parser.add_argument(

        "--recover-latest-output",

        action="store_true",

        help="Recover/download already-generated output without clicking Generate",

    )

    parser.add_argument(

        "--approve-generate",

        action="store_true",

        help="Explicit operator approval to click Generate (spends credits)",

    )

    parser.add_argument(

        "--approved-by",

        default="",

        help="Operator name — required with --approve-generate",

    )

    parser.add_argument(

        "--confirm-credit-spend",

        action="store_true",

        help="Second explicit confirmation that credits will be spent",

    )

    args = parser.parse_args()



    if args.recover_latest_output:

        if not args.run_id:

            print("ERROR: --recover-latest-output requires --run-id", file=sys.stderr)

            return 2

        result = recover_kling_product_run(

            project_root=ROOT,

            run_id=resolve_kling_parent_run_id(args.run_id),

            clip_index=max(1, int(args.clip_index)),

            cdp_url=args.cdp_url,

        )

        print(json.dumps(result, indent=2, ensure_ascii=False))

        return 0 if result.get("ok") else 1



    result = run_kling_multishot_live(

        shot_1_prompt=args.shot_1_prompt,

        shot_2_prompt=args.shot_2_prompt,

        first_frame_path=args.first_frame_path or None,

        approve_generate=args.approve_generate,

        approved_by=args.approved_by,

        confirm_credit_spend=args.confirm_credit_spend,

        cdp_url=args.cdp_url,

        map_path=Path(args.map_path),

        max_wait_minutes=args.max_wait_minutes,

        run_id=args.run_id or None,

    )



    summary_path = ROOT / "project_brain" / "kling_multishot_live_run_summary.json"

    summary_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")



    run_dir = OUTPUT_ROOT / result.run_id

    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "live_run_summary.json").write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")



    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    if result.status == "awaiting_approval":

        print("\n--- APPROVAL CHECKLIST ---")

        print(json.dumps(result.approval_checklist, indent=2, ensure_ascii=False))

        print("\nTo proceed (spends credits):")

        print(

            "  python tools/kling_multishot_live_runner.py "

            "--approve-generate --approved-by \"YOUR_NAME\" --confirm-credit-spend"

        )

    if result.status == "download_failed":

        print("\n--- DOWNLOAD FAILED — RECOVERY AVAILABLE ---")

        print(

            "  python tools/kling_multishot_live_runner.py "

            f"--recover-latest-output --run-id \"{result.run_id}\" --clip-index 1"

        )

    return 0 if result.ok else 1





if __name__ == "__main__":

    raise SystemExit(main())

