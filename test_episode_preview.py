from core.content_series_planner import ContentSeriesPlanner
from core.selfcare_content_engine import SelfcareContentEngine

from full_selfcare_factory import add_brand_intro_to_prompts


EPISODE_NUMBER = 1


def main():
    planner = ContentSeriesPlanner()
    episode = planner.get_episode(EPISODE_NUMBER)

    content_engine = SelfcareContentEngine()
    plan = content_engine.build_mask_video(
        topic=episode.topic
    )

    prompts = add_brand_intro_to_prompts(
        prompts=plan.video_prompts,
        brand_intro=episode.brand_intro,
    )

    print("\nEPISODE PREVIEW")
    print("=" * 80)
    print("Series:", episode.series_name)
    print("Episode:", episode.episode_number)
    print("Category:", episode.category)
    print("Topic:", episode.topic)
    print("Title:", plan.title)
    print("Hook:", episode.hook)

    print("\nVIDEO PROMPTS:")
    for index, prompt in enumerate(prompts, start=1):
        print("\n" + "=" * 80)
        print(f"CLIP {index}")
        print("=" * 80)
        print(prompt)


if __name__ == "__main__":
    main()