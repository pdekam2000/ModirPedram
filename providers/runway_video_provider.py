import os
import time
import requests
from pathlib import Path

from dotenv import load_dotenv


class RunwayVideoProvider:

    def __init__(self):
        load_dotenv()

        self.api_key = os.getenv("RUNWAY_API_KEY")

        if not self.api_key:
            raise RuntimeError("RUNWAY_API_KEY not found in .env")

        self.base_url = "https://api.dev.runwayml.com/v1"

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Runway-Version": os.getenv(
                "RUNWAY_API_VERSION",
                "2024-11-06"
            ),
            "Content-Type": "application/json",
        }

        self.model = os.getenv("RUNWAY_VIDEO_MODEL", "gen4.5")
        self.ratio = os.getenv("RUNWAY_VIDEO_RATIO", "1280:720")
        self.duration = int(os.getenv("RUNWAY_VIDEO_DURATION", "5"))

        self.poll_interval = int(os.getenv("RUNWAY_POLL_INTERVAL", "10"))
        self.max_attempts = int(os.getenv("RUNWAY_MAX_ATTEMPTS", "60"))
        self.max_prompt_chars = int(os.getenv("RUNWAY_MAX_PROMPT_CHARS", "950"))

        self.output_dir = Path("downloads") / "runway"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def clean_prompt(self, prompt):
        text = str(prompt).strip()
        text = " ".join(text.split())

        if len(text) <= self.max_prompt_chars:
            return text

        cut = text[:self.max_prompt_chars]
        split_at = max(cut.rfind("."), cut.rfind(","))

        if split_at > 300:
            cut = cut[:split_at + 1]

        print(f"[Runway] Prompt shortened: {len(text)} -> {len(cut)} chars")
        return cut.strip()

    def generate_single_clip(self, prompt, index):
        prompt_text = self.clean_prompt(prompt)

        output_path = self.output_dir / f"runway_clip_{int(time.time())}_{index}.mp4"

        endpoint = f"{self.base_url}/text_to_video"

        payload = {
            "model": self.model,
            "promptText": prompt_text,
            "ratio": self.ratio,
            "duration": self.duration,
        }

        print("\n" + "=" * 60)
        print(f"[Runway] GENERATING CLIP {index}")
        print("=" * 60)
        print(f"[Runway] Model: {self.model}")
        print(f"[Runway] Ratio: {self.ratio}")
        print(f"[Runway] Duration: {self.duration}")
        print(f"[Runway] Prompt chars: {len(prompt_text)}")
        print("[Runway] Sending REST text_to_video request...")

        response = requests.post(
            endpoint,
            headers=self.headers,
            json=payload,
            timeout=120,
        )

        if response.status_code not in [200, 201]:
            raise RuntimeError(
                f"Runway API Error: {response.status_code} {response.text}"
            )

        task_data = response.json()
        task_id = task_data.get("id")

        if not task_id:
            raise RuntimeError(f"Runway task id missing: {task_data}")

        print(f"[Runway] Task created: {task_id}")

        return self.wait_for_task(task_id, output_path)

    def wait_for_task(self, task_id, output_path):
        task_url = f"{self.base_url}/tasks/{task_id}"

        for attempt in range(1, self.max_attempts + 1):
            response = requests.get(
                task_url,
                headers=self.headers,
                timeout=60,
            )

            if response.status_code != 200:
                raise RuntimeError(
                    f"Runway polling failed: {response.status_code} {response.text}"
                )

            data = response.json()
            status = data.get("status")

            print(f"[Runway] Status: {status} ({attempt}/{self.max_attempts})")

            if status == "SUCCEEDED":
                output = data.get("output", [])

                if not output:
                    raise RuntimeError(f"No Runway output URL returned: {data}")

                video_url = output[0]
                return self.download_video(video_url, output_path)

            if status in ["FAILED", "CANCELLED"]:
                raise RuntimeError(f"Runway task failed: {data}")

            time.sleep(self.poll_interval)

        raise TimeoutError(f"Timeout waiting for Runway task: {task_id}")

    def download_video(self, video_url, output_path):
        print("[Runway] Downloading video...")

        response = requests.get(
            video_url,
            stream=True,
            allow_redirects=True,
            timeout=300,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "video/mp4,*/*",
            },
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to download Runway video: {response.status_code} {response.text}"
            )

        total_bytes = 0

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    total_bytes += len(chunk)

        print(f"[Runway] Saved: {output_path}")
        print(f"[Runway] Downloaded bytes: {total_bytes}")

        return str(output_path)

    def generate_clips(self, prompts):
        print("\n[Runway] Runway REST API selected.")
        print("[Runway] Real generation started.")

        downloaded_files = []

        for index, prompt in enumerate(prompts, start=1):
            file_path = self.generate_single_clip(prompt, index)
            downloaded_files.append(file_path)

        print("[Runway] All clips generated.")
        return downloaded_files