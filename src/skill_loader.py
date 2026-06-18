"""
Skill loader — loads external YAML skill configs that define per-contractor
rules, service catalogues, pricing brackets, image validation rules, and
AI prompt templates.
"""

import logging
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

logger = logging.getLogger("bidagent.skill")

yaml = YAML(typ="safe")


DEFAULT_SKILL_DIR = Path(__file__).resolve().parent.parent / "skills"


def load_skill(skill_path: str | Path) -> dict[str, Any]:
    """Load a skill YAML file. Returns the parsed dict or a minimal fallback."""
    path = Path(skill_path)
    if not path.exists():
        logger.warning("Skill file not found: %s — using built-in defaults", path)
        return _default_skill()

    with open(path) as f:
        skill = yaml.load(f)

    if not isinstance(skill, dict):
        logger.warning("Skill file %s is empty/invalid — using defaults", path)
        return _default_skill()

    logger.info("Loaded skill: %s (version %s)", skill.get("name", "?"), skill.get("version", "?"))
    return skill


def _default_skill() -> dict:
    """Fallback when no skill file is found."""
    return {
        "name": "default",
        "version": "0.1",
        "description": "Fallback skill — no YAML config loaded.",
        "services": {},
        "image_rules": {
            "min_photos": 1,
            "max_photos": 10,
            "allowed_formats": ["image/jpeg", "image/png", "image/webp"],
            "min_width": 200,
            "min_height": 200,
        },
        "validation": {
            "photo_quality_check": True,
            "content_check": True,
            "climate_check": True,
        },
        "prompts": {
            "system": (
                "You are a BidAgent estimator. Analyze the provided property photos "
                "and classify each requested service into its most appropriate pricing bracket. "
                "Return JSON. Be concise."
            ),
        },
    }
