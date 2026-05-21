import yaml
from pathlib import Path


class ConfigLoader:
    def __init__(self):
        self.config_path = Path(
            "config/config.yaml"
        )

    def load(self):
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Config not found: "
                f"{self.config_path}"
            )

        with open(
            self.config_path,
            "r",
            encoding="utf-8",
        ) as f:
            return yaml.safe_load(f)


if __name__ == "__main__":
    loader = ConfigLoader()

    config = loader.load()

    print("\nCONFIG LOADED\n")

    for section, values in config.items():
        print("=" * 60)
        print(section.upper())
        print(values)