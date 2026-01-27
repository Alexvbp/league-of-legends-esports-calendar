"""Caching for fallback on scrape failures (ICS and JSON data)."""

from __future__ import annotations

from pathlib import Path


# --- ICS cache (legacy / local dev) ---


def save_to_cache(cache_dir: Path, team_slug: str, ics_data: bytes) -> None:
    """Save ICS data to cache directory."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{team_slug.lower()}.ics"
    cache_file.write_bytes(ics_data)


def load_cached_calendar(cache_dir: Path, team_slug: str) -> bytes | None:
    """Load cached ICS data for a team. Returns None if no cache exists."""
    cache_file = cache_dir / f"{team_slug.lower()}.ics"
    if cache_file.exists():
        return cache_file.read_bytes()
    return None


def validate_ics(data: bytes) -> bool:
    """Basic validation that ICS data is well-formed."""
    text = data.decode("utf-8", errors="replace")
    return text.startswith("BEGIN:VCALENDAR") and "END:VCALENDAR" in text


# --- JSON data cache ---


def save_json_cache(cache_dir: Path, team_slug: str, json_str: str) -> None:
    """Save JSON data string to cache directory."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{team_slug.lower()}.json"
    cache_file.write_text(json_str, encoding="utf-8")


def load_json_cache(cache_dir: Path, team_slug: str) -> str | None:
    """Load cached JSON data for a team. Returns None if no cache exists."""
    cache_file = cache_dir / f"{team_slug.lower()}.json"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    return None
