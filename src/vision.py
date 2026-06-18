"""
Vision analysis — uses an LLM with vision to analyze property photos.
Returns (is_ok: bool, message: str).
"""

import base64
import json
import logging
from typing import Any

from openai import OpenAI

from src.config import settings

logger = logging.getLogger("bidagent.vision")


def _build_client() -> OpenAI:
    base = settings.openai_base_url.rstrip("/")
    if "generativelanguage" in base and not base.endswith("/openai"):
        base += "/openai"
    return OpenAI(api_key=settings.openai_api_key, base_url=base)


async def analyze_images(
    image_buffers: list[dict],
    skill_def: dict,
) -> tuple[bool, str]:
    """
    Check image quality and appropriateness using the LLM.

    Returns (True, "OK") or (False, "rejection message").
    """
    if not settings.openai_api_key:
        logger.warning("No OpenAI API key — skipping vision analysis")
        return True, "Vision API not configured — skipping image validation."

    system_prompt = _build_image_check_prompt(skill_def)

    # Build message content
    content_parts: list[dict] = [
        {"type": "text", "text": system_prompt},
    ]
    for buf in image_buffers:
        b64 = base64.b64encode(buf["data"]).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64}",
                "detail": "auto",
            },
        })

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content_parts},
    ]

    try:
        client = _build_client()
        response = client.chat.completions.create(
            model=settings.llm_model_name,
            messages=messages,
            max_tokens=500,
            temperature=0.1,
        )
        raw = response.choices[0].message.content or ""
        clean = raw.replace("```json", "").replace("```", "").strip()
        start = clean.find('{')
        end = clean.rfind('}')
        if start >= 0 and end > start:
            clean = clean[start:end+1]
        result = json.loads(clean)
    except Exception as e:
        logger.warning("Vision LLM error: %s — allowing through", e)
        return True, "Vision check unavailable — proceeding."

    if not result.get("appropriate", True):
        reason = result.get("reason", "Photos are not appropriate for this estimate.")
        return False, reason

    return True, "OK"


def _build_image_check_prompt(skill_def: dict) -> str:
    """Create the prompt for image validation."""
    rules = skill_def.get("validation", {})
    lines = [
        "You are a BidAgent image validator. Analyze the provided exterior property photos.",
    ]
    if rules.get("photo_quality_check", True):
        lines.append(
            "- Check photo quality: are they clear, well-lit, and usable for estimating? "
            "If blurry, too dark, obstructed, or obviously not a real property, mark as inappropriate."
        )
    if rules.get("content_check", True):
        lines.append(
            "- Check content: are these exterior property photos (house, driveway, yard, entryway)? "
            "If they are unrelated (people, pets, interiors, screenshots, text documents, etc.), mark as inappropriate."
        )
    lines.append(
        "\nRespond with ONLY a JSON object: {\"appropriate\": true/false, \"reason\": \"explanation if not appropriate\"}"
    )
    return "\n".join(lines)
