"""Platform string normalization utilities.

We standardize on dashed ESP32 variants (e.g., esp32-c3, esp32-s3) while
accepting historical formats like esp32c3 or esp32_s3.
"""

from __future__ import annotations

import re
from typing import Iterable


_ESP32_PREFIX_RE = re.compile(r"^esp32([\-_]?[a-z0-9]+)?$", re.IGNORECASE)


def normalize_platform(platform: str | None) -> str | None:
    """Normalize platform strings to a canonical form.

    Canonical rules:
    - lowercase + stripped
    - esp32 variants use a dash: esp32-c3, esp32-s2, esp32-s3, esp32-c6, ...
    - esp8266 remains esp8266

    Returns None if input is None or empty/whitespace.
    """
    if platform is None:
        return None
    value = platform.strip().lower()
    if not value:
        return None

    match = _ESP32_PREFIX_RE.match(value)
    if not match:
        return value

    # group(1) includes optional separator + suffix
    suffix = match.group(1)
    if not suffix:
        return "esp32"

    normalized_suffix = suffix.lstrip("-_")
    if not normalized_suffix:
        return "esp32"

    return f"esp32-{normalized_suffix}"


def platform_variants(platform: str | None) -> list[str]:
    """Return acceptable variants for matching against existing DB values."""
    normalized = normalize_platform(platform)
    if not normalized:
        return []

    variants: list[str] = [normalized]

    if normalized.startswith("esp32-"):
        suffix = normalized.removeprefix("esp32-")
        variants.extend([f"esp32{suffix}", f"esp32_{suffix}"])

    # De-dup while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def first_non_empty(values: Iterable[str | None]) -> str | None:
    for v in values:
        if v is None:
            continue
        vv = v.strip()
        if vv:
            return vv
    return None
