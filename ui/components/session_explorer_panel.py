"""
Session Explorer Panel V1 — inspect content execution sessions on disk.

Integrated into Execution Center (ModirAgent Control Center).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from typing import Any

from content_brain.execution.session_store import ExecutionSessionStore

STATUS_COLORS = {
    "COMPLETED": "#1e7a34",
    "EXECUTING": "#0057b7",
    "SIMULATED": "#0057b7",
    "QUEUED": "#c77700",
    "AWAITING_APPROVAL": "#c77700",
    "BUDGET_BLOCKED": "#b00020",
    "FAILED": "#b00020",
    "CANCELLED": "#666666",
    "PLANNED": "#444444",
}


class SessionExplorerPanel:
    """Browse and inspect execution sessions from storage."""

    LIST_COLUMNS = (
        "session_id",
        "brief_id",
        "status",
        "provider",
        "story_quality_score",
        "approval_state",
        "budget_state",
        "priority_band",
        "execution_confidence",
        "created_at",
    )

    COLUMN_HEADINGS = {
        "session_id": "Session ID",
        "brief_id": "Brief ID",
        "status": "Status",
        "provider": "Provider",
        "story_quality_score": "Story Q",
        "approval_state": "Approval",
        "budget_state": "Budget",
        "priority_band": "Priority",
        "execution_confidence": "Confidence",
        "created_at": "Created",
    }

    COLUMN_WIDTHS = {
        "session_id": 180,
        "brief_id": 120,
        "status": 110,
        "provider": 110,
        "story_quality_score": 70,
        "approval_state": 90,
        "budget_state": 80,
        "priority_band": 80,
        "execution_confidence": 90,
        "created_at": 140,
    }

    def __init__(self, parent, project_root: str | Path | None = None):
        self.parent = parent
        self.root = parent.winfo_toplevel()
        self.project_root = Path(
            project_root or Path(__file__).resolve().parent.parent.parent
        ).resolve()
        self.store = ExecutionSessionStore(self.project_root)

        self.summaries: list[dict[str, Any]] = []
        self.summary_by_session_id: dict[str, dict[str, Any]] = {}
        self.current_session: dict[str, Any] | None = None
        self.current_session_id: str | None = None

        self.frame = tk.Frame(parent)
        self.frame.pack(fill="both", expand=True)

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        controls = tk.Frame(self.frame)
        controls.pack(fill="x", padx=10, pady=(8, 4))

        tk.Button(
            controls,
            text="REFRESH",
            command=self.refresh,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            controls,
            text="OPEN SESSION",
            command=self.open_selected_session,
        ).pack(side="left", padx=(0, 8))

        self.count_label = tk.Label(
            controls,
            text="Sessions: 0",
            anchor="w",
        )
        self.count_label.pack(side="left", fill="x", expand=True)

        self.path_label = tk.Label(
            self.frame,
            text=f"Source: {self.store.sessions_dir}",
            anchor="w",
            font=("Arial", 9),
            fg="#555555",
        )
        self.path_label.pack(fill="x", padx=10, pady=(0, 4))

        list_frame = tk.LabelFrame(
            self.frame,
            text="Execution Sessions",
            padx=8,
            pady=8,
        )
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.tree = ttk.Treeview(
            list_frame,
            columns=self.LIST_COLUMNS,
            show="headings",
            selectmode="browse",
        )

        for column in self.LIST_COLUMNS:
            self.tree.heading(column, text=self.COLUMN_HEADINGS[column])
            self.tree.column(
                column,
                width=self.COLUMN_WIDTHS[column],
                anchor="w",
            )

        y_scroll = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.tree.yview,
        )
        x_scroll = ttk.Scrollbar(
            list_frame,
            orient="horizontal",
            command=self.tree.xview,
        )
        self.tree.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda _event: self.open_selected_session())

        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(
                f"status_{status.lower()}",
                foreground=color,
            )

        action_frame = tk.Frame(self.frame)
        action_frame.pack(fill="x", padx=10, pady=(0, 4))

        actions = [
            ("INSPECT JSON", lambda: self._show_detail_tab("json")),
            ("INSPECT TIMELINE", lambda: self._show_detail_tab("timeline")),
            ("INSPECT SIMULATION", lambda: self._show_detail_tab("simulation")),
            ("INSPECT APPROVAL", lambda: self._show_detail_tab("approval")),
        ]
        for index, (label, command) in enumerate(actions):
            tk.Button(
                action_frame,
                text=label,
                command=command,
            ).grid(row=0, column=index, padx=4)

        detail_frame = tk.LabelFrame(
            self.frame,
            text="Session Detail",
            padx=8,
            pady=8,
        )
        detail_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.detail_notebook = ttk.Notebook(detail_frame)
        self.detail_notebook.pack(fill="both", expand=True)

        self.json_tab = tk.Frame(self.detail_notebook)
        self.timeline_tab = tk.Frame(self.detail_notebook)
        self.simulation_tab = tk.Frame(self.detail_notebook)
        self.approval_tab = tk.Frame(self.detail_notebook)

        self.detail_notebook.add(self.json_tab, text="JSON")
        self.detail_notebook.add(self.timeline_tab, text="Timeline")
        self.detail_notebook.add(self.simulation_tab, text="Simulation")
        self.detail_notebook.add(self.approval_tab, text="Approval")

        self.json_box = self._make_text_widget(self.json_tab)
        self.simulation_box = self._make_text_widget(self.simulation_tab)
        self.approval_box = self._make_text_widget(self.approval_tab)
        self.timeline_box = self._build_timeline_widget(self.timeline_tab)

        self._set_text(self.json_box, "Select a session and click OPEN SESSION.")
        self._set_text(self.simulation_box, "(no simulation report)")
        self._set_text(self.approval_box, "(no approval decision)")
        self._render_timeline([])

    @staticmethod
    def _make_text_widget(parent) -> tk.Text:
        box = tk.Text(parent, wrap="none", font=("Consolas", 10))
        box.pack(fill="both", expand=True)

        y_scroll = ttk.Scrollbar(parent, orient="vertical", command=box.yview)
        x_scroll = ttk.Scrollbar(parent, orient="horizontal", command=box.xview)
        box.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        return box

    def _build_timeline_widget(self, parent) -> tk.Text:
        return self._make_text_widget(parent)

    def refresh(self):
        self.summaries = self.store.list_summaries()
        self.summary_by_session_id = {
            item["session_id"]: item for item in self.summaries
        }

        selected_id = self.current_session_id
        self.tree.delete(*self.tree.get_children())

        for summary in self.summaries:
            score = summary.get("story_quality_score")
            confidence = summary.get("execution_confidence")
            values = (
                summary.get("session_id", ""),
                summary.get("brief_id", ""),
                summary.get("status", ""),
                summary.get("provider", ""),
                self._format_number(score),
                summary.get("approval_state", ""),
                summary.get("budget_state", ""),
                summary.get("priority_band", ""),
                self._format_number(confidence),
                summary.get("created_at", ""),
            )
            status_tag = f"status_{str(summary.get('status', '')).lower()}"
            self.tree.insert(
                "",
                "end",
                iid=summary.get("session_id"),
                values=values,
                tags=(status_tag,),
            )

        self.count_label.config(text=f"Sessions: {len(self.summaries)}")

        if not self.summaries:
            self.current_session = None
            self.current_session_id = None
            self._set_text(
                self.json_box,
                "No execution sessions found.\n\n"
                f"Expected path:\n{self.store.sessions_dir}\n\n"
                "Sessions will appear here after Phase 9F execution runtime "
                "persists them.",
            )
            self._set_text(self.simulation_box, "(no simulation report)")
            self._set_text(self.approval_box, "(no approval decision)")
            self._render_timeline([])
            return

        if selected_id and selected_id in self.summary_by_session_id:
            self.tree.selection_set(selected_id)
            self.tree.focus(selected_id)
            self.open_session(selected_id)
        elif self.summaries:
            first_id = self.summaries[0]["session_id"]
            self.tree.selection_set(first_id)
            self.tree.focus(first_id)

    def _on_tree_select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        self.current_session_id = selection[0]

    def open_selected_session(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(
                "Session Explorer",
                "Select a session from the list first.",
            )
            return
        self.open_session(selection[0])

    def open_session(self, session_id: str):
        try:
            session = self.store.load_session(session_id)
        except FileNotFoundError:
            messagebox.showerror(
                "Session Explorer",
                f"Could not load session: {session_id}",
            )
            return
        except Exception as error:
            messagebox.showerror(
                "Session Explorer",
                f"Failed to load session:\n{error}",
            )
            return

        self.current_session_id = session_id
        self.current_session = session
        self._populate_detail_panes(session)

    def _populate_detail_panes(self, session: dict[str, Any]):
        self._set_text(self.json_box, self.store.format_json(session))

        timeline = self.store.build_timeline_events(session)
        self._render_timeline(timeline)

        simulation = self.store.resolve_simulation_report(session)
        self._set_text(
            self.simulation_box,
            self.store.format_json(simulation),
        )

        approval = self.store.resolve_approval_decision(session)
        self._set_text(
            self.approval_box,
            self.store.format_json(approval),
        )

    def _show_detail_tab(self, tab_key: str):
        if not self.current_session:
            self.open_selected_session()
            if not self.current_session:
                return

        tab_map = {
            "json": self.json_tab,
            "timeline": self.timeline_tab,
            "simulation": self.simulation_tab,
            "approval": self.approval_tab,
        }
        target = tab_map.get(tab_key)
        if target is not None:
            self.detail_notebook.select(target)

    def _render_timeline(self, events: list[dict[str, str]]):
        self.timeline_box.config(state="normal")
        self.timeline_box.delete("1.0", tk.END)

        if not events:
            self.timeline_box.insert(
                tk.END,
                "No timeline events recorded for this session.",
            )
            return

        for event in events:
            line = (
                f"{event.get('timestamp', '—'):<20} "
                f"[{event.get('event_type', 'EVENT')}] "
                f"{event.get('label', '')} "
                f"({event.get('status', '')})\n"
                f"  {event.get('message', '')}\n\n"
            )
            self.timeline_box.insert(tk.END, line)

    @staticmethod
    def _set_text(widget: tk.Text, content: str):
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)
        widget.config(state="disabled")

    @staticmethod
    def _format_number(value: Any) -> str:
        if value is None or value == "":
            return "—"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
