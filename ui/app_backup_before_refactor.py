import os
import sys
import json
import shutil
import zipfile
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

HANDOFF_FILE = PROJECT_ROOT / "project_brain" / "FULL_PROJECT_HANDOFF.md"
PROJECT_BRAIN_DIR = PROJECT_ROOT / "project_brain"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"
BACKUP_DIR = PROJECT_ROOT / "backups"

CONFIG_DIR = PROJECT_ROOT / "config"
PROVIDER_REGISTRY_FILE = CONFIG_DIR / "provider_registry.json"
ACTIVE_PROVIDERS_FILE = CONFIG_DIR / "active_providers.json"
ENV_FILE = PROJECT_ROOT / ".env"


class ModirAgentControlCenter:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "ModirAgent OS - Created by Pedram Kamangar"
        )

        self.root.geometry("1320x920")

        self.is_running = False
        self.provider_vars = {}

        self.build_ui()
        self.load_provider_panel()

    # =========================================================
    # UI
    # =========================================================

    def build_ui(self):

        title = tk.Label(
            self.root,
            text=(
                "MODIRAGENT OS\n"
                "AUTONOMOUS AI CONTENT STUDIO"
            ),
            font=("Arial", 20, "bold"),
            justify="center"
        )

        title.pack(pady=10)

        creator = tk.Label(
            self.root,
            text="Created by Pedram Kamangar",
            font=("Arial", 11)
        )

        creator.pack()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.dashboard_tab = tk.Frame(self.notebook)
        self.providers_tab = tk.Frame(self.notebook)
        self.runstudio_tab = tk.Frame(self.notebook)

        self.notebook.add(self.dashboard_tab, text="Dashboard")
        self.notebook.add(self.providers_tab, text="AI Providers")
        self.notebook.add(self.runstudio_tab, text="Run Studio")

        self.build_dashboard_tab()
        self.build_providers_tab()
        self.build_runstudio_tab()

    # =========================================================
    # DASHBOARD
    # =========================================================

    def build_dashboard_tab(self):

        button_frame = tk.Frame(self.dashboard_tab)
        button_frame.pack(pady=12)

        buttons = [

            ("BUILD FINAL HANDOFF", self.build_final_handoff),
            ("RUN FULL VIDEO PIPELINE", self.run_full_pipeline),
            ("OPEN AI BROWSER", self.open_ai_browser),
            ("SHOW TOPIC MEMORY", self.show_topic_memory),
            ("OPEN PROJECT BRAIN", self.open_project_brain),
            ("OPEN OUTPUTS", self.open_outputs),
            ("OPEN HANDOFF", self.open_handoff),
            ("CLEAN DOWNLOADS", self.clean_downloads),
            ("CLEAN TEST OUTPUTS", self.clean_outputs),
            ("CLEAN TEMP FILES", self.clean_temp_files),
            ("CREATE BACKUP", self.create_backup),
            ("CLEAR LOG", self.clear_log),
        ]

        row = 0
        col = 0

        for text, command in buttons:

            btn = tk.Button(
                button_frame,
                text=text,
                width=28,
                height=2,
                command=command
            )

            btn.grid(
                row=row,
                column=col,
                padx=6,
                pady=6
            )

            col += 1

            if col >= 3:
                col = 0
                row += 1

        self.progress = ttk.Progressbar(
            self.dashboard_tab,
            mode="indeterminate",
            length=760
        )

        self.progress.pack(pady=10)

        self.status_label = tk.Label(
            self.dashboard_tab,
            text="Status: Ready",
            font=("Arial", 10)
        )

        self.status_label.pack()

        self.log_box = tk.Text(
            self.dashboard_tab,
            width=155,
            height=28,
            wrap="word"
        )

        self.log_box.pack(padx=10, pady=10)

        self.log(
            "ModirAgent Control Center Ready."
        )

    # =========================================================
    # PROVIDERS TAB
    # =========================================================

    def build_providers_tab(self):

        header = tk.Label(
            self.providers_tab,
            text="AI PROVIDER CONTROL PANEL",
            font=("Arial", 16, "bold")
        )

        header.pack(pady=8)

        self.provider_frame = tk.Frame(self.providers_tab)
        self.provider_frame.pack(pady=8, fill="x", padx=30)

        action_frame = tk.Frame(self.providers_tab)
        action_frame.pack(pady=8)

        tk.Button(
            action_frame,
            text="SAVE ACTIVE PROVIDERS",
            width=28,
            height=2,
            command=self.save_active_providers
        ).grid(row=0, column=0, padx=6)

        tk.Button(
            action_frame,
            text="REFRESH STATUS",
            width=28,
            height=2,
            command=self.load_provider_panel
        ).grid(row=0, column=1, padx=6)

        tk.Button(
            action_frame,
            text="OPEN CONFIG FOLDER",
            width=28,
            height=2,
            command=self.open_provider_config
        ).grid(row=0, column=2, padx=6)

        self.provider_status_box = tk.Text(
            self.providers_tab,
            width=155,
            height=28,
            wrap="word"
        )

        self.provider_status_box.pack(padx=10, pady=8)

    # =========================================================
    # RUN STUDIO TAB
    # =========================================================

    def build_runstudio_tab(self):

        title = tk.Label(
            self.runstudio_tab,
            text="RUN STUDIO",
            font=("Arial", 18, "bold")
        )

        title.pack(pady=10)

        form_frame = tk.Frame(self.runstudio_tab)
        form_frame.pack(pady=10)

        # Topic

        tk.Label(
            form_frame,
            text="Topic / Niche",
            font=("Arial", 11, "bold")
        ).grid(row=0, column=0, sticky="w", pady=8)

        self.topic_var = tk.StringVar()

        tk.Entry(
            form_frame,
            textvariable=self.topic_var,
            width=70
        ).grid(row=0, column=1, padx=10, pady=8)

        # Platform

        tk.Label(
            form_frame,
            text="Platform",
            font=("Arial", 11, "bold")
        ).grid(row=1, column=0, sticky="w", pady=8)

        self.platform_var = tk.StringVar(value="TikTok")

        ttk.Combobox(
            form_frame,
            textvariable=self.platform_var,
            values=[
                "TikTok",
                "Instagram Reels",
                "YouTube Shorts"
            ],
            state="readonly",
            width=30
        ).grid(row=1, column=1, sticky="w", padx=10)

        # Video Type

        tk.Label(
            form_frame,
            text="Video Type",
            font=("Arial", 11, "bold")
        ).grid(row=2, column=0, sticky="w", pady=8)

        self.video_type_var = tk.StringVar(value="ai_video")

        ttk.Combobox(
            form_frame,
            textvariable=self.video_type_var,
            values=[
                "ai_video",
                "slide_video",
                "voice_only",
                "seo_only"
            ],
            state="readonly",
            width=30
        ).grid(row=2, column=1, sticky="w", padx=10)

        # Run Mode

        tk.Label(
            form_frame,
            text="Run Mode",
            font=("Arial", 11, "bold")
        ).grid(row=3, column=0, sticky="w", pady=8)

        self.run_mode_var = tk.StringVar(value="full_video")

        ttk.Combobox(
            form_frame,
            textvariable=self.run_mode_var,
            values=[
                "full_video",
                "seo_only",
                "voice_only"
            ],
            state="readonly",
            width=30
        ).grid(row=3, column=1, sticky="w", padx=10)

        # Active Providers

        tk.Label(
            form_frame,
            text="Active Providers",
            font=("Arial", 11, "bold")
        ).grid(row=4, column=0, sticky="nw", pady=8)

        self.active_provider_box = tk.Text(
            form_frame,
            width=70,
            height=8
        )

        self.active_provider_box.grid(
            row=4,
            column=1,
            padx=10,
            pady=8
        )

        self.refresh_active_provider_box()

        # Buttons

        button_frame = tk.Frame(self.runstudio_tab)
        button_frame.pack(pady=10)

        tk.Button(
            button_frame,
            text="GENERATE FULL VIDEO",
            width=28,
            height=2,
            command=self.run_studio_pipeline
        ).grid(row=0, column=0, padx=6)

        tk.Button(
            button_frame,
            text="OPEN LATEST OUTPUT",
            width=28,
            height=2,
            command=self.open_outputs
        ).grid(row=0, column=1, padx=6)

        tk.Button(
            button_frame,
            text="REFRESH ACTIVE PROVIDERS",
            width=28,
            height=2,
            command=self.refresh_active_provider_box
        ).grid(row=0, column=2, padx=6)

        # Studio Log

        self.studio_log_box = tk.Text(
            self.runstudio_tab,
            width=155,
            height=22,
            wrap="word"
        )

        self.studio_log_box.pack(padx=10, pady=10)

    # =========================================================
    # RUN STUDIO EXECUTION
    # =========================================================

    def run_studio_pipeline(self):

        def task():

            self.is_running = True
            self.progress.start()

            topic = self.topic_var.get().strip()
            platform = self.platform_var.get().strip()
            video_type = self.video_type_var.get().strip()
            run_mode = self.run_mode_var.get().strip()

            if not topic:

                messagebox.showerror(
                    "Missing Topic",
                    "Please enter a topic."
                )

                self.progress.stop()
                self.is_running = False
                return

            self.studio_log_box.insert(
                tk.END,
                "\n" + "=" * 80 + "\n"
            )

            self.studio_log_box.insert(
                tk.END,
                "[RUN STUDIO] STARTING PIPELINE\n"
            )

            self.studio_log_box.insert(
                tk.END,
                f"Topic: {topic}\n"
            )

            self.studio_log_box.insert(
                tk.END,
                f"Platform: {platform}\n"
            )

            self.studio_log_box.insert(
                tk.END,
                f"Video Type: {video_type}\n"
            )

            self.studio_log_box.insert(
                tk.END,
                f"Run Mode: {run_mode}\n\n"
            )

            # =========================================
            # ENV INJECTION
            # =========================================

            os.environ["STUDIO_TOPIC"] = topic
            os.environ["STUDIO_PLATFORM"] = platform
            os.environ["STUDIO_MODE"] = run_mode
            os.environ["STUDIO_VIDEO_TYPE"] = video_type

            try:

                env_copy = os.environ.copy()
                env_copy["PYTHONIOENCODING"] = "utf-8"
                env_copy["PYTHONUTF8"] = "1"

                process = subprocess.Popen(
                    [
                        sys.executable,
                        "test_full_ai_video_pipeline.py"
                ],
                    cwd=PROJECT_ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env_copy
                  )                                   

                for line in process.stdout:

                    self.studio_log_box.insert(
                        tk.END,
                        line
                    )

                    self.studio_log_box.see(tk.END)

                    self.root.update_idletasks()

                process.wait()

                if process.returncode == 0:

                    self.studio_log_box.insert(
                        tk.END,
                        "\n[RUN STUDIO] PIPELINE COMPLETE\n"
                    )

                else:

                    self.studio_log_box.insert(
                        tk.END,
                        "\n[RUN STUDIO] PIPELINE FAILED\n"
                    )

            finally:

                self.progress.stop()
                self.is_running = False

        self.run_threaded(task)

    # =========================================================
    # PROVIDER SYSTEM
    # =========================================================

    def load_json_file(self, path, default):

        if not path.exists():
            return default

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_json_file(self, path, data):

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def load_provider_panel(self):

        for widget in self.provider_frame.winfo_children():
            widget.destroy()

        self.provider_vars = {}

        registry = self.load_json_file(
            PROVIDER_REGISTRY_FILE,
            {}
        )

        active = self.load_json_file(
            ACTIVE_PROVIDERS_FILE,
            {}
        )

        row = 0

        for category, providers in registry.items():

            tk.Label(
                self.provider_frame,
                text=category.upper(),
                font=("Arial", 12, "bold"),
                width=16,
                anchor="w"
            ).grid(
                row=row,
                column=0,
                padx=6,
                pady=8,
                sticky="w"
            )

            names = [
                provider.get("name", "")
                for provider in providers
            ]

            selected = active.get(category)

            if selected not in names and names:
                selected = names[0]

            var = tk.StringVar(value=selected or "")
            self.provider_vars[category] = var

            combo = ttk.Combobox(
                self.provider_frame,
                textvariable=var,
                values=names,
                state="readonly",
                width=32
            )

            combo.grid(
                row=row,
                column=1,
                padx=6,
                pady=8,
                sticky="w"
            )

            row += 1

        self.refresh_provider_status_box()

    def refresh_provider_status_box(self):

        self.provider_status_box.delete("1.0", tk.END)

        registry = self.load_json_file(
            PROVIDER_REGISTRY_FILE,
            {}
        )

        active = self.load_json_file(
            ACTIVE_PROVIDERS_FILE,
            {}
        )

        for category, providers in registry.items():

            self.provider_status_box.insert(
                tk.END,
                f"\n[{category.upper()}]\n"
            )

            for provider in providers:

                name = provider.get("name", "")
                mode = provider.get("mode", "api")
                env_name = provider.get("api_key_env", "")

                active_mark = ""

                if active.get(category) == name:
                    active_mark = " <-- ACTIVE"

                if mode == "browser":
                    status = "BROWSER MODE"

                elif env_name and os.getenv(env_name):
                    status = "API OK"

                else:
                    status = "NO API KEY"

                self.provider_status_box.insert(
                    tk.END,
                    f"- {name} | {status}{active_mark}\n"
                )

    def save_active_providers(self):

        active = {}

        for category, var in self.provider_vars.items():
            active[category] = var.get()

        self.save_json_file(
            ACTIVE_PROVIDERS_FILE,
            active
        )

        self.refresh_provider_status_box()
        self.refresh_active_provider_box()

        messagebox.showinfo(
            "Saved",
            "Active providers saved successfully."
        )

    def refresh_active_provider_box(self):

        self.active_provider_box.delete("1.0", tk.END)

        active = self.load_json_file(
            ACTIVE_PROVIDERS_FILE,
            {}
        )

        for category, provider in active.items():

            self.active_provider_box.insert(
                tk.END,
                f"{category.upper()} : {provider}\n"
            )

    # =========================================================
    # UTILITIES
    # =========================================================

    def log(self, message):

        self.log_box.insert(
            tk.END,
            message + "\n"
        )

        self.log_box.see(tk.END)

        self.root.update_idletasks()

    def clear_log(self):

        self.log_box.delete(
            "1.0",
            tk.END
        )

        self.log("Log cleared.")

    def run_threaded(self, target):

        if self.is_running:

            messagebox.showwarning(
                "Busy",
                "Another process is running."
            )

            return

        thread = threading.Thread(
            target=target,
            daemon=True
        )

        thread.start()

    def run_command(self, command, title):

        self.log("")
        self.log("=" * 80)
        self.log(title)
        self.log("=" * 80)

        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        for line in process.stdout:
            self.log(line.rstrip())

        process.wait()

        if process.returncode == 0:
            self.log(f"[OK] {title} complete.")
        else:
            self.log(f"[ERROR] {title} failed.")

    def build_final_handoff(self):

        def task():

            self.is_running = True
            self.progress.start()

            try:

                self.run_command(
                    [
                        sys.executable,
                        "-m",
                        "core.project_brain_engine"
                    ],
                    "PROJECT BRAIN ENGINE"
                )

            finally:

                self.progress.stop()
                self.is_running = False

        self.run_threaded(task)

    def run_full_pipeline(self):

        def task():

            self.is_running = True
            self.progress.start()

            try:

                self.run_command(
                    [
                        sys.executable,
                        "test_full_ai_video_pipeline.py"
                    ],
                    "FULL VIDEO PIPELINE"
                )

            finally:

                self.progress.stop()
                self.is_running = False

        self.run_threaded(task)

    def open_ai_browser(self):

        try:

            subprocess.Popen([
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "--remote-debugging-port=9222",
                (
                    "--user-data-dir="
                    "C:\\Users\\kaman\\Desktop\\"
                    "ModirAgentOS\\storage\\"
                    "real_chrome_profile"
                )
            ])

            self.log("[OK] AI Browser opened.")

        except Exception as e:

            self.log(
                f"[ERROR] Browser failed: {e}"
            )

    def show_topic_memory(self):

        def task():

            self.is_running = True
            self.progress.start()

            try:

                self.run_command(
                    [
                        sys.executable,
                        "-m",
                        "core.topic_memory_engine"
                    ],
                    "TOPIC MEMORY"
                )

            finally:

                self.progress.stop()
                self.is_running = False

        self.run_threaded(task)

    def open_path(self, path):

        path = Path(path)

        if not path.exists():

            messagebox.showerror(
                "Not found",
                str(path)
            )

            return

        subprocess.Popen(
            ["explorer", str(path)]
        )

    def open_project_brain(self):
        self.open_path(PROJECT_BRAIN_DIR)

    def open_outputs(self):
        self.open_path(OUTPUTS_DIR)

    def open_handoff(self):
        self.open_path(HANDOFF_FILE)

    def open_provider_config(self):
        self.open_path(CONFIG_DIR)

    def clean_downloads(self):

        if not DOWNLOADS_DIR.exists():
            return

        shutil.rmtree(
            DOWNLOADS_DIR,
            ignore_errors=True
        )

        DOWNLOADS_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        self.log("[OK] Downloads cleaned.")

    def clean_outputs(self):

        if not OUTPUTS_DIR.exists():
            return

        for item in OUTPUTS_DIR.iterdir():

            if item.name not in [
                "music",
                "thumbnails"
            ]:

                if item.is_dir():

                    shutil.rmtree(
                        item,
                        ignore_errors=True
                    )

        self.log("[OK] Test outputs cleaned.")

    def clean_temp_files(self):

        removed = 0

        for root, dirs, files in os.walk(
            PROJECT_ROOT
        ):

            dirs[:] = [
                d for d in dirs
                if d != "venv"
            ]

            for d in dirs:

                if d == "__pycache__":

                    shutil.rmtree(
                        Path(root) / d,
                        ignore_errors=True
                    )

                    removed += 1

            for file in files:

                if (
                    file.endswith(".tmp")
                    or file.endswith(".log")
                ):

                    try:

                        os.remove(
                            Path(root) / file
                        )

                        removed += 1

                    except:
                        pass

        self.log(
            f"[OK] Temp cleanup complete. "
            f"Removed: {removed}"
        )

    def create_backup(self):

        BACKUP_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        backup_name = (
            "ModirAgentOS_BACKUP_"
            + datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )
            + ".zip"
        )

        backup_path = (
            BACKUP_DIR /
            backup_name
        )

        self.log("[BACKUP] Creating backup...")

        with zipfile.ZipFile(
            backup_path,
            "w",
            zipfile.ZIP_DEFLATED
        ) as zipf:

            for root, dirs, files in os.walk(
                PROJECT_ROOT
            ):

                dirs[:] = [

                    d for d in dirs

                    if d not in [
                        "venv",
                        "__pycache__",
                        "outputs",
                        "downloads",
                        "real_chrome_profile",
                        "backups",
                    ]
                ]

                for file in files:

                    filepath = (
                        Path(root) / file
                    )

                    arcname = filepath.relative_to(
                        PROJECT_ROOT
                    )

                    zipf.write(
                        filepath,
                        arcname
                    )

        self.log(
            f"[OK] Backup created:\n"
            f"{backup_path}"
        )


def main():

    root = tk.Tk()

    app = ModirAgentControlCenter(
        root
    )

    root.mainloop()


if __name__ == "__main__":
    main()