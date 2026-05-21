import random


class TrendEngine:

    def __init__(self):

        self.default_topics = [

            "luxury skincare routine",
            "glass skin secrets",
            "night skincare routine",
            "morning beauty ritual",
            "soft glow skincare",
            "acne healing routine",
            "dark circle removal",
            "korean skincare secrets",
            "clean girl beauty routine",
            "viral glow up routine",
        ]

        self.viral_hooks = [

            "Stop buying expensive skincare before trying this...",
            "Your skin looks tired because you're missing THIS...",
            "This beauty trick changed everything...",
            "Do this before sleep for glowing skin...",
            "Your future skin will thank you...",
            "The skincare secret nobody talks about...",
        ]

        self.thumbnail_texts = [

            "VIRAL BEAUTY SECRET",
            "GLOW UP FAST",
            "SKINCARE HACK",
            "LUXURY SKIN ROUTINE",
            "SOFT SKIN ENERGY",
        ]

        self.caption_hooks = [

            "Soft skin energy only ✨",
            "Your future self will thank you 💫",
            "Luxury skincare vibes only 🌸",
            "Glow different ✨",
            "Main character skincare energy 💕",
        ]

    def generate_topic(self, custom_topic=None):

        if custom_topic and custom_topic.strip():

            return {
                "title": custom_topic.title(),
                "topic": custom_topic,
                "ingredients": [
                    {
                        "name": "Skincare Step",
                        "amount": "1 routine",
                    },
                    {
                        "name": "Clean Skin",
                        "amount": "1 base",
                    }
                ]
            }

        topic = random.choice(
            self.default_topics
        )

        return {
            "title": topic.title(),
            "topic": topic,
            "ingredients": [
                {
                    "name": "Hydrating Serum",
                    "amount": "2 drops",
                },
                {
                    "name": "Glow Cream",
                    "amount": "1 layer",
                }
            ]
        }

    def generate_viral_package(self):

        return {

            "hook": random.choice(
                self.viral_hooks
            ),

            "thumbnail": random.choice(
                self.thumbnail_texts
            ),

            "caption_hook": random.choice(
                self.caption_hooks
            ),
        }