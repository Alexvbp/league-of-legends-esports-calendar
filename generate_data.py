#!/usr/bin/env python3
"""
Esports Calendar — Data Generator

Scrapes match data from Liquipedia for configured teams and outputs
JSON data files to public/data/ for the Cloudflare Pages Function to consume.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from src import Match, TeamConfig
from src.cache import load_json_cache, save_json_cache
from src.notify import send_error_notification
from src.scraper import fetch_team_matches


def load_teams(path: str = "teams.json") -> list[TeamConfig]:
    """Load team configurations from JSON file."""
    with open(path) as f:
        data = json.load(f)
    return [TeamConfig(**t) for t in data["teams"]]


def match_to_dict(m: Match) -> dict:
    """Convert a Match to a JSON-serializable dict."""
    return {
        "timestamp": m.timestamp,
        "opponent": m.opponent,
        "tournament": m.tournament,
        "url": m.url,
        "is_upcoming": m.is_upcoming,
    }


def main() -> int:
    teams = load_teams()
    output_dir = Path("public/data")
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = Path("cache")
    cache_dir.mkdir(exist_ok=True)

    generated_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    team_manifest: list[dict] = []
    errors: list[str] = []

    for team in teams:
        print(f"\n{team.emoji} Fetching {team.name} matches from Liquipedia...")

        try:
            matches = fetch_team_matches(team)
            upcoming = [m for m in matches if m.is_upcoming]
            past = [m for m in matches if not m.is_upcoming]
            print(f"  Found {len(upcoming)} upcoming, {len(past)} past matches")

            if not upcoming and not past:
                print("  Warning: no matches found (page structure may have changed)")
                # Don't overwrite good data with empty data — use cache instead
                cached = load_json_cache(cache_dir, team.slug)
                if cached:
                    print(f"  Using cached data (has matches) instead of empty scrape")
                    out_path = output_dir / f"{team.slug.lower()}.json"
                    out_path.write_text(cached, encoding="utf-8")
                    team_manifest.append({
                        "name": team.name,
                        "slug": team.slug,
                        "short_name": team.short_name,
                        "emoji": team.emoji,
                        "game": team.game,
                    })
                    continue

            team_data = {
                "team": {
                    "name": team.name,
                    "slug": team.slug,
                    "short_name": team.short_name,
                    "emoji": team.emoji,
                    "game": team.game,
                    "liquipedia_url": team.liquipedia_url,
                },
                "matches": [match_to_dict(m) for m in matches],
                "generated_utc": generated_utc,
            }

            json_str = json.dumps(team_data, indent=2, ensure_ascii=False)

            # Save to output
            out_path = output_dir / f"{team.slug.lower()}.json"
            out_path.write_text(json_str, encoding="utf-8")
            print(f"  Saved {out_path}")

            # Cache the successful result
            save_json_cache(cache_dir, team.slug, json_str)

            # Add to manifest
            team_manifest.append({
                "name": team.name,
                "slug": team.slug,
                "short_name": team.short_name,
                "emoji": team.emoji,
                "game": team.game,
            })

            for m in upcoming:
                dt = datetime.fromtimestamp(m.timestamp, tz=timezone.utc)
                print(f"    {dt.strftime('%Y-%m-%d %H:%M UTC')} vs {m.opponent}")

        except Exception as e:
            error_msg = f"Failed to fetch {team.name}: {e}"
            print(f"  ERROR: {error_msg}")
            errors.append(error_msg)

            # Try cache fallback
            cached = load_json_cache(cache_dir, team.slug)
            if cached:
                print(f"  Using cached data for {team.name}")
                out_path = output_dir / f"{team.slug.lower()}.json"
                out_path.write_text(cached, encoding="utf-8")
                # Still add to manifest
                team_manifest.append({
                    "name": team.name,
                    "slug": team.slug,
                    "short_name": team.short_name,
                    "emoji": team.emoji,
                    "game": team.game,
                })
            else:
                send_error_notification(
                    f"{error_msg}\n\nNo cached data available — team will be missing."
                )

    # Write team manifest
    manifest = {
        "teams": team_manifest,
        "generated_utc": generated_utc,
    }
    manifest_path = output_dir / "teams.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSaved {manifest_path} ({len(team_manifest)} teams)")

    # Summary
    if errors:
        print(f"\nErrors encountered: {len(errors)}")
        for err in errors:
            print(f"  - {err}")
        send_error_notification(
            f"Data generation completed with {len(errors)} error(s):\n\n"
            + "\n".join(f"- {e}" for e in errors)
        )
        return 1

    print("\nDone — all data generated successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
