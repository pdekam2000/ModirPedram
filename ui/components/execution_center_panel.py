"""
Execution Center Panel V1 — content execution runtime hub in ModirAgent Control Center.

V1 hosts Session Explorer for inspecting persisted execution sessions.
Future: simulation controls, approval gate, budget governance.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk

from ui.components.session_explorer_panel import SessionExplorerPanel


class ExecutionCenterPanel:
    """Execution Center tab shell with Session Explorer embedded."""

    def __init__(self, parent, project_root: str | Path | None = None):
        self.parent = parent
        self.project_root = Path(
            project_root or Path(__file__).resolve().parent.parent.parent
        ).resolve()

        self.frame = tk.Frame(parent)
        self.frame.pack(fill="both", expand=True)

        header = tk.Label(
            self.frame,
            text="EXECUTION CENTER",
            font=("Arial", 14, "bold"),
        )
        header.pack(pady=(8, 2))

        subtitle = tk.Label(
            self.frame,
            text=(
                "Inspect content execution sessions — simulation, approval, "
                "budget, and queue state (read-only V1)."
            ),
            font=("Arial", 10),
        )
        subtitle.pack(pady=(0, 8))

        self.session_explorer = SessionExplorerPanel(
            self.frame,
            project_root=self.project_root,
        )
