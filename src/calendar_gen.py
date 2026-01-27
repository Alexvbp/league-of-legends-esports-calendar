"""ICS calendar generation from match data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from icalendar import Alarm, Calendar, Event

from src import Match, TeamConfig


def create_team_calendar(team: TeamConfig, matches: list[Match]) -> Calendar:
    """Create an ICS calendar for a team's matches."""
    cal = Calendar()
    cal.add("prodid", f"-//{team.name} Match Calendar//liquipedia.net//")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", f"{team.name} Matches")
    cal.add("x-wr-timezone", "Europe/Amsterdam")
    # Refresh interval hint for calendar clients (4 hours)
    cal.add("x-published-ttl", "PT4H")

    for match in matches:
        event = _create_event(team, match)
        cal.add_component(event)

    return cal


def _create_event(team: TeamConfig, match: Match) -> Event:
    """Create a calendar event from a match."""
    event = Event()
    dt = datetime.fromtimestamp(match.timestamp, tz=timezone.utc)

    summary = f"{team.emoji} {team.short_name} vs {match.opponent}"
    event.add("summary", summary)
    event.add("dtstart", dt)
    event.add("dtend", dt + timedelta(hours=2))

    description = f"Tournament: {match.tournament}"
    if match.url:
        description += f"\n\nMore info: {match.url}"
    if not match.is_upcoming:
        description += "\n\n(Completed match — no spoilers)"
    event.add("description", description)

    if match.url:
        event.add("url", match.url)

    # Stable UID based on timestamp + opponent + team
    uid = (
        f"{team.slug.lower()}-{match.timestamp}-"
        f"{match.opponent.replace(' ', '-').replace('_', '-').lower()}"
        f"@liquipedia.net"
    )
    event.add("uid", uid)

    # Only add alarm for upcoming matches
    if match.is_upcoming:
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add(
            "description",
            f"{team.name} vs {match.opponent} starts in 30 minutes!",
        )
        alarm.add("trigger", timedelta(minutes=-30))
        event.add_component(alarm)

    # Status
    if match.is_upcoming:
        event.add("status", "CONFIRMED")
    else:
        event.add("status", "CONFIRMED")
        event.add("transp", "TRANSPARENT")  # Don't block time for past matches

    return event
