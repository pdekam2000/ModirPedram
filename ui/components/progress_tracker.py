class ProgressTracker:

    STAGES = [
        {
            "name": "Voice",
            "percent": 10,
            "markers": ["[1]", "elevenlabs", "narration", "voice"],
        },
        {
            "name": "Hailuo",
            "percent": 25,
            "markers": ["[2]", "hailuo", "generating hailuo", "clips"],
        },
        {
            "name": "Audio Sync",
            "percent": 40,
            "markers": ["[3]", "syncing clip audio", "audio sync"],
        },
        {
            "name": "Assembly",
            "percent": 55,
            "markers": ["[4]", "assembly", "assembled_video"],
        },
        {
            "name": "Subtitles",
            "percent": 65,
            "markers": ["[5]", "[6]", "subtitles", "burning subtitles"],
        },
        {
            "name": "Music",
            "percent": 75,
            "markers": ["[7]", "[8]", "music", "smoothing audio"],
        },
        {
            "name": "Overlays",
            "percent": 85,
            "markers": ["[9]", "[10]", "ingredient overlay", "hook overlay"],
        },
        {
            "name": "SEO / Packaging",
            "percent": 95,
            "markers": ["[11]", "[12]", "[13]", "[14]", "[15]", "seo", "publishing package"],
        },
        {
            "name": "Complete",
            "percent": 100,
            "markers": ["[16]", "full test complete", "pipeline complete"],
        },
    ]

    def __init__(self):
        self.current_stage = None
        self.current_percent = 0

    def detect(self, line):
        clean_line = line.strip()
        lower_line = clean_line.lower()

        for stage in self.STAGES:
            for marker in stage["markers"]:
                if marker.lower() in lower_line:
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