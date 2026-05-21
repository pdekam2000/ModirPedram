import json
from pathlib import Path


class ControlCenter:
    def __init__(self):
        self.base_output = Path(
            "outputs"
        )

    def print_header(self):
        print("\n" + "=" * 80)
        print("MODIRAGENT OS - CONTROL CENTER")
        print("=" * 80)

    def show_file_status(
        self,
        title,
        path,
    ):
        exists = Path(path).exists()

        status = (
            "READY"
            if exists
            else "MISSING"
        )

        print(
            f"{title:<35} {status}"
        )

    def show_pipeline_status(self):
        print("\nPIPELINE STATUS\n")

        self.show_file_status(
            "SEO Package",
            (
                "outputs/seo_packages/"
                "episode_01_seo_package.json"
            ),
        )

        self.show_file_status(
            "Performance Report",
            (
                "outputs/performance_reports/"
                "episode_01_report.json"
            ),
        )

        self.show_file_status(
            "Optimization Strategy",
            (
                "outputs/optimization/"
                "episode_01_optimization.json"
            ),
        )

        self.show_file_status(
            "Publishing Package",
            (
                "outputs/publishing/"
                "episode_01_publish_package.json"
            ),
        )

        self.show_file_status(
            "Final Hooked Video",
            (
                "outputs/postprocessed/"
                "episode_01_final_hooked_video.mp4"
            ),
        )

        self.show_file_status(
            "Thumbnail",
            (
                "outputs/thumbnails/"
                "episode_01_thumbnail.jpg"
            ),
        )

        self.show_file_status(
            "Learning Memory",
            (
                "outputs/ai_memory/"
                "learning_memory.json"
            ),
        )

    def show_latest_scores(self):
        report_path = (
            "outputs/performance_reports/"
            "episode_01_report.json"
        )

        if not Path(report_path).exists():
            print(
                "\nNo performance report found."
            )
            return

        with open(
            report_path,
            "r",
            encoding="utf-8",
        ) as f:
            report = json.load(f)

        print("\nLATEST PERFORMANCE\n")

        print(
            "Overall Score:",
            report["overall_score"],
        )

        print(
            "Rating:",
            report["rating"],
        )

    def show_memory_summary(self):
        memory_path = (
            "outputs/ai_memory/"
            "learning_memory.json"
        )

        if not Path(memory_path).exists():
            print(
                "\nNo AI memory found."
            )
            return

        with open(
            memory_path,
            "r",
            encoding="utf-8",
        ) as f:
            memory = json.load(f)

        print("\nAI MEMORY SUMMARY\n")

        print(
            "Total Learned Videos:",
            len(memory["videos"]),
        )

        print(
            "Best Hooks Stored:",
            len(memory["best_hooks"]),
        )

        print(
            "Best Thumbnail Styles:",
            len(
                memory[
                    "best_thumbnail_styles"
                ]
            ),
        )

    def run(self):
        self.print_header()

        self.show_pipeline_status()

        self.show_latest_scores()

        self.show_memory_summary()

        print("\n" + "=" * 80)
        print("CONTROL CENTER READY")
        print("=" * 80)


if __name__ == "__main__":
    dashboard = ControlCenter()
    dashboard.run()