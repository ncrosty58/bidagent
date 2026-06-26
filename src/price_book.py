"""
Price book — fetches live pricing through Node-RED, which proxies from Twenty CRM.
BidAgent never calls CRM directly. All CRM interaction goes through Node-RED.

BidAgent combines CRM service records (names, descriptions, basePrice hints)
with the structural pricing (brackets, flat_rates) defined in the YAML skill file.
Node-RED proxies the CRM query; YAML provides the pricing structure.
"""

import logging
import re
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger("bidagent.price")

NODERED_PRICEBOOK_URL = settings.pricebook_url


def _parse_base_price(base_price_str: str) -> float | None:
    if not base_price_str:
        return None
    match = re.search(r'\d+', base_price_str.replace(',', ''))
    if match:
        return float(match.group(0))
    return None


async def load_or_fetch_price_book(skill_def: dict) -> list[dict]:
    """
    Returns a combined price book. Node-RED is called first to proxy CRM services,
    then enriched with YAML bracket/flat_rate pricing. Falls back to YAML-only
    if Node-RED is unavailable or returns empty.
    """
    yaml_services = skill_def.get("services", {})
    book = None

    if NODERED_PRICEBOOK_URL:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(NODERED_PRICEBOOK_URL)
                resp.raise_for_status()
                data = resp.json()

            crm_services = data.get("data", {}).get("services", [])
            if not crm_services:
                logger.warning("CRM pricebook returned empty services — using YAML")
            else:
                book = _merge_crm_with_yaml(crm_services, yaml_services)
                logger.info("Price book: %d services via pricebook URL", len(book))
        except Exception as e:
            logger.warning("Pricebook fetch failed (%s) — using YAML", e)

    if book is None:
        book = _yaml_to_book(yaml_services)

    return book


def _merge_crm_with_yaml(crm_services: list[dict], yaml_services: dict) -> list[dict]:
    """Merge CRM service records with YAML pricing brackets/flat rates."""
    book = []
    for svc in crm_services:
        name = svc.get("name", "unknown")
        yml = yaml_services.get(name, {})
        entry = {
            "name": name,
            "display": yml.get("display", name),
            "category": yml.get("category", svc.get("category", "")),
            "description": svc.get("description", ""),
            "basePrice": svc.get("basePrice", ""),
        }
        if "flat_rate" in yml:
            entry["flat_rate"] = yml["flat_rate"]
        elif "brackets" in yml:
            entry["brackets"] = yml["brackets"]
        else:
            parsed = _parse_base_price(svc.get("basePrice", ""))
            if parsed is not None:
                entry["flat_rate"] = {"low": parsed, "high": parsed}

        book.append(entry)
    return book


def _yaml_to_book(yaml_services: dict) -> list[dict]:
    """Pure YAML price book (no CRM connection)."""
    book = []
    for name, svc in yaml_services.items():
        entry = {"name": name, "display": svc.get("display", name)}
        if "flat_rate" in svc:
            entry["flat_rate"] = svc["flat_rate"]
        elif "brackets" in svc:
            entry["brackets"] = svc["brackets"]
        book.append(entry)
    return book
