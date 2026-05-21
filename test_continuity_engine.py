from core.continuity_engine import ContinuityEngine


def main():
    engine = ContinuityEngine(clip_duration=10)

    clips = engine.build_three_clip_story(
        main_idea="""
A man hears strange whispers inside an abandoned underground bunker
while searching for a missing tape recorder.
""",
        visual_style="""
dark cinematic horror, realistic lighting, subtle fog,
cold colors, highly detailed, suspenseful atmosphere
""",
        character="""
same man, short dark hair, black jacket, tired face
""",
        location="""
same underground concrete bunker with flickering lights
""",
        camera_style="""
slow handheld cinematic movement, realistic horror cinematography
""",
    )

    print("\n" + "=" * 80)

    for clip in clips:
        print(f"\nCLIP {clip.clip_number} — {clip.title}")
        print("-" * 80)
        print(clip.prompt)
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()