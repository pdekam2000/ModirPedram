import json
from pathlib import Path
from datetime import datetime


class TopicMemoryEngine:

    def __init__(self):

        self.memory_dir = Path(
            "project_brain/topic_memory"
        )

        self.memory_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.memory_file = (
            self.memory_dir /
            "used_topics.json"
        )

        self.memory = self.load_memory()

    def load_memory(self):

        if self.memory_file.exists():

            try:

                with open(
                    self.memory_file,
                    "r",
                    encoding="utf-8"
                ) as f:

                    return json.load(f)

            except:
                pass

        return {
            "topics": []
        }

    def save_memory(self):

        with open(
            self.memory_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                self.memory,
                f,
                indent=2,
                ensure_ascii=False
            )

    def normalize_topic(self, topic):

        return (
            topic
            .lower()
            .strip()
            .replace("-", " ")
            .replace("_", " ")
        )

    def calculate_similarity(
        self,
        topic_a,
        topic_b
    ):

        a_words = set(
            self.normalize_topic(topic_a).split()
        )

        b_words = set(
            self.normalize_topic(topic_b).split()
        )

        if not a_words or not b_words:
            return 0

        overlap = a_words.intersection(
            b_words
        )

        similarity = (
            len(overlap)
            / max(len(a_words), len(b_words))
        )

        return similarity

    def topic_exists(
        self,
        topic,
        similarity_threshold=0.60
    ):

        normalized = self.normalize_topic(
            topic
        )

        for item in self.memory["topics"]:

            existing = self.normalize_topic(
                item["topic"]
            )

            if normalized == existing:
                return True

            similarity = self.calculate_similarity(
                normalized,
                existing
            )

            if similarity >= similarity_threshold:
                return True

        return False

    def add_topic(
        self,
        topic,
        source="unknown"
    ):

        if self.topic_exists(topic):
            return False

        self.memory["topics"].append({
            "topic": topic,
            "source": source,
            "created_at": str(datetime.now())
        })

        self.save_memory()

        return True

    def get_recent_topics(
        self,
        limit=20
    ):

        topics = self.memory["topics"]

        return topics[-limit:]

    def print_summary(self):

        print("\n" + "=" * 60)
        print("TOPIC MEMORY SUMMARY")
        print("=" * 60)

        print(
            f"Stored topics: "
            f"{len(self.memory['topics'])}"
        )

        print("\nRecent topics:\n")

        recent = self.get_recent_topics()

        if not recent:
            print("No topics yet.")
            return

        for item in reversed(recent):

            print(
                f"- {item['topic']} "
                f"[{item['source']}]"
            )


if __name__ == "__main__":

    engine = TopicMemoryEngine()

    engine.print_summary()