"""Configuration: .env discovery, model settings, prices, and safety limits.

The .env file is looked up in the repository root first, then one folder above it
(the course requirement). Secrets are never printed or logged.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.getenv("CIVIC_DB_PATH", DATA_DIR / "civic.db"))
USAGE_LOG = Path(os.getenv("CIVIC_USAGE_LOG", DATA_DIR / "usage_log.jsonl"))


def find_env_file(root: Path = ROOT) -> Path | None:
    """Return the .env that will be used: repo root first, then its parent."""
    for folder in (root, root.parent):
        candidate = folder / ".env"
        if candidate.is_file():
            return candidate
    return None


ENV_FILE = find_env_file()
if ENV_FILE:
    load_dotenv(ENV_FILE, override=False)

# --- Model: the course-approved model only, through Portkey -----------------------
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
API_TIMEOUT_SECONDS = 45
REASONING_EFFORT = os.getenv("CIVIC_REASONING_EFFORT", "low")

# USD per 1M tokens (OpenAI Standard, short context), as used in MGT 409 Lecture 11.
# Source: https://developers.openai.com/api/docs/pricing
PRICES_PER_M = {"input": 0.10, "cached": 0.01, "cache_write": 0.125, "output": 0.50}
PRICING_SOURCE = "MGT 409 Lecture 11 price table (OpenAI Standard, short context)"

# --- Limits -----------------------------------------------------------------------
MAX_BODY_BYTES = 20_000          # whole request
MAX_DESCRIPTION_CHARS = 2_000
MAX_OUTCOME_CHARS = 600
MAX_EXTRA_CHARS = 1_000
MAX_NAME_CHARS = 80
MAX_ADDRESS_CHARS = 120
ROUTING_MAX_OUTPUT_TOKENS = 1_200   # includes hidden reasoning tokens
LETTER_MAX_OUTPUT_TOKENS = 2_500
DAILY_BUDGET_USD = float(os.getenv("CIVIC_DAILY_BUDGET_USD", "2.00"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("CIVIC_RATE_LIMIT_PER_MINUTE", "12"))

CATEGORIES = {
    "housing": "Housing / tenants",
    "health": "Healthcare / public health",
    "education": "Education",
    "transportation": "Transportation / infrastructure",
    "environment": "Environment",
    "benefits": "Government benefits",
    "other": "Other",
}


def api_key() -> str | None:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    return key or None
