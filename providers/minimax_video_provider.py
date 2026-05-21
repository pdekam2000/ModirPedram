import os
from dotenv import load_dotenv


class MiniMaxVideoProvider:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("MINIMAX_API_KEY")

    def validate(self):
        if not self.api_key:
            raise RuntimeError(
                "MINIMAX_API_KEY is missing from .env"
            )

    def generate_clips(self, prompts):
        self.validate()

        print("\n[MiniMax] MiniMax API selected.")
        print("[MiniMax] API routing is ready.")
        print("[MiniMax] Real video generation endpoint is not connected yet.")

        raise NotImplementedError(
            "MiniMax API video generation is not implemented yet. "
            "Router is ready; next step is connecting the real MiniMax endpoint."
        )