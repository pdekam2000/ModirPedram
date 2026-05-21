import os
from dotenv import load_dotenv

from openai import OpenAI


class OpenAITrendProvider:
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
    ):
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not found in .env"
            )

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate_selfcare_trends(
        self,
        niche: str = "women skincare and selfcare",
        platform: str = "TikTok and Instagram Reels",
        count: int = 5,
    ):
        prompt = f"""
You are a viral short-form content strategist.

Generate {count} trending skincare/selfcare short video ideas.

NICHE:
{niche}

PLATFORM:
{platform}

For each idea provide:
1. Viral title
2. Strong hook
3. One-sentence concept
4. Suggested DIY/selfcare recipe
5. Emotional tone

Focus on:
- highly clickable
- emotionally engaging
- realistic
- aesthetic
- easy to film
- viral skincare/selfcare topics women actually search for

Keep ideas modern and social-media optimized.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert viral beauty and skincare strategist."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.9,
        )

        return response.choices[0].message.content
        