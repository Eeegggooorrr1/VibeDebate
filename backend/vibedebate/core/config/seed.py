from pathlib import Path
from .base import EnvSettings


class SeedSettings(EnvSettings):
    seed_dir: Path = Path(__file__).resolve().parents[2] / "seed"

def create_seed_settings() -> SeedSettings:
    return SeedSettings()
