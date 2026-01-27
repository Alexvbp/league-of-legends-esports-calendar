#!/usr/bin/env python3
"""
Esports Match Calendar Generator

Scrapes match data from Liquipedia for configured teams and generates
ICS calendar, RSS, and JSON feeds. Deploys via GitHub Pages.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src import Match, TeamConfig
from src.cache import load_cached_calendar, save_to_cache, validate_ics
from src.calendar_gen import create_team_calendar
from src.feeds import generate_json_feed, generate_rss_feed
from src.html_gen import generate_index_html
from src.notify import send_error_notification
from src.scraper import fetch_team_matches


def load_teams(path: str = "teams.json") -> list[TeamConfig]:
    """Load team configurations from JSON file."""
    with open(path) as f:
        data = json.load(f)
    return [TeamConfig(**t) for t in data["teams"]]


def match_to_dict(m: Match) -> dict:
    """Convert a Match to a JSON-serializable dict for the HTML template."""
    return {
        "timestamp": m.timestamp,
        "opponent": m.opponent,
        "tournament": m.tournament,
        "url": m.url,
        "is_upcoming": m.is_upcoming,
    }


def main() -> int:
    teams = load_teams()
    output_dir = Path("public")
    output_dir.mkdir(exist_ok=True)
    cache_dir = Path("cache")
    cache_dir.mkdir(exist_ok=True)

    all_team_data: dict = {}
    errors: list[str] = []
    base_url = ""  # Populated at runtime by JS; feeds use relative paths

    for team in teams:
        print(f"\n{team.emoji} Fetching {team.name} matches from Liquipedia...")

        try:
            matches = fetch_team_matches(team)
            upcoming = [m for m in matches if m.is_upcoming]
            past = [m for m in matches if not m.is_upcoming]
            print(f"  Found {len(upcoming)} upcoming, {len(past)} past matches")

            if not upcoming and not past:
                print("  Warning: no matches found (page structure may have changed)")

            # Generate ICS
            cal = create_team_calendar(team, matches)
            ics_bytes = cal.to_ical()

            # Validate before saving
            if not validate_ics(ics_bytes):
                raise ValueError("Generated ICS failed validation")

            ics_path = output_dir / f"{team.slug.lower()}.ics"
            ics_path.write_bytes(ics_bytes)
            print(f"  Saved {ics_path}")

            # Cache the successful result
            save_to_cache(cache_dir, team.slug, ics_bytes)

            # Generate RSS feed
            rss = generate_rss_feed(team, matches, base_url)
            rss_path = output_dir / f"{team.slug.lower()}.xml"
            rss_path.write_text(rss, encoding="utf-8")
            print(f"  Saved {rss_path}")

            # Generate JSON feed
            json_feed = generate_json_feed(team, matches, base_url)
            json_path = output_dir / f"{team.slug.lower()}.json"
            json_path.write_text(json.dumps(json_feed, indent=2), encoding="utf-8")
            print(f"  Saved {json_path}")

            # Collect data for HTML
            all_team_data[team.slug] = {
                "config": {
                    "name": team.name,
                    "short_name": team.short_name,
                    "emoji": team.emoji,
                    "slug": team.slug,
                    "game": team.game,
                },
                "upcoming": [match_to_dict(m) for m in upcoming],
                "past": [match_to_dict(m) for m in past],
            }

            for m in upcoming:
                from datetime import datetime, timezone

                dt = datetime.fromtimestamp(m.timestamp, tz=timezone.utc)
                print(f"    {dt.strftime('%Y-%m-%d %H:%M UTC')} vs {m.opponent}")

        except Exception as e:
            error_msg = f"Failed to fetch {team.name}: {e}"
            print(f"  ERROR: {error_msg}")
            errors.append(error_msg)

            # Try cache fallback
            cached = load_cached_calendar(cache_dir, team.slug)
            if cached:
                print(f"  Using cached calendar for {team.name}")
                ics_path = output_dir / f"{team.slug.lower()}.ics"
                ics_path.write_bytes(cached)

                all_team_data[team.slug] = {
                    "config": {
                        "name": team.name,
                        "short_name": team.short_name,
                        "emoji": team.emoji,
                        "slug": team.slug,
                        "game": team.game,
                    },
                    "upcoming": [],
                    "past": [],
                    "cached": True,
                }
            else:
                send_error_notification(
                    f"{error_msg}\n\nNo cached data available — calendar will be empty."
                )

    # Generate index HTML
    html = generate_index_html(all_team_data)
    html_path = output_dir / "index.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"\nSaved {html_path}")

    # Summary
    print(f"\nGenerated feeds for {len(all_team_data)} team(s)")
    if errors:
        print(f"Errors encountered: {len(errors)}")
        for err in errors:
            print(f"  - {err}")
        send_error_notification(
            f"Calendar generation completed with {len(errors)} error(s):\n\n"
            + "\n".join(f"- {e}" for e in errors)
        )
        return 1

    print("Done — all feeds generated successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
