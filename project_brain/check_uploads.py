import json
from pathlib import Path

data = json.loads(Path("project_brain/automation/automation_jobs.json").read_text(encoding="utf-8"))
jobs = data.get("jobs", []) if isinstance(data, dict) else data
completed = [j for j in jobs if j.get("status") == "completed"]
print("Completed:", len(completed))
for j in completed:
    upload = j.get("upload_result") or {}
    platforms = upload.get("platforms", {})
    print("Platform:", j.get("platform_targets"))
    for p, r in platforms.items():
        print(" ", p, "| ok:", r.get("ok"), "| uploaded:", r.get("uploaded"), "| reason:", r.get("reason", ""))
    print("---")
