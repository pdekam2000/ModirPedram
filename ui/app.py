from pathlib import Path

import os
import sys
import json
import time
import queue
import shutil
import zipfile
import signal
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog

from dotenv import load_dotenv

from ui.services.runner_service import RunnerService
from ui.services.env_service import EnvService
from ui.components.progress_tracker import ProgressTracker


# =========================================================
# PATHS
# =========================================================

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


# =========================================================
# MAIN UI
# =========================================================

class ModirAgentControlCenter:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "ModirAgent OS - Created by Pedram Kamangar"
        )

        self.root.geometry("1380x940")
        self.root.minsize(1180, 820)

        self.is_running = False
        self.studio_process = None
        self.provider_vars = {}

        self.runner_service = RunnerService(PROJECT_ROOT)
        self.env_service = EnvService(PROJECT_ROOT)
        self.progress_tracker = ProgressTracker()

        # Thread-safe UI queues
        self.dashboard_log_queue = queue.Queue()
        self.studio_log_queue = queue.Queue()

        self.build_ui()
        self.load_provider_panel()

        self.root.after(150, self.process_dashboard_log_queue)
        self.root.after(150, self.process_studio_log_queue)

        self.queue_dashboard_log("ModirAgent Control Center Ready.")

    # =========================================================
    # UI ROOT
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

        title.pack(pady=(10, 2))

        creator = tk.Label(
            self.root,
            text="Created by Pedram Kamangar",
            font=("Arial", 11)
        )

        creator.pack(pady=(0, 8))

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
    # DASHBOARD TAB
    # =========================================================

    def build_dashboard_tab(self):

        button_frame = tk.Frame(self.dashboard_tab)
        button_frame.pack(pady=12)

        buttons = [
            ("BUILD FINAL HANDOFF", self.build_final_handoff),
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
            mode="determinate",
            length=780,
            maximum=100
        )

        self.progress["value"] = 0
        self.progress.pack(pady=10)

        self.status_label = tk.Label(
            self.dashboard_tab,
            text="Status: Ready",
            font=("Arial", 10)
        )

        self.status_label.pack()

        self.log_box = tk.Text(
            self.dashboard_tab,
            width=165,
            height=30,
            wrap="word"
        )

        self.log_box.pack(padx=10, pady=10)

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

        info = tk.Label(
            self.providers_tab,
            text=(
                "Choose which provider the pipeline should use. "
                "For current browser generation use video = runway_browser."
            ),
            font=("Arial", 10)
        )

        info.pack(pady=(0, 8))

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

        tk.Button(
            action_frame,
            text="SET RUNWAY BROWSER",
            width=28,
            height=2,
            command=self.set_runway_browser_provider
        ).grid(row=0, column=3, padx=6)

        self.provider_status_box = tk.Text(
            self.providers_tab,
            width=165,
            height=30,
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

        title.pack(pady=(8, 4))

        form_frame = tk.LabelFrame(
            self.runstudio_tab,
            text="Project Input",
            padx=10,
            pady=8
        )

        form_frame.pack(fill="x", padx=16, pady=8)

        # -----------------------------------------------------
        # Topic / Niche
        # -----------------------------------------------------

        tk.Label(
            form_frame,
            text="Topic / Niche",
            font=("Arial", 11, "bold")
        ).grid(row=0, column=0, sticky="w", pady=8)

        self.topic_var = tk.StringVar()

        tk.Entry(
            form_frame,
            textvariable=self.topic_var,
            width=78
        ).grid(row=0, column=1, padx=10, pady=8, sticky="w")

        # -----------------------------------------------------
        # Content Mode
        # -----------------------------------------------------

        tk.Label(
            form_frame,
            text="Content Mode",
            font=("Arial", 11, "bold")
        ).grid(row=1, column=0, sticky="w", pady=8)

        self.content_mode_var = tk.StringVar(value="channel_niche_trend")

        ttk.Combobox(
            form_frame,
            textvariable=self.content_mode_var,
            values=[
                "channel_niche_trend",
                "custom_one_time_topic"
            ],
            state="readonly",
            width=34
        ).grid(row=1, column=1, sticky="w", padx=10)

        # -----------------------------------------------------
        # Trend + Repetition Options
        # -----------------------------------------------------

        options_frame = tk.Frame(form_frame)
        options_frame.grid(row=2, column=1, sticky="w", padx=10, pady=6)

        self.use_trends_var = tk.BooleanVar(value=True)
        self.avoid_repeat_var = tk.BooleanVar(value=True)
        self.director_mode_var = tk.BooleanVar(value=True)

        tk.Checkbutton(
            options_frame,
            text="Use daily trend research",
            variable=self.use_trends_var
        ).grid(row=0, column=0, sticky="w", padx=(0, 18))

        tk.Checkbutton(
            options_frame,
            text="Avoid repeated topics",
            variable=self.avoid_repeat_var
        ).grid(row=0, column=1, sticky="w", padx=(0, 18))

        tk.Checkbutton(
            options_frame,
            text="AI Director structure",
            variable=self.director_mode_var
        ).grid(row=0, column=2, sticky="w")

        # -----------------------------------------------------
        # Platform
        # -----------------------------------------------------

        tk.Label(
            form_frame,
            text="Platform",
            font=("Arial", 11, "bold")
        ).grid(row=3, column=0, sticky="w", pady=8)

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
            width=34
        ).grid(row=3, column=1, sticky="w", padx=10)

        # -----------------------------------------------------
        # Video Type
        # -----------------------------------------------------

        tk.Label(
            form_frame,
            text="Video Type",
            font=("Arial", 11, "bold")
        ).grid(row=4, column=0, sticky="w", pady=8)

        self.video_type_var = tk.StringVar(value="ai_video")

        ttk.Combobox(
            form_frame,
            textvariable=self.video_type_var,
            values=[
                "ai_video",
                "slide_video",
                "voice_only",
                "seo_only",
                "music_only",
                "music_video"
            ],
            state="readonly",
            width=34
        ).grid(row=4, column=1, sticky="w", padx=10)

        # -----------------------------------------------------
        # Run Mode
        # -----------------------------------------------------

        tk.Label(
            form_frame,
            text="Run Mode",
            font=("Arial", 11, "bold")
        ).grid(row=5, column=0, sticky="w", pady=8)

        self.run_mode_var = tk.StringVar(value="full_video")

        ttk.Combobox(
            form_frame,
            textvariable=self.run_mode_var,
            values=[
                "full_video",
                "video_only",
                "script_only",
                "seo_only",
                "voice_only",
                "postprocess_only"
            ],
            state="readonly",
            width=34
        ).grid(row=5, column=1, sticky="w", padx=10)

        # -----------------------------------------------------
        # Story Style
        # -----------------------------------------------------

        tk.Label(
            form_frame,
            text="Story Style",
            font=("Arial", 11, "bold")
        ).grid(row=6, column=0, sticky="w", pady=8)

        self.story_style_var = tk.StringVar(value="cinematic_professional")

        ttk.Combobox(
            form_frame,
            textvariable=self.story_style_var,
            values=[
                "cinematic_professional",
                "viral_hook_fast",
                "educational_clean",
                "dark_mystery",
                "luxury_brand",
                "emotional_story",
                "documentary_style"
            ],
            state="readonly",
            width=34
        ).grid(row=6, column=1, sticky="w", padx=10)

        # -----------------------------------------------------
        # Output Language
        # -----------------------------------------------------

        tk.Label(
            form_frame,
            text="Output Language",
            font=("Arial", 11, "bold")
        ).grid(row=7, column=0, sticky="w", pady=8)

        self.output_language_var = tk.StringVar(value="English")

        ttk.Combobox(
            form_frame,
            textvariable=self.output_language_var,
            values=[
                "English",
                "German",
                "Persian",
                "Spanish",
                "French",
                "Arabic",
                "Hindi",
                "Portuguese"
            ],
            state="readonly",
            width=34
        ).grid(row=7, column=1, sticky="w", padx=10)

        # -----------------------------------------------------
        # Music
        # -----------------------------------------------------

        music_frame = tk.LabelFrame(
            self.runstudio_tab,
            text="Music / Audio",
            padx=10,
            pady=8
        )

        music_frame.pack(fill="x", padx=16, pady=6)

        tk.Label(
            music_frame,
            text="Music Source",
            font=("Arial", 11, "bold")
        ).grid(row=0, column=0, sticky="w", pady=8)

        self.music_source_var = tk.StringVar(value="local_default")

        ttk.Combobox(
            music_frame,
            textvariable=self.music_source_var,
            values=[
                "local_default",
                "local_mp3",
                "suno_ai",
                "no_music"
            ],
            state="readonly",
            width=34
        ).grid(row=0, column=1, sticky="w", padx=10)

        tk.Label(
            music_frame,
            text="Local MP3 File",
            font=("Arial", 11, "bold")
        ).grid(row=1, column=0, sticky="w", pady=8)

        music_file_frame = tk.Frame(music_frame)
        music_file_frame.grid(row=1, column=1, sticky="w", padx=10)

        self.music_file_var = tk.StringVar(value="")

        tk.Entry(
            music_file_frame,
            textvariable=self.music_file_var,
            width=60
        ).grid(row=0, column=0, padx=(0, 6))

        tk.Button(
            music_file_frame,
            text="Choose MP3",
            width=14,
            command=self.browse_studio_music_file
        ).grid(row=0, column=1)

        # -----------------------------------------------------
        # Providers
        # -----------------------------------------------------

        provider_frame = tk.LabelFrame(
            self.runstudio_tab,
            text="Active Providers",
            padx=10,
            pady=8
        )

        provider_frame.pack(fill="x", padx=16, pady=6)

        self.active_provider_box = tk.Text(
            provider_frame,
            width=120,
            height=5
        )

        self.active_provider_box.pack(side="left", padx=(0, 10))

        tk.Button(
            provider_frame,
            text="Refresh",
            width=14,
            height=2,
            command=self.refresh_active_provider_box
        ).pack(side="left", padx=4)

        tk.Button(
            provider_frame,
            text="Set Runway Browser",
            width=18,
            height=2,
            command=self.set_runway_browser_provider
        ).pack(side="left", padx=4)

        self.refresh_active_provider_box()

        # -----------------------------------------------------
        # Buttons
        # -----------------------------------------------------

        button_frame = tk.Frame(self.runstudio_tab)
        button_frame.pack(pady=8)

        self.generate_button = tk.Button(
            button_frame,
            text="GENERATE FULL VIDEO",
            width=28,
            height=2,
            command=self.run_studio_pipeline
        )

        self.generate_button.grid(row=0, column=0, padx=6)

        self.cancel_button = tk.Button(
            button_frame,
            text="CANCEL RUN",
            width=24,
            height=2,
            command=self.cancel_studio_pipeline,
            state="disabled"
        )

        self.cancel_button.grid(row=0, column=1, padx=6)

        tk.Button(
            button_frame,
            text="OPEN LATEST OUTPUT",
            width=28,
            height=2,
            command=self.open_outputs
        ).grid(row=0, column=2, padx=6)

        tk.Button(
            button_frame,
            text="CLEAR STUDIO LOG",
            width=24,
            height=2,
            command=self.clear_studio_log
        ).grid(row=0, column=3, padx=6)

        # -----------------------------------------------------
        # Studio Progress
        # -----------------------------------------------------

        self.studio_progress = ttk.Progressbar(
            self.runstudio_tab,
            mode="determinate",
            length=820,
            maximum=100
        )

        self.studio_progress["value"] = 0
        self.studio_progress.pack(pady=(6, 4))

        self.studio_status_label = tk.Label(
            self.runstudio_tab,
            text="Studio Status: Ready",
            font=("Arial", 10)
        )

        self.studio_status_label.pack(pady=(0, 6))

        # -----------------------------------------------------
        # Studio Log
        # -----------------------------------------------------

        self.studio_log_box = tk.Text(
            self.runstudio_tab,
            width=165,
            height=16,
            wrap="word"
        )

        self.studio_log_box.pack(padx=10, pady=10, fill="both", expand=True)

    # =========================================================
    # STUDIO HELPERS
    # =========================================================

    def browse_studio_music_file(self):

        file_path = filedialog.askopenfilename(
            title="Choose background music MP3",
            filetypes=[
                ("MP3 files", "*.mp3"),
                ("Audio files", "*.mp3 *.wav *.m4a"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            self.music_file_var.set(file_path)
            self.music_source_var.set("local_mp3")

    def clear_studio_log(self):

        self.studio_log_box.delete("1.0", tk.END)
        self.studio_status_label.config(text="Studio Status: Ready")
        self.studio_progress["value"] = 0

    def queue_studio_log(self, message):

        self.studio_log_queue.put(("log", message))

    def queue_studio_status(self, status):

        self.studio_log_queue.put(("status", status))

    def queue_studio_progress(self, percent, stage):

        self.studio_log_queue.put(("progress", percent, stage))

    def process_studio_log_queue(self):

        try:

            while True:

                item = self.studio_log_queue.get_nowait()
                event_type = item[0]

                if event_type == "log":

                    self.studio_log_box.insert(tk.END, item[1])
                    self.studio_log_box.see(tk.END)

                elif event_type == "progress":

                    percent = item[1]
                    stage = item[2]

                    self.studio_progress["value"] = percent
                    self.studio_status_label.config(
                        text=f"Studio Status: {stage} - {percent}%"
                    )

                elif event_type == "status":

                    self.studio_status_label.config(text=item[1])

                elif event_type == "done":

                    self.is_running = False
                    self.studio_process = None
                    self.generate_button.config(state="normal")
                    self.cancel_button.config(state="disabled")

                elif event_type == "failed":

                    self.is_running = False
                    self.studio_process = None
                    self.generate_button.config(state="normal")
                    self.cancel_button.config(state="disabled")
                    self.studio_status_label.config(
                        text="Studio Status: FAILED"
                    )

        except queue.Empty:
            pass

        self.root.after(150, self.process_studio_log_queue)

    # =========================================================
    # RUN STUDIO EXECUTION
    # =========================================================

    def run_studio_pipeline(self):

        if self.is_running:

            messagebox.showwarning(
                "Busy",
                "Another process is running."
            )

            return

        topic = self.topic_var.get().strip()
        platform = self.platform_var.get().strip()
        video_type = self.video_type_var.get().strip()
        run_mode = self.run_mode_var.get().strip()
        content_mode = self.content_mode_var.get().strip()
        music_source = self.music_source_var.get().strip()
        music_file = self.music_file_var.get().strip()
        story_style = self.story_style_var.get().strip()
        output_language = self.output_language_var.get().strip()

        use_trends = "1" if self.use_trends_var.get() else "0"
        avoid_repeat = "1" if self.avoid_repeat_var.get() else "0"
        director_mode = "1" if self.director_mode_var.get() else "0"

        if not topic:

            messagebox.showerror(
                "Missing Topic",
                "Please enter a topic or niche."
            )

            return

        self.is_running = True
        self.studio_process = None

        self.generate_button.config(state="disabled")
        self.cancel_button.config(state="normal")

        self.studio_progress["value"] = 0
        self.studio_status_label.config(
            text="Studio Status: Starting..."
        )

        self.studio_log_box.delete("1.0", tk.END)

        self.queue_studio_log("\n" + "=" * 90 + "\n")
        self.queue_studio_log("[RUN STUDIO] STARTING PROFESSIONAL PIPELINE\n")
        self.queue_studio_log("=" * 90 + "\n")
        self.queue_studio_log(f"Topic / Niche: {topic}\n")
        self.queue_studio_log(f"Content Mode: {content_mode}\n")
        self.queue_studio_log(f"Use Trends: {use_trends}\n")
        self.queue_studio_log(f"Avoid Repeat: {avoid_repeat}\n")
        self.queue_studio_log(f"AI Director: {director_mode}\n")
        self.queue_studio_log(f"Platform: {platform}\n")
        self.queue_studio_log(f"Video Type: {video_type}\n")
        self.queue_studio_log(f"Run Mode: {run_mode}\n")
        self.queue_studio_log(f"Story Style: {story_style}\n")
        self.queue_studio_log(f"Output Language: {output_language}\n")
        self.queue_studio_log(f"Music Source: {music_source}\n")

        if music_file:
            self.queue_studio_log(f"Music File: {music_file}\n")

        self.queue_studio_log("\n")

        # Environment contract for pipeline engines.
        # Existing old variables are preserved.
        os.environ["STUDIO_TOPIC"] = topic
        os.environ["STUDIO_PLATFORM"] = platform
        os.environ["STUDIO_MODE"] = run_mode
        os.environ["STUDIO_VIDEO_TYPE"] = video_type
        os.environ["STUDIO_MUSIC_SOURCE"] = music_source
        os.environ["STUDIO_MUSIC_FILE"] = music_file

        # New UI control variables.
        os.environ["STUDIO_CONTENT_MODE"] = content_mode
        os.environ["STUDIO_USE_TRENDS"] = use_trends
        os.environ["STUDIO_AVOID_REPEAT"] = avoid_repeat
        os.environ["STUDIO_DIRECTOR_MODE"] = director_mode
        os.environ["STUDIO_STORY_STYLE"] = story_style
        os.environ["STUDIO_OUTPUT_LANGUAGE"] = output_language

        def task():

            try:

                env_copy = os.environ.copy()
                env_copy["PYTHONIOENCODING"] = "utf-8"
                env_copy["PYTHONUTF8"] = "1"
                env_copy["PYTHONUNBUFFERED"] = "1"

                command = [
                    sys.executable,
                    "-u",
                    "-m",
                    "pipelines.full_video_pipeline"
                ]

                self.studio_log_queue.put(
                    (
                        "log",
                        "[RUN STUDIO] Command: "
                        + " ".join(command)
                        + "\n\n"
                    )
                )

                process = subprocess.Popen(
                    command,
                    cwd=PROJECT_ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    env=env_copy
                )

                self.studio_process = process

                for line in iter(process.stdout.readline, ""):

                    if not line:
                        break

                    progress_data = self.progress_tracker.detect(line)

                    if progress_data:

                        self.studio_log_queue.put(
                            (
                                "progress",
                                progress_data["percent"],
                                progress_data["stage"]
                            )
                        )

                        self.studio_log_queue.put(
                            (
                                "log",
                                (
                                    "\n[STAGE] "
                                    f"{progress_data['stage']} "
                                    f"- {progress_data['percent']}%\n"
                                )
                            )
                        )

                    self.studio_log_queue.put(("log", line))

                process.wait()

                if process.returncode == 0:

                    self.studio_log_queue.put(
                        ("progress", 100, "COMPLETE")
                    )

                    self.studio_log_queue.put(
                        (
                            "log",
                            "\n[RUN STUDIO] PIPELINE COMPLETE\n"
                        )
                    )

                    self.studio_log_queue.put(
                        (
                            "status",
                            "Studio Status: COMPLETE - 100%"
                        )
                    )

                    self.studio_log_queue.put(("done", None))

                else:

                    self.studio_log_queue.put(
                        (
                            "log",
                            (
                                "\n[RUN STUDIO] PIPELINE FAILED "
                                f"(code {process.returncode})\n"
                            )
                        )
                    )

                    self.studio_log_queue.put(("failed", None))

            except Exception as e:

                self.studio_log_queue.put(
                    ("log", f"\n[RUN STUDIO ERROR] {e}\n")
                )

                self.studio_log_queue.put(("failed", None))

        thread = threading.Thread(
            target=task,
            daemon=True
        )

        thread.start()

    def cancel_studio_pipeline(self):

        if not self.is_running:
            return

        if not self.studio_process:

            self.queue_studio_log(
                "\n[CANCEL] Process is not ready yet.\n"
            )

            return

        try:

            self.queue_studio_log(
                "\n[CANCEL] Terminating studio pipeline...\n"
            )

            self.studio_process.terminate()

            time.sleep(1)

            if self.studio_process.poll() is None:
                self.studio_process.kill()

            self.queue_studio_status(
                "Studio Status: CANCELLED"
            )

        except Exception as e:

            self.queue_studio_log(
                f"\n[CANCEL ERROR] {e}\n"
            )

        finally:

            self.studio_log_queue.put(("done", None))

    # =========================================================
    # PROVIDER SYSTEM
    # =========================================================

    def load_json_file(self, path, default):

        if not path.exists():
            return default

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def save_json_file(self, path, data):

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

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
                if provider.get("name", "")
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
                width=36
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

        self.provider_status_box.insert(
            tk.END,
            "PROVIDER STATUS\n"
            + "=" * 80
            + "\n\n"
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

        if not active:

            self.active_provider_box.insert(
                tk.END,
                "No active provider config found.\n"
            )

            return

        for category, provider in active.items():

            self.active_provider_box.insert(
                tk.END,
                f"{category.upper()} : {provider}\n"
            )

    def set_runway_browser_provider(self):

        active = self.load_json_file(
            ACTIVE_PROVIDERS_FILE,
            {}
        )

        if not active:
            active = {
                "video": "runway_browser",
                "music": "suno",
                "voice": "elevenlabs",
                "llm": "openai"
            }

        active["video"] = "runway_browser"

        self.save_json_file(
            ACTIVE_PROVIDERS_FILE,
            active
        )

        self.load_provider_panel()
        self.refresh_active_provider_box()

        messagebox.showinfo(
            "Provider Updated",
            "Video provider set to runway_browser."
        )

    # =========================================================
    # DASHBOARD LOG QUEUE
    # =========================================================

    def queue_dashboard_log(self, message):

        self.dashboard_log_queue.put(("log", message))

    def process_dashboard_log_queue(self):

        try:

            while True:

                item = self.dashboard_log_queue.get_nowait()

                if item[0] == "log":

                    self.log_box.insert(
                        tk.END,
                        item[1] + "\n"
                    )

                    self.log_box.see(tk.END)

                elif item[0] == "status":

                    self.status_label.config(text=item[1])

                elif item[0] == "progress":

                    self.progress["value"] = item[1]

                elif item[0] == "done":

                    self.is_running = False
                    self.progress.stop()

        except queue.Empty:
            pass

        self.root.after(150, self.process_dashboard_log_queue)

    # =========================================================
    # GENERAL UTILITIES
    # =========================================================

    def log(self, message):

        self.queue_dashboard_log(message)

    def clear_log(self):

        self.log_box.delete(
            "1.0",
            tk.END
        )

        self.queue_dashboard_log("Log cleared.")

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

        self.queue_dashboard_log("")
        self.queue_dashboard_log("=" * 80)
        self.queue_dashboard_log(title)
        self.queue_dashboard_log("=" * 80)

        try:

            process = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env={
                    **os.environ.copy(),
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONUTF8": "1",
                    "PYTHONUNBUFFERED": "1",
                }
            )

            for line in iter(process.stdout.readline, ""):
                self.queue_dashboard_log(line.rstrip())

            process.wait()

            if process.returncode == 0:
                self.queue_dashboard_log(f"[OK] {title} complete.")
            else:
                self.queue_dashboard_log(f"[ERROR] {title} failed.")

        except Exception as e:

            self.queue_dashboard_log(f"[ERROR] {title}: {e}")

    # =========================================================
    # DASHBOARD ACTIONS
    # =========================================================

    def build_final_handoff(self):

        def task():

            self.is_running = True
            self.dashboard_log_queue.put(("progress", 5))
            self.dashboard_log_queue.put(("status", "Status: Building project brain..."))

            try:

                self.run_command(
                    [
                        sys.executable,
                        "-u",
                        "-m",
                        "core.project_brain_engine"
                    ],
                    "PROJECT BRAIN ENGINE"
                )

            finally:

                self.dashboard_log_queue.put(("progress", 100))
                self.dashboard_log_queue.put(("status", "Status: Ready"))
                self.dashboard_log_queue.put(("done", None))

        self.run_threaded(task)

    def run_full_pipeline(self):

        def task():

            self.is_running = True
            self.dashboard_log_queue.put(("progress", 5))
            self.dashboard_log_queue.put(("status", "Status: Running full pipeline..."))

            try:

                self.run_command(
                    [
                        sys.executable,
                        "-u",
                        "test_full_ai_video_pipeline.py"
                    ],
                    "FULL VIDEO PIPELINE"
                )

            finally:

                self.dashboard_log_queue.put(("progress", 100))
                self.dashboard_log_queue.put(("status", "Status: Ready"))
                self.dashboard_log_queue.put(("done", None))

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

            self.queue_dashboard_log("[OK] AI Browser opened.")

        except Exception as e:

            self.queue_dashboard_log(
                f"[ERROR] Browser failed: {e}"
            )

    def show_topic_memory(self):

        def task():

            self.is_running = True
            self.dashboard_log_queue.put(("progress", 5))
            self.dashboard_log_queue.put(("status", "Status: Reading topic memory..."))

            try:

                self.run_command(
                    [
                        sys.executable,
                        "-u",
                        "-m",
                        "core.topic_memory_engine"
                    ],
                    "TOPIC MEMORY"
                )

            finally:

                self.dashboard_log_queue.put(("progress", 100))
                self.dashboard_log_queue.put(("status", "Status: Ready"))
                self.dashboard_log_queue.put(("done", None))

        self.run_threaded(task)

    # =========================================================
    # FILE / FOLDER ACTIONS
    # =========================================================

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

        if DOWNLOADS_DIR.exists():

            shutil.rmtree(
                DOWNLOADS_DIR,
                ignore_errors=True
            )

        DOWNLOADS_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        self.queue_dashboard_log("[OK] Downloads cleaned.")

    def clean_outputs(self):

        if not OUTPUTS_DIR.exists():

            self.queue_dashboard_log("[INFO] Outputs folder does not exist.")
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

                else:

                    try:
                        item.unlink()
                    except Exception:
                        pass

        self.queue_dashboard_log("[OK] Test outputs cleaned.")

    def clean_temp_files(self):

        def task():

            self.is_running = True
            self.dashboard_log_queue.put(("progress", 5))
            self.dashboard_log_queue.put(("status", "Status: Cleaning temp files..."))

            removed = 0

            skip_dirs = {
                "venv",
                ".venv",
                "__pycache__",
                ".git",
                "storage",
                "downloads",
                "outputs",
                "backups",
            }

            for root, dirs, files in os.walk(PROJECT_ROOT):

                dirs[:] = [
                    d for d in dirs
                    if d not in skip_dirs
                ]

                for d in list(dirs):

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

                        except Exception:
                            pass

            self.queue_dashboard_log(
                f"[OK] Temp cleanup complete. Removed: {removed}"
            )

            self.dashboard_log_queue.put(("progress", 100))
            self.dashboard_log_queue.put(("status", "Status: Ready"))
            self.dashboard_log_queue.put(("done", None))

        self.run_threaded(task)

    def create_backup(self):

        def task():

            self.is_running = True
            self.dashboard_log_queue.put(("progress", 5))
            self.dashboard_log_queue.put(("status", "Status: Creating backup..."))

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

            self.queue_dashboard_log("[BACKUP] Creating backup...")

            skip_dirs = {
                "venv",
                ".venv",
                "__pycache__",
                ".git",
                "outputs",
                "downloads",
                "real_chrome_profile",
                "browser_session",
                "backups",
                "backup_temp",
            }

            try:

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
                            if d not in skip_dirs
                        ]

                        for file in files:

                            if file.endswith((".mp4", ".mov", ".avi", ".zip")):
                                continue

                            filepath = (
                                Path(root) / file
                            )

                            try:

                                arcname = filepath.relative_to(
                                    PROJECT_ROOT
                                )

                                zipf.write(
                                    filepath,
                                    arcname
                                )

                            except Exception:
                                pass

                self.queue_dashboard_log(
                    f"[OK] Backup created:\n{backup_path}"
                )

            except Exception as e:

                self.queue_dashboard_log(
                    f"[ERROR] Backup failed: {e}"
                )

            self.dashboard_log_queue.put(("progress", 100))
            self.dashboard_log_queue.put(("status", "Status: Ready"))
            self.dashboard_log_queue.put(("done", None))

        self.run_threaded(task)


# =========================================================
# ENTRYPOINT
# =========================================================

def main():

    root = tk.Tk()

    app = ModirAgentControlCenter(
        root
    )

    root.mainloop()


if __name__ == "__main__":
    main()
