from core.timeline_engine import TimelineEngine


def main():
    engine = TimelineEngine()
    timeline = engine.build_selfcare_timeline()

    print("\nVIDEO TIMELINE")
    print("=" * 80)
    print("Total duration:", timeline.total_duration, "seconds")

    for segment in timeline.segments:
        print("\n" + "-" * 80)
        print(f"Clip: {segment.clip_number}")
        print(f"Time: {segment.start_time} - {segment.end_time}")
        print(f"Scene: {segment.scene_label}")
        print(f"Emotion: {segment.emotion}")
        print(f"Pause after: {segment.pause_after}")
        print("Narration:")
        print(segment.narration)


if __name__ == "__main__":
    main()