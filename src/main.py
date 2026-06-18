"""
BidAgent: AI-powered instant cost estimating engine.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from src.config import settings
from src.skill_loader import load_skill
from src.price_book import load_or_fetch_price_book
from src.vision import analyze_images
from src.validator import validate_estimate_request
from src.region_check import check_region_consistency
from src.quote_builder import build_quote

logger = logging.getLogger("bidagent")

app = FastAPI(title="BidAgent", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

skill: dict = {}


@app.on_event("startup")
async def startup():
    global skill
    skill_path = Path(__file__).resolve().parent.parent / "skills" / f"{settings.active_skill}.yaml"
    skill = load_skill(str(skill_path))
    logger.info("BidAgent ready | skill=%s | model=%s", settings.active_skill, settings.llm_model_name)


class EstimateResponse(BaseModel):
    status: str
    estimate: Optional[dict] = None
    rejection: Optional[str] = None
    warnings: list[str] = []
    itemized_quote: Optional[list[dict]] = None
    total_low: Optional[float] = None
    total_high: Optional[float] = None


@app.post("/api/v1/estimate", response_model=EstimateResponse)
async def estimate(
    requested_services: str = Form(...),
    zip_code: str = Form(""),
    images: list[UploadFile] = File(default=[]),
    customer_name: str = Form(""),
    customer_email: str = Form(""),
    customer_phone: str = Form(""),
):
    try:
        validate_estimate_request(requested_services, images, skill)
    except ValueError as e:
        logger.warning("Validation failed: %s", e)
        return EstimateResponse(status="rejected", rejection=str(e))

    image_buffers = []
    for img in images:
        data = await img.read()
        image_buffers.append({"filename": img.filename or "photo.jpg", "data": data})

    vision_ok, vision_msg = await analyze_images(image_buffers, skill)
    if not vision_ok:
        logger.warning("Image rejected: %s", vision_msg)
        return EstimateResponse(status="rejected", rejection=vision_msg)

    if zip_code:
        geo_warnings = await check_region_consistency(image_buffers, zip_code, skill)
    else:
        geo_warnings = ["No zip code provided — skipping climate/region check."]

    price_book = await load_or_fetch_price_book(skill)

    services_list = [s.strip() for s in requested_services.split(",")]
    result = await build_quote(services_list, price_book, image_buffers, skill)

    result["warnings"] = geo_warnings + result.get("warnings", [])
    result["status"] = "estimate"

    return EstimateResponse(**result)
