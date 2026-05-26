class ProgressTracker:

    STAGES = [
        {
            "name": "Planning / Topic",
            "percent": 5,
            "markers": [
                "full ai video pipeline",
                "[run studio]",
                "custom topic received",
                "[trend topic]",
            ],
        },
        {
            "name": "Story / Prompt",
            "percent": 15,
            "markers": [
                "viral package",
                "video prompts",
                "direction data",
                "timeline",
            ],
        },
        {
            "name": "Voice",
            "percent": 25,
            "markers": [
                "elevenlabs",
                "narration",
                "voice",
                "generating narration",
            ],
        },
        {
            "name": "Video Clip 1",
            "percent": 40,
            "markers": [
                "clip 1",
                "generating clip 1",
                "[runway browser] clip 1",
                "[runway] generating clip 1",
            ],
        },
        {
            "name": "Video Clip 2",
            "percent": 55,
            "markers": [
                "clip 2",
                "generating clip 2",
                "[runway browser] clip 2",
                "[runway] generating clip 2",
            ],
        },
        {
            "name": "Video Clip 3",
            "percent": 70,
            "markers": [
                "clip 3",
                "generating clip 3",
                "[runway browser] clip 3",
                "[runway] generating clip 3",
            ],
        },
        {
            "name": "Audio Sync",
            "percent": 78,
            "markers": [
                "syncing clip audio",
                "audio sync",
            ],
        },
        {
            "name": "Assembly",
            "percent": 84,
            "markers": [
                "assembly",
                "assembled_video",
                "assemble video",
            ],
        },
        {
            "name": "Subtitles",
            "percent": 90,
            "markers": [
                "generating subtitles",
                "burning subtitles",
                "subtitles",
            ],
        },
        {
            "name": "Music / Overlays",
            "percent": 95,
            "markers": [
                "adding music",
                "adding hook overlay",
                "adding ingredient overlay",
                "thumbnail",
                "seo package",
            ],
        },
        {
            "name": "Complete",
            "percent": 100,
            "markers": [
                "full pipeline complete",
                "pipeline complete",
                "final video:",
            ],
        },
    ]

    def __init__(self):
        self.current_stage = None
        self.current_percent = 0

    def detect(self, line):
        clean_line = str(line).strip()
        lower_line = clean_line.lower()

        for stage in self.STAGES:
            for marker in stage["markers"]:
                if marker.lower() in lower_line:
                    if stage["percent"] >= self.current_percent:
                        self.current_stage = stage["name"]
                        self.current_percent = stage["percent"]

                    return {
                        "stage": self.current_stage,
                        "percent": self.current_percent,
                    }

        return None

    def detect_percent(self, line):
        result = self.detect(line)
        if result:
            return result["percent"]
        return None

    def detect_stage(self, line):
        result = self.detect(line)
        if result:
            return result["stage"]
        return None

    def reset(self):
        self.current_stage = None
        self.current_percent = 0