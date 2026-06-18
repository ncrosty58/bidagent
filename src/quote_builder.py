"""
Quote builder — takes requested services, price book, and vision analysis
from the LLM, then constructs an itemized quote with job descriptions.
"""

import base64
import json
import logging

from openai import OpenAI

from src.config import settings

logger = logging.getLogger("bidagent.quote")


async def build_quote(
    services_list: list[str],
    price_book: list[dict],
    image_buffers: list[dict],
    skill_def: dict,
) -> dict:
    if not settings.openai_api_key:
        return _flat_quote_fallback(services_list, price_book)

    pricing_json = json.dumps(price_book, indent=2, default=str)
    services_json = json.dumps(services_list)
    system_prompt = _quote_prompt(services_json, pricing_json, skill_def)

    content_parts = [
        {"type": "text", "text": "Analyze these property photos and produce an estimate."},
    ]
    for buf in image_buffers:
        b64 = base64.b64encode(buf["data"]).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "auto"},
        })

    try:
        client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        response = client.chat.completions.create(
            model=settings.llm_model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content_parts},
            ],
            max_tokens=2000,
            temperature=0.2,
        )
        raw = response.choices[0].message.content or ""
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
        return result
    except Exception as e:
        logger.error("LLM quote generation failed: %s", e)
        return _flat_quote_fallback(services_list, price_book)


def _quote_prompt(services_json: str, pricing_json: str, skill_def: dict) -> str:
    prompts = skill_def.get("prompts", {})
    custom_system = prompts.get("system", "")
    return f"""
{custom_system}

Requested services:
{services_json}

Available pricing data:
{pricing_json}

For each requested service, determine the most appropriate bracket based on
the property photos (driveway size, house height, bed area, etc.).

If a service must be flat-rate, apply the flat rate. If no brackets can be
determined, pick the middle option.

For each line item, generate a concise (1-2 sentence) job description
based on the photos -- what needs to be done and why it is priced
at that bracket. This becomes part of a CRM note.

Respond with ONLY a JSON object:
{{
  "itemized_quote": [
    {{"service": "concrete_clean", "bracket": "medium_4_car", "label": "Driveway & Concrete Deep Clean", "description": "Medium 4-car driveway with light staining.", "price_low": 250, "price_high": 350}}
  ],
  "description": "Concise 2-3 sentence overall job summary based on the photos, what work is needed, and estimated price range.",
  "total_low": 1000,
  "total_high": 1500,
  "warnings": [],
  "rejection": null
}}

If you cannot estimate any of the requested services, return rejection with an explanation.
"""


def _flat_quote_fallback(services_list: list[str], price_book: list[dict]) -> dict:
    items = []
    total_low = 0
    total_high = 0

    for svc_name in services_list:
        pricing = next((p for p in price_book if p["name"] == svc_name), None)
        if not pricing:
            items.append({"service": svc_name, "error": "No pricing data found"})
            continue

        if "flat_rate" in pricing:
            fr = pricing["flat_rate"]
            items.append({
                "service": svc_name,
                "label": pricing.get("display", svc_name),
                "flat_rate": True,
                "price_low": fr["low"],
                "price_high": fr["high"],
                "description": f'Standard flat-rate pricing for {pricing.get("display", svc_name)}.'
            })
            total_low += fr["low"]
            total_high += fr["high"]
        elif "brackets" in pricing:
            brackets = pricing["brackets"]
            mid = brackets[len(brackets) // 2]
            items.append({
                "service": svc_name,
                "label": pricing.get("display", svc_name),
                "bracket": mid.get("name", "standard"),
                "price_low": mid["low"],
                "price_high": mid["high"],
                "description": f'Classified at {mid.get("label", "standard")} bracket.'
            })
            total_low += mid["low"]
            total_high += mid["high"]
        else:
            items.append({"service": svc_name, "error": "No bracket or flat rate data"})

    # Build overall description for CRM note
    svc_names = ", ".join(i.get("label", i.get("service", "")) for i in items if "error" not in i)
    description = f"Auto-estimate for {len(items)} service(s): {svc_names}. Estimated range ${total_low}-${total_high}."

    return {
        "itemized_quote": items,
        "description": description,
        "total_low": total_low,
        "total_high": total_high,
        "warnings": ["AI analysis unavailable -- used default brackets."],
        "rejection": None,
    }
