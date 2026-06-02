"""
Content Brain Panel V1

Self-contained UI component for testing and monitoring the Content Brain
pipeline via ContentBriefOrchestrator only.

No video generation, upload, or browser automation.
"""

from __future__ import annotations

import json
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from content_brain.orchestrators.content_brief_orchestrator import (
    ContentBriefOrchestrator,
    ContentBriefOrchestratorError,
    ContentBriefRunRequest,
)
from content_brain.schemas.content_brief import Platform

try:
    from content_brain.profiles.channel_identity_store import (
        ChannelIdentity,
        ChannelIdentityStore,
    )
except ImportError:
    ChannelIdentity = None  # type: ignore[assignment,misc]
    ChannelIdentityStore = None  # type: ignore[assignment,misc]

PLATFORM_OPTIONS = (
    Platform.TIKTOK.value,
    Platform.YOUTUBE_SHORTS.value,
    Platform.INSTAGRAM_REELS.value,
)

PROVIDER_OPTIONS = ("hailuo", "runway")

DECISION_COLORS = {
    "proceed": "#1e7a34",
    "revise": "#c77700",
    "regenerate": "#b00020",
    "reject": "#b00020",
}


class ContentBrainPanel:
    """
    Content Brain Panel V1

    Runs ContentBriefOrchestrator in a background thread and updates the UI
    through a thread-safe queue (mirrors ui/app.py dashboard log pattern).
    """

    def __init__(self, parent, project_root: str | Path | None = None):
        self.parent = parent
        self.root = parent.winfo_toplevel()
        self.project_root = Path(project_root or self._default_project_root()).resolve()

        self.ui_queue: queue.Queue = queue.Queue()
        self.is_running = False
        self.last_result_payload: dict | None = None
        self.active_channel = None
        self.channel_map: dict[str, str] = {}
        self.channel_store = (
            ChannelIdentityStore(self.project_root)
            if ChannelIdentityStore is not None
            else None
        )

        self.frame = tk.Frame(parent)
        self.frame.pack(fill="both", expand=True)

        self._build_ui()
        self.root.after(150, self._process_ui_queue)
        self.root.after(0, self._load_active_channel_on_startup)

    @staticmethod
    def _default_project_root() -> Path:
        return Path(__file__).resolve().parent.parent.parent

    def _build_ui(self):
        header = tk.Label(
            self.frame,
            text="CONTENT BRAIN — BRIEF ORCHESTRATOR",
            font=("Arial", 14, "bold"),
        )
        header.pack(pady=(8, 4))

        subtitle = tk.Label(
            self.frame,
            text=(
                "Safe pipeline test via ContentBriefOrchestrator "
                "(no video, upload, or browser automation)"
            ),
            font=("Arial", 10),
        )
        subtitle.pack(pady=(0, 8))

        self._build_channel_controls()
        self._build_inputs()
        self._build_actions()
        self._build_status()
        self._build_summary()
        self._build_json_panel()

    def _build_channel_controls(self):
        channel_frame = tk.LabelFrame(
            self.frame,
            text="Channel Identity",
            padx=10,
            pady=8,
        )
        channel_frame.pack(fill="x", padx=10, pady=(0, 8))

        row = tk.Frame(channel_frame)
        row.pack(fill="x", pady=4)

        tk.Label(row, text="Channel:", width=12, anchor="w").pack(side="left")

        self.channel_var = tk.StringVar(value="(Manual — no saved channel)")
        self.channel_selector = ttk.Combobox(
            row,
            textvariable=self.channel_var,
            state="readonly",
            width=52,
        )
        self.channel_selector.pack(side="left", padx=(0, 8))
        self.channel_selector.bind("<<ComboboxSelected>>", self._on_channel_selected)

        tk.Button(
            row,
            text="REFRESH LIST",
            command=self._refresh_channel_list,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            row,
            text="LOAD ACTIVE",
            command=lambda: self._load_active_channel(silent=False),
        ).pack(side="left")

        self.channel_status = tk.Label(
            channel_frame,
            text="Active channel: manual inputs",
            anchor="w",
            font=("Arial", 10),
        )
        self.channel_status.pack(fill="x", pady=(4, 0))

        self._refresh_channel_list()

    def _build_inputs(self):
        inputs = tk.LabelFrame(
            self.frame,
            text="Run Inputs",
            padx=10,
            pady=8,
        )
        inputs.pack(fill="x", padx=10, pady=(0, 8))

        row1 = tk.Frame(inputs)
        row1.pack(fill="x", pady=4)

        tk.Label(row1, text="Topic:", width=12, anchor="w").pack(side="left")
        self.topic_var = tk.StringVar(value="")
        tk.Entry(
            row1,
            textvariable=self.topic_var,
            width=72,
        ).pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 8),
        )
        tk.Label(
            row1,
            text="(empty = auto topic in niche)",
            font=("Arial", 9),
            fg="#555555",
        ).pack(side="left")

        row2 = tk.Frame(inputs)
        row2.pack(fill="x", pady=4)

        tk.Label(row2, text="Niche:", width=12, anchor="w").pack(side="left")
        self.niche_var = tk.StringVar(value="general")
        tk.Entry(
            row2,
            textvariable=self.niche_var,
            width=48,
        ).pack(side="left", padx=(0, 16))

        tk.Label(row2, text="Platform:", width=10, anchor="w").pack(side="left")
        self.platform_var = tk.StringVar(value=Platform.TIKTOK.value)
        self.platform_selector = ttk.Combobox(
            row2,
            textvariable=self.platform_var,
            values=PLATFORM_OPTIONS,
            state="readonly",
            width=18,
        )
        self.platform_selector.pack(side="left", padx=(0, 16))

        tk.Label(row2, text="Duration (s):", width=12, anchor="w").pack(side="left")
        self.duration_var = tk.StringVar(value="30")
        tk.Entry(row2, textvariable=self.duration_var, width=8).pack(side="left")

        row3 = tk.Frame(inputs)
        row3.pack(fill="x", pady=4)

        tk.Label(row3, text="Provider:", width=12, anchor="w").pack(side="left")
        self.provider_var = tk.StringVar(value="hailuo")
        self.provider_selector = ttk.Combobox(
            row3,
            textvariable=self.provider_var,
            values=PROVIDER_OPTIONS,
            state="readonly",
            width=22,
        )
        self.provider_selector.pack(side="left")

    def _build_actions(self):
        actions = tk.Frame(self.frame)
        actions.pack(fill="x", padx=10, pady=(0, 8))

        self.run_button = tk.Button(
            actions,
            text="RUN CONTENT BRAIN",
            width=22,
            height=2,
            command=self.run_content_brain,
        )
        self.run_button.pack(side="left", padx=(0, 8))

        tk.Button(
            actions,
            text="CLEAR OUTPUT",
            width=16,
            height=2,
            command=self.clear_output,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            actions,
            text="COPY JSON",
            width=14,
            height=2,
            command=self.copy_json,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            actions,
            text="SAVE JSON",
            width=14,
            height=2,
            command=self.save_json,
        ).pack(side="left")

    def _build_status(self):
        status_frame = tk.Frame(self.frame)
        status_frame.pack(fill="x", padx=10, pady=(0, 8))

        self.progress = ttk.Progressbar(
            status_frame,
            mode="determinate",
            length=780,
            maximum=100,
        )
        self.progress["value"] = 0
        self.progress.pack(fill="x", pady=(0, 6))

        self.status_label = tk.Label(
            status_frame,
            text="Status: Ready",
            font=("Arial", 10),
            anchor="w",
        )
        self.status_label.pack(fill="x")

    def _build_summary(self):
        summary = tk.LabelFrame(
            self.frame,
            text="Brief Summary",
            padx=10,
            pady=8,
        )
        summary.pack(fill="x", padx=10, pady=(0, 8))

        self.summary_fields: dict[str, tk.Label] = {}
        field_defs = (
            ("run_mode", "Run Mode"),
            ("channel", "Channel"),
            ("viral_score", "Viral Score"),
            ("decision", "Decision"),
            ("recommended_title", "Recommended Title"),
            ("thumbnail_concept", "Thumbnail Concept"),
            ("next_action", "Next Action"),
            ("warnings", "Warnings"),
        )

        for key, label in field_defs:
            row = tk.Frame(summary)
            row.pack(fill="x", pady=2)

            tk.Label(
                row,
                text=f"{label}:",
                width=18,
                anchor="w",
                font=("Arial", 10, "bold"),
            ).pack(side="left")

            value_label = tk.Label(
                row,
                text="—",
                anchor="w",
                justify="left",
                wraplength=920,
            )
            value_label.pack(side="left", fill="x", expand=True)
            self.summary_fields[key] = value_label

    def _build_json_panel(self):
        panel = tk.LabelFrame(
            self.frame,
            text="JSON Preview / Log",
            padx=10,
            pady=8,
        )
        panel.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        text_frame = tk.Frame(panel)
        text_frame.pack(fill="both", expand=True)

        self.log_box = tk.Text(
            text_frame,
            width=120,
            height=18,
            wrap="none",
            font=("Consolas", 10),
        )
        y_scroll = ttk.Scrollbar(
            text_frame,
            orient="vertical",
            command=self.log_box.yview,
        )
        x_scroll = ttk.Scrollbar(
            text_frame,
            orient="horizontal",
            command=self.log_box.xview,
        )

        self.log_box.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )

        self.log_box.pack(side="left", fill="both", expand=True)
        y_scroll.pack(side="right", fill="y")
        x_scroll.pack(side="bottom", fill="x")

        self._queue_log("Content Brain Panel ready.")

    def _refresh_channel_list(self):
        options = ["(Manual — no saved channel)"]
        self.channel_map = {"(Manual — no saved channel)": ""}

        if self.channel_store is None:
            self.channel_selector["values"] = options
            self.channel_status.config(
                text="Active channel: unavailable (channel store not loaded)"
            )
            return

        for item in self.channel_store.list_channels():
            label = str(item.get("display_label") or item.get("channel_name") or "")
            channel_id = str(item.get("channel_id", "")).strip()
            if not label or not channel_id:
                continue
            options.append(label)
            self.channel_map[label] = channel_id

        self.channel_selector["values"] = options

    def _load_active_channel_on_startup(self):
        if self.channel_store is None:
            return
        self._refresh_channel_list()
        self._load_active_channel(silent=True)

    def _load_active_channel(self, silent: bool = False):
        if self.channel_store is None:
            if not silent:
                messagebox.showinfo(
                    "Channel Identity",
                    "Channel identity store is unavailable.",
                )
            return

        channel = self.channel_store.load_active()
        if channel is None:
            self.active_channel = None
            self.channel_status.config(text="Active channel: none")
            self.channel_var.set("(Manual — no saved channel)")
            if not silent:
                messagebox.showinfo(
                    "Channel Identity",
                    "No active channel is saved yet.",
                )
            return

        self._apply_channel_identity(channel)
        self._select_channel_in_list(channel.channel_id)

        if not silent:
            self._queue_log(f"[OK] Loaded active channel: {channel.display_label}")

    def _on_channel_selected(self, _event=None):
        if self.channel_store is None:
            return

        label = self.channel_var.get().strip()
        channel_id = self.channel_map.get(label, "")

        if not channel_id:
            self.active_channel = None
            self.channel_status.config(text="Active channel: manual inputs")
            return

        try:
            channel = self.channel_store.load(channel_id)
        except Exception as exc:
            messagebox.showerror("Channel Identity", f"Could not load channel: {exc}")
            return

        self._apply_channel_identity(channel)

    def _apply_channel_identity(self, channel) -> None:
        self.active_channel = channel
        self.niche_var.set(channel.main_niche.strip() or "general")
        self.platform_var.set(channel.platform)
        self.duration_var.set(str(channel.default_duration_seconds))
        self.provider_var.set(channel.default_provider.strip() or "hailuo")
        self.channel_status.config(
            text=f"Active channel: {channel.display_label} ({channel.channel_id})"
        )

    def _select_channel_in_list(self, channel_id: str) -> None:
        for label, mapped_id in self.channel_map.items():
            if mapped_id == channel_id:
                self.channel_var.set(label)
                return

        self.channel_var.set("(Manual — no saved channel)")

    def _resolve_run_inputs(self) -> dict[str, str | int]:
        topic = self.topic_var.get().strip()
        niche = self.niche_var.get().strip() or "general"
        platform = self.platform_var.get().strip() or Platform.TIKTOK.value
        provider = self.provider_var.get().strip() or "hailuo"
        duration = self._parse_duration()

        return {
            "topic": topic,
            "niche": niche,
            "platform": platform,
            "provider": provider,
            "duration": duration,
        }

    def _queue_log(self, message: str):
        self.ui_queue.put(("log", message))

    def _queue_status(self, message: str):
        self.ui_queue.put(("status", message))

    def _queue_progress(self, value: int):
        self.ui_queue.put(("progress", value))

    def _queue_result(self, payload: dict):
        self.ui_queue.put(("result", payload))

    def _queue_error(self, message: str):
        self.ui_queue.put(("error", message))

    def _queue_done(self):
        self.ui_queue.put(("done", None))

    def _process_ui_queue(self):
        try:
            while True:
                item = self.ui_queue.get_nowait()
                event_type = item[0]

                if event_type == "log":
                    self.log_box.insert(tk.END, item[1] + "\n")
                    self.log_box.see(tk.END)

                elif event_type == "status":
                    self.status_label.config(text=item[1])

                elif event_type == "progress":
                    self.progress["value"] = item[1]

                elif event_type == "result":
                    self._render_result(item[1])

                elif event_type == "error":
                    self._queue_log(f"[ERROR] {item[1]}")
                    self.status_label.config(text="Status: Failed")
                    messagebox.showerror("Content Brain Error", item[1])

                elif event_type == "done":
                    self.is_running = False
                    self.run_button.config(state="normal")

        except queue.Empty:
            pass

        self.root.after(150, self._process_ui_queue)

    def _render_result(self, payload: dict):
        self.last_result_payload = payload

        scorecard = payload.get("viral_scorecard", {})
        decision_pkg = payload.get("decision_package", {})
        title_pkg = payload.get("title_thumbnail_package", {})
        run_context = payload.get("run_context", {})

        channel_identity_applied = bool(run_context.get("channel_identity_applied"))
        run_mode_text = "active channel" if channel_identity_applied else "manual"
        channel_name = str(run_context.get("channel_name", "")).strip()
        channel_id = str(run_context.get("channel_id", "")).strip()
        if channel_identity_applied and (channel_name or channel_id):
            channel_text = channel_name or channel_id
            if channel_name and channel_id:
                channel_text = f"{channel_name} ({channel_id})"
        else:
            channel_text = "—"

        composite = scorecard.get("composite_score", "—")
        tier = scorecard.get("production_tier", "")
        viral_text = f"{composite}"
        if tier:
            viral_text = f"{composite} (tier {tier})"

        decision = str(
            decision_pkg.get("decision", run_context.get("decision", "—"))
        )
        title = title_pkg.get("recommended_title") or "—"
        thumbnail = self._format_thumbnail_concept(
            title_pkg.get("recommended_thumbnail_concept", {})
        )
        next_action = payload.get("next_action", "—")

        warnings = list(title_pkg.get("warnings", []))
        decision_reasons = decision_pkg.get("reasons", [])
        if decision_reasons:
            warnings = [f"Decision: {reason}" for reason in decision_reasons] + warnings
        warnings_text = "; ".join(warnings) if warnings else "none"

        self.summary_fields["run_mode"].config(text=run_mode_text)
        self.summary_fields["channel"].config(text=channel_text)
        self.summary_fields["viral_score"].config(text=str(viral_text))
        self.summary_fields["decision"].config(
            text=decision,
            fg=DECISION_COLORS.get(decision.lower(), "#000000"),
        )
        self.summary_fields["recommended_title"].config(text=title)
        self.summary_fields["thumbnail_concept"].config(text=thumbnail)
        self.summary_fields["next_action"].config(text=next_action)
        self.summary_fields["warnings"].config(text=warnings_text)

        pretty_json = json.dumps(payload, indent=2, ensure_ascii=False)
        self.log_box.delete("1.0", tk.END)
        self.log_box.insert(tk.END, pretty_json)
        self.log_box.see(tk.INSERT)

    @staticmethod
    def _format_thumbnail_concept(concept: dict) -> str:
        if not concept:
            return "—"

        concept_id = concept.get("concept_id", "unknown")
        focal = concept.get("focal_subject", "")
        visual = concept.get("visual_prompt", "")

        if focal:
            return f"{concept_id} — {focal}"
        if visual:
            snippet = visual[:120] + ("..." if len(visual) > 120 else "")
            return f"{concept_id} — {snippet}"
        return concept_id

    def _parse_duration(self) -> int | None:
        raw = self.duration_var.get().strip()
        if not raw:
            return 30

        try:
            duration = int(raw)
        except ValueError:
            raise ValueError("Duration must be a positive integer.")

        if duration <= 0:
            raise ValueError("Duration must be greater than zero.")

        return duration

    def run_content_brain(self):
        if self.is_running:
            messagebox.showwarning(
                "Busy",
                "Content Brain is already running.",
            )
            return

        try:
            run_inputs = self._resolve_run_inputs()
        except ValueError as exc:
            messagebox.showerror("Invalid Input", str(exc))
            return

        topic = str(run_inputs["topic"])
        niche = str(run_inputs["niche"])
        platform = str(run_inputs["platform"])
        provider = str(run_inputs["provider"])
        duration = int(run_inputs["duration"])
        user_topic_explicit = bool(topic)

        self.is_running = True
        self.run_button.config(state="disabled")
        self._queue_progress(5)
        self._queue_status("Status: Running Content Brain pipeline...")
        active_channel_id = (
            self.active_channel.channel_id
            if self.active_channel is not None
            else None
        )
        run_mode = "active channel" if active_channel_id else "manual"

        self._queue_log("")
        self._queue_log("=" * 72)
        self._queue_log(f"RUN MODE: {run_mode}")
        if self.active_channel is not None:
            self._queue_log(
                f"CHANNEL: {self.active_channel.display_label} "
                f"({self.active_channel.channel_id})"
            )
        self._queue_log(
            f"RUN | niche={niche} | platform={platform} | "
            f"duration={duration}s | provider={provider}"
        )
        self._queue_log(
            f"TOPIC: {topic or '(auto — trend discovery inside niche)'}"
        )
        if user_topic_explicit:
            self._queue_log("TOPIC MODE: user authoritative")
        else:
            self._queue_log("TOPIC MODE: auto-select inside niche")
        self._queue_log("=" * 72)

        thread = threading.Thread(
            target=self._run_orchestrator_worker,
            args=(topic, niche, platform, duration, provider, active_channel_id),
            daemon=True,
        )
        thread.start()

    def _run_orchestrator_worker(
        self,
        topic: str,
        niche: str,
        platform: str,
        duration: int,
        provider: str,
        channel_id: str | None = None,
    ):
        try:
            self._queue_progress(15)

            memory_path = (
                self.project_root
                / "storage"
                / "content_brain"
                / "content_history.json"
            )
            memory_path.parent.mkdir(parents=True, exist_ok=True)

            orchestrator = ContentBriefOrchestrator(
                project_root=self.project_root,
                memory_path=memory_path,
            )

            request_kwargs: dict[str, str | int | None] = {
                "niche": niche,
                "topic": topic,
                "platform": platform,
                "user_duration_seconds": duration,
                "provider_name": provider,
            }
            if channel_id:
                request_kwargs["channel_id"] = channel_id

            request = ContentBriefRunRequest(**request_kwargs)

            self._queue_progress(35)
            if channel_id:
                self._queue_log(
                    f"Orchestrator request: active channel mode (channel_id={channel_id})"
                )
            else:
                self._queue_log("Orchestrator request: manual mode (no channel_id)")
            self._queue_log(
                "Pipeline: profile -> trend -> hook -> format -> story -> "
                "retention -> uniqueness -> score -> decision -> title/thumbnail"
            )

            result = orchestrator.run(request)
            payload = result.to_dict()
            run_context = payload.get("run_context", {})

            self._queue_progress(90)
            completion_log = (
                f"[OK] Brief {result.brief_id} | decision={result.decision_package.decision.value} | "
                f"score={result.viral_scorecard.composite_score:.1f} | "
                f"ready={result.production_ready}"
            )
            if run_context.get("channel_identity_applied"):
                channel_name = run_context.get("channel_name", "")
                channel_ref = run_context.get("channel_id", "")
                completion_log += f" | channel={channel_name or channel_ref}"
            else:
                completion_log += " | mode=manual"
            self._queue_log(completion_log)

            self._queue_result(payload)
            self._queue_status("Status: Complete")
            self._queue_progress(100)

        except ContentBriefOrchestratorError as exc:
            self._queue_error(str(exc))
            self._queue_progress(0)

        except Exception as exc:
            self._queue_error(f"Unexpected error: {exc}")
            self._queue_progress(0)

        finally:
            self._queue_done()

    def clear_output(self):
        self.last_result_payload = None
        self.progress["value"] = 0
        self.status_label.config(text="Status: Ready")

        for label in self.summary_fields.values():
            label.config(text="—", fg="#000000")

        self.log_box.delete("1.0", tk.END)
        self._queue_log("Output cleared.")

    def copy_json(self):
        if not self.last_result_payload:
            messagebox.showinfo(
                "Copy JSON",
                "No result available. Run Content Brain first.",
            )
            return

        payload = json.dumps(
            self.last_result_payload,
            indent=2,
            ensure_ascii=False,
        )
        self.root.clipboard_clear()
        self.root.clipboard_append(payload)
        self._queue_log("[OK] JSON copied to clipboard.")

    def save_json(self):
        if not self.last_result_payload:
            messagebox.showinfo(
                "Save JSON",
                "No result available. Run Content Brain first.",
            )
            return

        default_dir = self.project_root / "outputs" / "content_brain"
        default_dir.mkdir(parents=True, exist_ok=True)

        brief_id = self.last_result_payload.get("brief_id", "content_brief")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"{brief_id}_{timestamp}.json"

        target_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save Content Brain JSON",
            initialdir=str(default_dir),
            initialfile=default_name,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )

        if not target_path:
            return

        try:
            Path(target_path).write_text(
                json.dumps(
                    self.last_result_payload,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self._queue_log(f"[OK] JSON saved: {target_path}")
        except OSError as exc:
            messagebox.showerror("Save Failed", str(exc))


def run_demo():
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    root = tk.Tk()
    root.title("Content Brain Panel — Standalone Demo")
    root.geometry("1280x940")
    root.minsize(1100, 780)

    ContentBrainPanel(root, project_root=project_root)
    root.mainloop()


if __name__ == "__main__":
    run_demo()
