# ============================================================
# core/utils.py -- Shared Utility Functions
# ============================================================
# Common helpers used across all analyzer and scoring modules.
# Centralised here to avoid duplication and ensure consistency.
# ============================================================

import json
import re


def safe_get(info: dict, key: str, default=None, cast=float):
    """
    Safely retrieves a value from a dict and casts it.
    Returns default if key is missing, None, or cast fails.

    Args:
        info    : Source dict (typically yfinance .info)
        key     : Key to retrieve
        default : Value to return on failure
        cast    : Type to cast to (float, int, str, etc.)
    """
    try:
        val = info.get(key)
        if val is None:
            return default
        return cast(val)
    except Exception:
        return default


def safe_json_loads(s: str, default=None):
    """
    Robust JSON parser that handles common GPT output issues:
      - Markdown code fences (```json ... ```)
      - Single-quoted keys/values (not apostrophes in content)
      - Trailing commas before } or ]
      - Leading/trailing whitespace

    Returns default ({} or []) if all parsing attempts fail.
    """
    if default is None:
        default = {}

    if not s or not isinstance(s, str):
        return default

    # Attempt 1: direct parse (handles well-formed JSON)
    try:
        return json.loads(s)
    except Exception:
        pass

    # Clean up common GPT formatting issues
    cleaned = s.strip()

    # Remove markdown fences
    if cleaned.startswith("```"):
        parts   = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    # Remove trailing commas before } or ]
    cleaned = re.sub(r",\s*}", "}", cleaned)
    cleaned = re.sub(r",\s*]", "]", cleaned)

    # Attempt 2: parse after fence/comma cleanup (no quote replacement)
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Attempt 3: replace single-quoted keys only (not apostrophes in values)
    # This regex targets 'key': patterns while leaving content apostrophes alone
    try:
        # Replace 'key' patterns → "key"
        fixed = re.sub(r"'([^']*?)'(\s*:)", r'"\1"\2', cleaned)
        # Replace : 'value' patterns → : "value"
        fixed = re.sub(r"(:\s*)'([^']*?)'", r'\1"\2"', fixed)
        return json.loads(fixed)
    except Exception:
        return default
