import json
import tkinter as tk
from tkinter import ttk


class RuntimeTimelinePanel:

    """
    Runtime Timeline Panel V1

    Read-only timeline view from runtime session JSON.
    """

    STATUS_COLORS = {
        "SUCCESS": "#1e7a34",
        "FAILED": "#b00020",
        "RECOVERY_PENDING": "#c77700",
        "ROLLBACK": "#0057b7",
        "ROLLBACK_COMPLETE": "#0057b7",
        "COMPLETE": "#1e7a34",
    }

    COLUMNS = (
        "timestamp",
        "event_type",
        "label",
        "status",
        "message",
    )

    def __init__(
        self,
        parent,
        state_manager,
    ):

        self.parent = parent
        self.state_manager = state_manager
        self.selected_session_id = None
        self.session_map = {}
        self.session_options = []

        self.frame = tk.Frame(parent)
        self.frame.pack(
            fill="both",
            expand=True,
        )

        self.build_controls()
        self.build_table()

    def build_controls(self):

        controls = tk.Frame(self.frame)
        controls.pack(
            fill="x",
            padx=8,
            pady=(8, 4),
        )

        tk.Label(
            controls,
            text="Session:",
        ).pack(
            side="left",
            padx=(0, 6),
        )

        self.session_var = tk.StringVar()

        self.session_selector = ttk.Combobox(
            controls,
            textvariable=self.session_var,
            state="readonly",
            width=52,
        )

        self.session_selector.pack(
            side="left",
            padx=(0, 8),
        )

        self.session_selector.bind(
            "<<ComboboxSelected>>",
            self.handle_session_selected,
        )

        tk.Button(
            controls,
            text="REFRESH TIMELINE",
            command=self.refresh,
        ).pack(
            side="left",
            padx=(0, 8),
        )

        self.summary_label = tk.Label(
            controls,
            text="Timeline: Ready",
            anchor="w",
        )

        self.summary_label.pack(
            side="left",
            fill="x",
            expand=True,
        )

    def build_table(self):

        table_frame = tk.Frame(self.frame)
        table_frame.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=(0, 8),
        )

        self.tree = ttk.Treeview(
            table_frame,
            columns=self.COLUMNS,
            show="headings",
        )

        headings = {
            "timestamp": "Timestamp",
            "event_type": "Type",
            "label": "Action / Decision",
            "status": "Status",
            "message": "Message",
        }

        widths = {
            "timestamp": 150,
            "event_type": 90,
            "label": 170,
            "status": 130,
            "message": 420,
        }

        for column in self.COLUMNS:
            self.tree.heading(
                column,
                text=headings[column],
            )
            self.tree.column(
                column,
                width=widths[column],
                anchor="w",
            )

        y_scroll = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview,
        )

        self.tree.configure(
            yscrollcommand=y_scroll.set,
        )

        self.tree.pack(
            side="left",
            fill="both",
            expand=True,
        )

        y_scroll.pack(
            side="right",
            fill="y",
        )

        for status, color in self.STATUS_COLORS.items():
            tag = f"status_{status.lower()}"
            self.tree.tag_configure(
                tag,
                foreground=color,
            )

    def get_status_tag(self, status):

        normalized = str(status or "FAILED").upper()
        return f"status_{normalized.lower()}"

    def list_runtime_sessions(self):

        sessions = []
        state_dir = self.state_manager.state_dir

        for path in sorted(
            state_dir.glob("runtime_*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(
                    path.read_text(encoding="utf-8")
                )
            except Exception:
                continue

            sessions.append({
                "session_id": data.get("session_id"),
                "status": data.get("status"),
                "goal": data.get("goal"),
                "updated_at": data.get("updated_at"),
            })

        return sessions

    def build_timeline_events(self, state):

        events = []

        session_id = state.get("session_id", "")
        created_at = state.get("created_at", "")
        updated_at = state.get("updated_at", "")
        status = state.get("status", "")

        events.append({
            "timestamp": created_at,
            "event_type": "SESSION",
            "label": "SESSION_CREATED",
            "status": "SUCCESS",
            "message": (
                f"Session {session_id} created. "
                f"Goal: {state.get('goal', '')}"
            ),
        })

        for entry in state.get("execution_log", []):
            action = entry.get("action", "ACTION")
            event_type = (
                "VERIFIER"
                if action == "RUN_VERIFIER"
                else "ACTION"
            )

            events.append({
                "timestamp": entry.get("timestamp", ""),
                "event_type": event_type,
                "label": action,
                "status": entry.get("status", ""),
                "message": entry.get("message", ""),
            })

        for entry in state.get("recovery_history", []):
            events.append({
                "timestamp": entry.get("timestamp", ""),
                "event_type": "RECOVERY",
                "label": entry.get("decision", "RECOVERY"),
                "status": entry.get("decision", ""),
                "message": entry.get("reason", ""),
            })

        for entry in state.get("rollback_history", []):
            result = entry.get("result", {})
            result_status = (
                "SUCCESS"
                if result.get("success")
                else "FAILED"
            )

            events.append({
                "timestamp": entry.get("timestamp", ""),
                "event_type": "ROLLBACK",
                "label": entry.get(
                    "rollback_action",
                    "ROLLBACK",
                ),
                "status": result_status,
                "message": result.get("message", ""),
            })

        if updated_at:
            events.append({
                "timestamp": updated_at,
                "event_type": "SESSION",
                "label": "SESSION_STATUS",
                "status": status,
                "message": f"Session status: {status}",
            })

        events.sort(
            key=lambda item: item.get("timestamp", "")
        )

        return events

    def load_session_options(self):

        sessions = self.list_runtime_sessions()
        options = []
        self.session_map = {}

        for session in sessions:
            label = (
                f"{session.get('session_id')} | "
                f"{session.get('status')} | "
                f"{session.get('updated_at')}"
            )
            options.append(label)
            self.session_map[label] = session.get(
                "session_id"
            )

        self.session_options = options
        self.session_selector["values"] = options

        return sessions

    def clear_table(self):

        for item in self.tree.get_children():
            self.tree.delete(item)

    def render_timeline(self, timeline, session_status=""):

        self.clear_table()

        for event in timeline:
            status = event.get("status", "")

            self.tree.insert(
                "",
                "end",
                values=(
                    event.get("timestamp", ""),
                    event.get("event_type", ""),
                    event.get("label", ""),
                    status,
                    event.get("message", ""),
                ),
                tags=(self.get_status_tag(status),),
            )

        self.summary_label.config(
            text=(
                f"Timeline: {len(timeline)} events"
                + (
                    f" | Session status: {session_status}"
                    if session_status
                    else ""
                )
            )
        )

    def render_selected_session(self):

        if not self.selected_session_id:
            self.clear_table()
            self.summary_label.config(
                text="Timeline: No session selected",
            )
            return

        state = self.state_manager.load_state(
            self.selected_session_id
        )

        timeline = self.build_timeline_events(state)

        self.render_timeline(
            timeline=timeline,
            session_status=state.get("status", ""),
        )

    def handle_session_selected(self, _event=None):

        selected_label = self.session_var.get()
        self.selected_session_id = self.session_map.get(
            selected_label
        )
        self.render_selected_session()

    def select_latest_session(self):

        sessions = self.load_session_options()

        if not sessions:
            self.selected_session_id = None
            self.session_var.set("")
            self.clear_table()
            self.summary_label.config(
                text="Timeline: No sessions found",
            )
            return None

        latest_label = self.session_options[0]
        self.session_var.set(latest_label)
        self.selected_session_id = sessions[0].get(
            "session_id"
        )

        return self.selected_session_id

    def refresh(self, session_id=None):

        self.load_session_options()

        if session_id:
            for label, mapped_id in self.session_map.items():
                if mapped_id == session_id:
                    self.session_var.set(label)
                    self.selected_session_id = session_id
                    break
        elif not self.selected_session_id:
            self.select_latest_session()
        elif self.session_var.get() not in self.session_map:
            self.select_latest_session()

        self.render_selected_session()

    def show_latest(self):

        self.refresh()
