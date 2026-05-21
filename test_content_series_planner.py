from core.content_series_planner import ContentSeriesPlanner


def main():
    planner = ContentSeriesPlanner()
    ideas = planner.build_series()

    print("\nGLOW RITUAL SERIES PLAN")
    print("=" * 80)

    for idea in ideas:
        print(
            f"Episode {idea.episode_number:02d} | "
            f"{idea.category} | "
            f"{idea.topic}"
        )

    print("\nTEST EPISODE 1")
    print("=" * 80)

    episode = planner.get_episode(1)

    print("Series:", episode.series_name)
    print("Episode:", episode.episode_number)
    print("Category:", episode.category)
    print("Topic:", episode.topic)
    print("Hook:", episode.hook)
    print("Brand Intro:", episode.brand_intro)


if __name__ == "__main__":
    main()