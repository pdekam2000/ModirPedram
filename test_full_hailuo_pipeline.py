from core.continuity_engine import ContinuityEngine
from orchestrators.hailuo_multi_clip_orchestrator import HailuoMultiClipOrchestrator


def main():
    engine = ContinuityEngine(clip_duration=10)

    clip_plans = engine.build_three_clip_story(
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

    prompts = [plan.prompt for plan in clip_plans]

    print("\n[Continuity Pipeline] Starting connected clip generation...")
    for plan in clip_plans:
        print(f" - Clip {plan.clip_number}: {plan.title}")

    orchestrator = HailuoMultiClipOrchestrator(wait_seconds=150)

    downloaded_clips = orchestrator.run(prompts)

    print("\n[Continuity Pipeline] Downloaded clips:")
    for clip in downloaded_clips:
        print(" -", clip)


if __name__ == "__main__":
    main()