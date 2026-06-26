"""
Centralized settings — loaded once, imported everywhere.
"""

import logging
from pathlib import Path

from pydantic_settings import BaseSettings

logger = logging.getLogger("bidagent")


class Settings(BaseSettings):
    port: int = 8000
    openai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    openai_api_key: str = ""
    llm_model_name: str = "gemini-2.5-flash"
    active_skill: str = "curbclass"
    pricebook_url: str = ""

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent / "config" / ".env"),
        "extra": "ignore",
    }


settings = Settings()  # type: ignore[call-arg]
