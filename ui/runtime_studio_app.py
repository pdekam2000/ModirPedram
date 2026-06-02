from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from agents.runtime_patch_generator_agent import (
    RuntimePatchGeneratorAgent
)
from core.runtime_command_parser import RuntimeCommandParser
from execution.action_executor_registry import ActionExecutorRegistry
from execution.function_extractor import (
    FunctionExtractor
)
from execution.runtime_state_manager import RuntimeStateManager
from ui.components.runtime_timeline_panel import (
    RuntimeTimelinePanel
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class RuntimeStudioApp:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "ModirAgentOS - AI Runtime Studio V2"
        )

        self.root.geometry("1400x900")
        self.root.minsize(1180, 760)
        self.patch_generator = RuntimePatchGeneratorAgent()
        self.log_queue = queue.Queue()
        self.function_extractor = FunctionExtractor( str(PROJECT_ROOT) )
        self.is_running = False

        self.current_patch_payload = None
        self.current_diff_preview = None
        self.current_recovery_plan = None

        self.state_manager = RuntimeStateManager(
            str(PROJECT_ROOT)
        )

        self.registry = ActionExecutorRegistry(
            str(PROJECT_ROOT)
        )

        self.command_parser = RuntimeCommandParser()

        self.build_ui()

        self.timeline_panel = RuntimeTimelinePanel(
            parent=self.timeline_tab,
            state_manager=self.state_manager,
        )

        self.root.after(
            300,
            self.timeline_panel.show_latest,
        )

        self.root.after(
            150,
            self.process_log_queue
        )

    def build_ui(self):

        title = tk.Label(
            self.root,
            text=(
                "AI RUNTIME STUDIO V2\n"
                "Human-in-the-loop Runtime Editing"
            ),
            font=("Arial", 18, "bold"),
            justify="center"
        )

        title.pack(pady=(10, 6))

        goal_frame = tk.LabelFrame(
            self.root,
            text="Goal / Command"
        )

        goal_frame.pack(
            fill="x",
            padx=12,
            pady=8
        )

        self.goal_box = tk.Text(
            goal_frame,
            height=5,
            wrap="word"
        )

        self.goal_box.pack(
            fill="x",
            padx=8,
            pady=8
        )

        button_frame = tk.Frame(self.root)

        button_frame.pack(pady=8)

        self.execute_button = tk.Button(
            button_frame,
            text="BUILD PATCH PREVIEW",
            width=28,
            height=2,
            command=self.execute_runtime_plan
        )

        self.execute_button.grid(
            row=0,
            column=0,
            padx=6
        )

        self.approve_button = tk.Button(
            button_frame,
            text="APPROVE PATCH",
            width=22,
            height=2,
            state="disabled",
            command=self.approve_patch
        )

        self.approve_button.grid(
            row=0,
            column=1,
            padx=6
        )

        self.reject_button = tk.Button(
            button_frame,
            text="REJECT PATCH",
            width=22,
            height=2,
            state="disabled",
            command=self.reject_patch
        )

        self.reject_button.grid(
            row=0,
            column=2,
            padx=6
        )

        tk.Button(
            button_frame,
            text="CLEAR LOG",
            width=20,
            height=2,
            command=self.clear_log
        ).grid(
            row=1,
            column=0,
            padx=6,
            pady=(6, 0)
        )

        self.view_recovery_button = tk.Button(
            button_frame,
            text="VIEW RECOVERY PLAN",
            width=22,
            height=2,
            command=self.view_recovery_plan
        )

        self.view_recovery_button.grid(
            row=1,
            column=1,
            padx=6,
            pady=(6, 0)
        )

        self.progress = ttk.Progressbar(
            self.root,
            mode="determinate",
            length=860,
            maximum=100
        )

        self.progress["value"] = 0

        self.progress.pack(
            pady=(8, 4)
        )

        self.status_label = tk.Label(
            self.root,
            text="Runtime Status: Ready",
            font=("Arial", 10)
        )

        self.status_label.pack(
            pady=(0, 8)
        )

        self.notebook = ttk.Notebook(self.root)

        self.notebook.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=8
        )

        self.log_tab = tk.Frame(self.notebook)
        self.preview_tab = tk.Frame(self.notebook)
        self.timeline_tab = tk.Frame(self.notebook)
        self.recovery_tab = tk.Frame(self.notebook)

        self.notebook.add(
            self.log_tab,
            text="Runtime Logs"
        )

        self.notebook.add(
            self.preview_tab,
            text="Patch Diff Preview"
        )

        self.notebook.add(
            self.timeline_tab,
            text="Runtime Timeline"
        )

        self.notebook.add(
            self.recovery_tab,
            text="Recovery"
        )

        self.log_box = tk.Text(
            self.log_tab,
            wrap="word"
        )

        self.log_box.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=8
        )

        self.preview_box = tk.Text(
            self.preview_tab,
            wrap="word"
        )

        self.preview_box.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=8
        )

        self.recovery_box = tk.Text(
            self.recovery_tab,
            wrap="word"
        )

        self.recovery_box.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=8
        )

        self.recovery_box.insert(
            tk.END,
            "Recovery plan will appear here when available.\n"
        )

    def view_recovery_plan(self):

        if not self.current_recovery_plan:

            messagebox.showinfo(
                "Recovery Plan",
                (
                    "No recovery plan is available yet.\n"
                    "Recovery details will appear here "
                    "after a verifier failure."
                )
            )

            return

        self.recovery_box.delete(
            "1.0",
            tk.END
        )

        self.recovery_box.insert(
            tk.END,
            "RECOVERY PLAN\n"
            + "=" * 50
            + "\n\n"
            + str(self.current_recovery_plan)
        )

        self.notebook.select(self.recovery_tab)

    def queue_log(self, message):

        self.log_queue.put(
            ("log", message)
        )

    def queue_status(self, status):

        self.log_queue.put(
            ("status", status)
        )

    def queue_progress(self, percent, stage):

        self.log_queue.put(
            ("progress", percent, stage)
        )

    def process_log_queue(self):

        try:

            while True:

                item = self.log_queue.get_nowait()

                if item[0] == "log":

                    self.log_box.insert(
                        tk.END,
                        item[1]
                    )

                    self.log_box.see(tk.END)

                elif item[0] == "status":

                    self.status_label.config(
                        text=item[1]
                    )

                elif item[0] == "progress":

                    self.progress["value"] = item[1]

                    self.status_label.config(
                        text=(
                            f"Runtime Status: "
                            f"{item[2]} - {item[1]}%"
                        )
                    )

                elif item[0] == "done":

                    self.is_running = False

                    self.execute_button.config(
                        state="normal"
                    )

                elif item[0] == "failed":

                    self.is_running = False

                    self.execute_button.config(
                        state="normal"
                    )

                    self.status_label.config(
                        text="Runtime Status: FAILED"
                    )

                elif item[0] == "recovery_ready":

                    self.current_recovery_plan = item[1]

                    self.view_recovery_button.config(
                        state="normal"
                    )

        except queue.Empty:
            pass

        self.root.after(
            150,
            self.process_log_queue
        )

    def clear_log(self):

        self.log_box.delete(
            "1.0",
            tk.END
        )

        self.preview_box.delete(
            "1.0",
            tk.END
        )

        self.recovery_box.delete(
            "1.0",
            tk.END
        )

        self.recovery_box.insert(
            tk.END,
            "Recovery plan will appear here when available.\n"
        )

        self.progress["value"] = 0

        self.status_label.config(
            text="Runtime Status: Ready"
        )

        self.current_recovery_plan = None

    def execute_runtime_plan(self):

        if self.is_running:

            messagebox.showwarning(
                "Runtime Busy",
                "Runtime is already running."
            )

            return

        self.is_running = True

        self.execute_button.config(
            state="disabled"
        )

        self.approve_button.config(
            state="disabled"
        )

        self.reject_button.config(
            state="disabled"
        )

        self.clear_log()

        thread = threading.Thread(
            target=self._runtime_task,
            daemon=True
        )

        thread.start()

    def _runtime_task(self):

        try:

            self.queue_status(
                "Runtime Status: Building preview..."
            )

            self.queue_progress(
                10,
                "Preparing patch"
            )

            goal = self.goal_box.get(
                "1.0",
                tk.END
            ).strip()

            if not goal:

                goal = (
                    "Runtime Studio preview execution"
                )

            self.queue_log(
                "=" * 70 + "\n"
            )

            self.queue_log(
                "PATCH PREVIEW BUILD STARTED\n"
            )

            self.queue_log(
                "=" * 70 + "\n\n"
            )

            self.queue_log(
                f"Goal:\n{goal}\n\n"
            )

            parsed = self.command_parser.parse(goal)

            if not parsed["success"]:

                self.queue_log(
                    "COMMAND PARSE FAILED\n\n"
                )

                for error in parsed["validation"]["errors"]:

                    self.queue_log(
                        f"- {error}\n"
                    )

                self.log_queue.put(
                    ("failed",)
                )

                return

            command_payload = parsed["payload"]

            self.queue_log(
                "PARSED COMMAND:\n"
            )

            self.queue_log(
                str(command_payload) + "\n\n"
            )

            change_request = command_payload.get(
           "change_request",
            ""
              )
            
            extracted = self.function_extractor.extract(
            file_path=
             command_payload["target_file"],

                function_name=
             command_payload["function_name"],

                 class_name=
              command_payload.get("class_name")
               )

            old_source = extracted["source"]

            self.queue_log(
             "EXTRACTED FUNCTION:\n\n"
             )

            self.queue_log(
                  old_source + "\n\n"
                      )
            generator_result = self.patch_generator.run(
             function_name=
            command_payload["function_name"],

           class_name=
             command_payload.get("class_name"),
              old_source=old_source,

              change_request=
               change_request
             )

            if not generator_result.get("success"):

                self.queue_log(
                    "PATCH GENERATION FAILED\n\n"
                )

                self.queue_log(
                    generator_result.get(
                        "message",
                        (
                            "Patch generation failed safely. "
                            "No code was changed."
                        ),
                    )
                    + "\n"
                )

                self.queue_status(
                    "Runtime Status: Patch generation failed"
                )

                self.log_queue.put(
                    ("failed",)
                )

                return

            new_function_source = generator_result[
             "new_function_source"
             ]

            patch_metadata = {
                "patch_strategy": generator_result.get(
                    "patch_strategy"
                ),
                "operations_applied": generator_result.get(
                    "operations_applied",
                    [],
                ),
                "ast_valid_after_each_step": (
                    generator_result.get(
                        "ast_valid_after_each_step",
                        False,
                    )
                ),
            }

            self.queue_log(
                "SEMANTIC PATCH METADATA\n\n"
            )

            self.queue_log(
                str(patch_metadata) + "\n\n"
            )

            payload = {
             "target_file":
              command_payload["target_file"],

               "function_name":
                    command_payload["function_name"],

                    "class_name":
                        command_payload.get("class_name"),

                      "new_function_source":
                    new_function_source,

                 "patch_metadata":
                    patch_metadata,

                 "approval_granted":
                   False,
                  }
            self.current_patch_payload = payload

            result = self.registry.execute(
                action="APPLY_REPLACE_PATCH",
                payload=payload
            )

            self.queue_progress(
                55,
                "Patch preview ready"
            )

            self.queue_log(
                str(result) + "\n\n"
            )

            preview = (
                result["data"]
                ["patch"]
                ["diff_preview"]
            )

            self.current_diff_preview = preview

            self.preview_box.insert(
                tk.END,
                preview
            )

            self.approve_button.config(
                state="normal"
            )

            self.reject_button.config(
                state="normal"
            )

            self.queue_progress(
                100,
                "Waiting approval"
            )

            self.queue_status(
                "Runtime Status: Waiting approval"
            )

            self.log_queue.put(
                ("done",)
            )

        except Exception as error:

            self.queue_log(
                "\nERROR:\n"
            )

            self.queue_log(
                str(error) + "\n"
            )

            self.log_queue.put(
                ("failed",)
            )

    def approve_patch(self):

        if not self.current_patch_payload:

            return

        self.approve_button.config(
            state="disabled"
        )

        self.reject_button.config(
            state="disabled"
        )

        thread = threading.Thread(
            target=self._approve_task,
            daemon=True
        )

        thread.start()

    def _approve_task(self):

        try:

            self.queue_progress(
                10,
                "Applying patch"
            )

            payload = dict(
                self.current_patch_payload
            )

            payload[
                "approval_granted"
            ] = True

            result = self.registry.execute(
                action="APPLY_REPLACE_PATCH",
                payload=payload
            )

            self.queue_log(
                "\nPATCH APPROVED\n\n"
            )

            self.queue_log(
                str(result) + "\n\n"
            )

            self.queue_progress(
                60,
                "Running verifier"
            )

            verifier_result = self.registry.execute(
                action="RUN_VERIFIER",
                payload={}
            )

            self.queue_log(
                "VERIFIER RESULT\n\n"
            )

            self.queue_log(
                str(verifier_result) + "\n\n"
            )

            self.queue_progress(
                100,
                "Runtime completed"
            )

            self.queue_status(
                "Runtime Status: COMPLETE"
            )

        except Exception as error:

            self.queue_log(
                "\nERROR:\n"
            )

            self.queue_log(
                str(error) + "\n"
            )

    def reject_patch(self):

        self.current_patch_payload = None
        self.current_diff_preview = None

        self.approve_button.config(
            state="disabled"
        )

        self.reject_button.config(
            state="disabled"
        )

        self.queue_log(
            "\nPATCH REJECTED BY USER\n\n"
        )

        self.queue_status(
            "Runtime Status: Patch rejected"
        )


def main():

    root = tk.Tk()

    app = RuntimeStudioApp(root)

    root.mainloop()


if __name__ == "__main__":
    main()