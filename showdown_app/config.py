import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TierConfig:
    slug: str
    label: str
    plain_name: str
    explanation: str


TIERS = {
    "gen9ou": TierConfig(
        slug="gen9ou",
        label="Gen 9 OU",
        plain_name="Standard format",
        explanation=(
            "OU (OverUsed) is the main standard singles format. It allows a broad "
            "pool of commonly used Pokémon while excluding the most powerful outliers."
        ),
    ),
    "gen9uu": TierConfig(
        slug="gen9uu",
        label="Gen 9 UU",
        plain_name="Lower-usage format",
        explanation=(
            "UU (UnderUsed) is built around Pokémon that do not meet the usage cutoff "
            "for OU, producing a different competitive environment."
        ),
    ),
    "gen9ubers": TierConfig(
        slug="gen9ubers",
        label="Gen 9 Ubers",
        plain_name="High-power format",
        explanation=(
            "Ubers permits many exceptionally powerful Pokémon that are not allowed "
            "in OU, so its teams and matchups look very different."
        ),
    ),
}

RELEASE_REPOSITORY = os.getenv(
    "SHOWDOWN_RELEASE_REPOSITORY", "jonnboi13/Showdown-project"
)
RELEASE_TAG = os.getenv("SHOWDOWN_RELEASE_TAG", "v1.0.0")
RELEASE_API_URL = (
    f"https://api.github.com/repos/{RELEASE_REPOSITORY}/releases/tags/{RELEASE_TAG}"
)

DEFAULT_TIER = "gen9ou"
DEFAULT_MIN_RATING = 1500

_default_cache_root = Path(tempfile.gettempdir()) / "showdown-meta-lab-cache"
CACHE_ROOT = Path(os.getenv("SHOWDOWN_CACHE_DIR", str(_default_cache_root)))
