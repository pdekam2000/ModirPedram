import random
from datetime import datetime


class TrendResearchEngine:

    def __init__(self):

        self.base_trends = [

            {
                "topic": "ice roller morning routine",
                "category": "skincare",
                "virality_score": 94,
                "platform": "TikTok",
            },

            {
                "topic": "glass skin hydration routine",
                "category": "skincare",
                "virality_score": 96,
                "platform": "TikTok",
            },

            {
                "topic": "overnight lip mask routine",
                "category": "lipcare",
                "virality_score": 90,
                "platform": "Instagram Reels",
            },

            {
                "topic": "cold spoon under eye trick",
                "category": "skincare",
                "virality_score": 92,
                "platform": "TikTok",
            },

            {
                "topic": "korean skincare layering",
                "category": "skincare",
                "virality_score": 95,
                "platform": "YouTube Shorts",
            },

            {
                "topic": "face icing morning routine",
                "category": "skincare",
                "virality_score": 93,
                "platform": "TikTok",
            },

            {
                "topic": "hair oil overnight ritual",
                "category": "haircare",
                "virality_score": 89,
                "platform": "Instagram Reels",
            },

            {
                "topic": "body glow exfoliation routine",
                "category": "bodycare",
                "virality_score": 88,
                "platform": "TikTok",
            },

            {
                "topic": "green tea depuff skincare",
                "category": "skincare",
                "virality_score": 91,
                "platform": "TikTok",
            },

            {
                "topic": "silk pillow skincare hack",
                "category": "beauty",
                "virality_score": 87,
                "platform": "YouTube Shorts",
            },

            {
                "topic": "hydrating rose water mist",
                "category": "skincare",
                "virality_score": 90,
                "platform": "Instagram Reels",
            },

            {
                "topic": "clean girl morning skincare",
                "category": "beauty",
                "virality_score": 97,
                "platform": "TikTok",
            },

            {
                "topic": "gua sha lymphatic routine",
                "category": "skincare",
                "virality_score": 95,
                "platform": "TikTok",
            },

            {
                "topic": "morning depuff facial massage",
                "category": "skincare",
                "virality_score": 93,
                "platform": "TikTok",
            },

            {
                "topic": "luxury shower selfcare routine",
                "category": "selfcare",
                "virality_score": 94,
                "platform": "Instagram Reels",
            },

        ]

    def get_trending_topics(
        self,
        limit=10
    ):

        trends = sorted(
            self.base_trends,
            key=lambda x: x["virality_score"],
            reverse=True
        )

        return trends[:limit]

    def get_random_trend(self):

        return random.choice(
            self.base_trends
        )

    def get_best_trend(self):

        trends = self.get_trending_topics(
            limit=5
        )

        return random.choice(
            trends
        )

    def generate_trend_report(self):

        trends = self.get_trending_topics()

        report = {
            "generated_at": str(datetime.now()),
            "total_trends": len(trends),
            "top_platforms": [
                "TikTok",
                "Instagram Reels",
                "YouTube Shorts",
            ],
            "trends": trends,
        }

        return report

    def print_report(self):

        report = self.generate_trend_report()

        print("\n" + "=" * 60)
        print("TREND RESEARCH REPORT")
        print("=" * 60)

        print(
            f"Generated: "
            f"{report['generated_at']}"
        )

        print(
            f"Trend count: "
            f"{report['total_trends']}"
        )

        print("\nTOP TRENDS:\n")

        for trend in report["trends"]:

            print(
                f"- {trend['topic']} "
                f"| Score: {trend['virality_score']} "
                f"| Platform: {trend['platform']}"
            )


if __name__ == "__main__":

    engine = TrendResearchEngine()

    engine.print_report()