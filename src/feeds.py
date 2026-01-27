"""RSS (Atom) and JSON feed generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src import Match, TeamConfig


def generate_rss_feed(team: TeamConfig, matches: list[Match], base_url: str = "") -> str:
    """Generate an Atom RSS feed for a team's matches."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    entries = ""
    for match in sorted(matches, key=lambda m: m.timestamp, reverse=True):
        dt = datetime.fromtimestamp(match.timestamp, tz=timezone.utc)
        date_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        status = "Upcoming" if match.is_upcoming else "Completed"
        title = _xml_escape(f"{team.emoji} {team.short_name} vs {match.opponent}")
        tournament = _xml_escape(match.tournament)

        entry_id = f"{team.slug.lower()}-{match.timestamp}-{match.opponent.replace(' ', '-').lower()}"

        entries += f"""  <entry>
    <id>urn:esports-calendar:{entry_id}</id>
    <title>{title}</title>
    <updated>{date_str}</updated>
    <summary>{status} — {tournament}</summary>
    <link href="{_xml_escape(match.url)}" rel="alternate"/>
    <category term="{status.lower()}"/>
  </entry>
"""

    feed_url = f"{base_url}/{team.slug.lower()}.xml" if base_url else ""
    ics_url = f"{base_url}/{team.slug.lower()}.ics" if base_url else ""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:esports-calendar:{team.slug.lower()}</id>
  <title>{_xml_escape(team.name)} Match Schedule</title>
  <subtitle>Upcoming and recent matches for {_xml_escape(team.name)}</subtitle>
  <updated>{now}</updated>
  <link href="{feed_url}" rel="self" type="application/atom+xml"/>
  <link href="{ics_url}" rel="alternate" type="text/calendar"/>
  <generator>esports-calendar</generator>
{entries}</feed>
"""


def generate_json_feed(team: TeamConfig, matches: list[Match], base_url: str = "") -> dict:
    """Generate a JSON Feed (v1.1) for a team's matches."""
    items = []
    for match in sorted(matches, key=lambda m: m.timestamp, reverse=True):
        dt = datetime.fromtimestamp(match.timestamp, tz=timezone.utc)
        items.append({
            "id": f"{team.slug.lower()}-{match.timestamp}-{match.opponent.replace(' ', '-').lower()}",
            "title": f"{team.emoji} {team.short_name} vs {match.opponent}",
            "date_published": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "url": match.url or team.liquipedia_url,
            "tags": ["upcoming" if match.is_upcoming else "completed", match.tournament],
            "content_text": f"{'Upcoming' if match.is_upcoming else 'Completed'} — {match.tournament}",
        })

    return {
        "version": "https://jsonfeed.org/version/1.1",
        "title": f"{team.name} Match Schedule",
        "home_page_url": base_url or team.liquipedia_url,
        "feed_url": f"{base_url}/{team.slug.lower()}.json" if base_url else "",
        "description": f"Upcoming and recent matches for {team.name}",
        "items": items,
    }


def _xml_escape(text: str) -> str:
    """Escape text for safe inclusion in XML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
