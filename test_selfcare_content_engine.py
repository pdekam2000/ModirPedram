from core.selfcare_content_engine import SelfcareContentEngine


def main():
    engine = SelfcareContentEngine()

    plan = engine.build_mask_video(
        topic="calming yogurt, honey, and oat mask for tired-looking skin"
    )

    print("\nTITLE:")
    print(plan.title)

    print("\nHOOK:")
    print(plan.hook)

    print("\nRECIPE:")
    print(plan.recipe)

    print("\nSAFETY NOTE:")
    print(plan.safety_note)

    print("\nVOICEOVER:")
    print(plan.voiceover)

    print("\nVIDEO PROMPTS:")
    for i, prompt in enumerate(plan.video_prompts, start=1):
        print("\n" + "=" * 80)
        print(f"CLIP {i}")
        print("=" * 80)
        print(prompt)


if __name__ == "__main__":
    main()