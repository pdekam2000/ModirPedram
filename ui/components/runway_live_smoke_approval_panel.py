"""
Phase RUNWAY-STARTER-TO-VIDEO-H.5 — Tkinter approval panel for Runtime Studio.

View + approval surface only; uses RunwayLiveSmokeApprovalRuntime bridge.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from content_brain.execution.runway_live_smoke_approval_runtime import (
    GATE_APPROVAL,
    GATE_MANUAL_HOLD,
    RunwayLiveSmokeApprovalRuntime,
)


class RunwayLiveSmokeApprovalPanel:
    """Runtime Studio panel: current gate, history, logs, Approve / Image Ready / Cancel."""

    def __init__(
        self,
        parent: tk.Misc,
        runtime: RunwayLiveSmokeApprovalRuntime,
        *,
        poll_ms: int = 400,
    ) -> None:
        self.runtime = runtime
        self.poll_ms = poll_ms
        self._root = parent.winfo_toplevel()

        self.frame = tk.LabelFrame(parent, text="Runway Live Smoke — Operator Approval")
        self.frame.pack(fill="both", expand=True, padx=8, pady=8)

        self.status_var = tk.StringVar(value="idle")
        self.step_var = tk.StringVar(value="—")
        self.control_var = tk.StringVar(value="—")
        self.label_var = tk.StringVar(value="—")
        self.gate_var = tk.StringVar(value="No approval gate active")

        info = tk.Frame(self.frame)
        info.pack(fill="x", padx=8, pady=8)

        tk.Label(info, text="Status:").grid(row=0, column=0, sticky="w")
        tk.Label(info, textvariable=self.status_var, font=("Consolas", 10)).grid(row=0, column=1, sticky="w")
        tk.Label(info, text="Step:").grid(row=1, column=0, sticky="w")
        tk.Label(info, textvariable=self.step_var, font=("Consolas", 9)).grid(row=1, column=1, sticky="w")
        tk.Label(info, text="Control:").grid(row=2, column=0, sticky="w")
        tk.Label(info, textvariable=self.control_var, font=("Consolas", 9)).grid(row=2, column=1, sticky="w")
        tk.Label(info, text="Label:").grid(row=3, column=0, sticky="w")
        tk.Label(info, textvariable=self.label_var, font=("Consolas", 9)).grid(row=3, column=1, sticky="w")
        tk.Label(info, textvariable=self.gate_var, font=("Arial", 11, "bold")).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

        buttons = tk.Frame(self.frame)
        buttons.pack(fill="x", padx=8, pady=(0, 8))

        self.approve_button = tk.Button(buttons, text="Approve", width=14, command=self._on_approve)
        self.approve_button.pack(side="left", padx=4)
        self.image_ready_button = tk.Button(buttons, text="Image Ready", width=14, command=self._on_image_ready)
        self.image_ready_button.pack(side="left", padx=4)
        self.cancel_button = tk.Button(buttons, text="Cancel Run", width=14, command=self._on_cancel)
        self.cancel_button.pack(side="left", padx=4)

        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        history_tab = tk.Frame(notebook)
        logs_tab = tk.Frame(notebook)
        notebook.add(history_tab, text="Approval History")
        notebook.add(logs_tab, text="Runtime Logs")

        self.history_box = tk.Text(history_tab, wrap="word", height=12)
        self.history_box.pack(fill="both", expand=True, padx=6, pady=6)
        self.log_box = tk.Text(logs_tab, wrap="word", height=12)
        self.log_box.pack(fill="both", expand=True, padx=6, pady=6)

        self.runtime.mark_ui_connected(True)
        self._schedule_poll()

    def _schedule_poll(self) -> None:
        self.refresh()
        self._root.after(self.poll_ms, self._schedule_poll)

    def refresh(self) -> None:
        snap = self.runtime.snapshot()
        self.status_var.set(snap.run_status)
        self.step_var.set(snap.current_step_id or "—")
        self.control_var.set(snap.current_control_key or "—")
        self.label_var.set(snap.current_label or snap.current_action or "—")

        if snap.waiting and snap.gate_type == GATE_APPROVAL:
            self.gate_var.set(f"Waiting: {snap.current_control_key or 'approval'}")
        elif snap.waiting and snap.gate_type == GATE_MANUAL_HOLD:
            self.gate_var.set("Waiting: image ready")
        else:
            self.gate_var.set("No approval gate active")

        self.approve_button.config(state="normal" if snap.waiting and snap.gate_type == GATE_APPROVAL else "disabled")
        self.image_ready_button.config(
            state="normal" if snap.waiting and snap.gate_type == GATE_MANUAL_HOLD else "disabled"
        )
        self.cancel_button.config(state="normal" if snap.waiting or snap.run_status == "running" else "disabled")

        self._render_list(self.history_box, self._format_history(snap.approval_history))
        self._render_list(self.log_box, snap.runtime_logs)

    @staticmethod
    def _format_history(items: list[dict]) -> list[str]:
        lines: list[str] = []
        for item in items:
            lines.append(
                f"{item.get('timestamp', '')} · {item.get('event', '')} · "
                f"{item.get('control_key') or item.get('label') or ''}"
            )
        return lines

    @staticmethod
    def _render_list(box: tk.Text, lines: list[str]) -> None:
        content = "\n".join(lines) if lines else "(empty)"
        if box.get("1.0", "end-1c") == content:
            return
        box.delete("1.0", tk.END)
        box.insert(tk.END, content)
        box.see(tk.END)

    def _on_approve(self) -> None:
        self.runtime.submit_approve()

    def _on_image_ready(self) -> None:
        self.runtime.submit_image_ready()

    def _on_cancel(self) -> None:
        self.runtime.submit_cancel()


def attach_runway_live_smoke_approval_panel(
    parent: tk.Misc,
    runtime: RunwayLiveSmokeApprovalRuntime,
) -> RunwayLiveSmokeApprovalPanel:
    return RunwayLiveSmokeApprovalPanel(parent, runtime)
