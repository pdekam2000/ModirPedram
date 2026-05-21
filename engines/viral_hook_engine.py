import random


class ViralHookEngine:
    def __init__(self):
        self.hook_templates = [

            "Your skin looks tired because you're missing THIS...",

            "Try this tonight and thank yourself tomorrow...",

            "Most girls use this ingredient WRONG...",

            "This simple trick can completely change your skin...",

            "Stop buying expensive skincare before trying this...",

            "Your glow routine is missing this step...",

            "This beauty secret went viral for a reason...",

            "Do this before sleep for softer glowing skin...",

            "The internet is obsessed with this skincare trick...",

            "This homemade mask works better than you think..."
        ]

        self.thumbnail_templates = [

            "GLOW OVERNIGHT",
            "TRY THIS TONIGHT",
            "SECRET SKIN HACK",
            "STOP DOING THIS",
            "SOFT SKIN SECRET",
            "YOUR SKIN NEEDS THIS",
            "VIRAL BEAUTY SECRET",
            "NATURAL GLOW",
            "BETTER THAN EXPENSIVE SKINCARE"
        ]

        self.caption_templates = [

            "Save this for your next selfcare night ✨",

            "Which one are you trying first? 👀",

            "This routine feels unreal at night 🌙",

            "Girls are loving this simple glow routine 💖",

            "Your future skin will thank you ✨",

            "This selfcare trick is everywhere right now 👀",

            "Perfect for your next selfcare evening 🕯️",

            "Soft skin energy only ✨"
        ]

    def generate_hook(self, topic):
        template = random.choice(self.hook_templates)

        return {
            "hook": template,
            "topic": topic
        }

    def generate_thumbnail_text(self):
        return random.choice(self.thumbnail_templates)

    def generate_caption_hook(self):
        return random.choice(self.caption_templates)

    def generate_full_package(self, topic):
        return {
            "hook": self.generate_hook(topic)["hook"],
            "thumbnail_text": self.generate_thumbnail_text(),
            "caption_hook": self.generate_caption_hook()
        }


if __name__ == "__main__":
    engine = ViralHookEngine()

    topic = "yogurt honey oat glow mask"

    result = engine.generate_full_package(topic)

    print("\n=== VIRAL PACKAGE ===\n")

    print("HOOK:")
    print(result["hook"])

    print("\nTHUMBNAIL:")
    print(result["thumbnail_text"])

    print("\nCAPTION:")
    print(result["caption_hook"])