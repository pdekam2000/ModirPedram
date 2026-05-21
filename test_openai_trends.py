from providers.openai_trend_provider import OpenAITrendProvider


def main():
    trend_provider = OpenAITrendProvider()

    trends = trend_provider.generate_selfcare_trends(
        niche="women skincare and selfcare",
        platform="TikTok and Instagram Reels",
        count=5,
    )

    print("\nTREND RESULTS")
    print("=" * 80)
    print(trends)


if __name__ == "__main__":
    main()
    