"""Tests for the scraper, calendar generation, and feed output."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src import Match, TeamConfig
from src.cache import save_to_cache, load_cached_calendar, validate_ics
from src.calendar_gen import create_team_calendar
from src.feeds import generate_json_feed, generate_rss_feed
from src.scraper import parse_matches_from_html

FIXTURE_DIR = Path(__file__).parent / "fixtures"

TEAM = TeamConfig(
    name="Los Ratones",
    slug="Los_Ratones",
    short_name="LR",
    emoji="\U0001f400",
    game="leagueoflegends",
)


@pytest.fixture
def fixture_html() -> str:
    return (FIXTURE_DIR / "los_ratones_page.html").read_text()


@pytest.fixture
def matches(fixture_html: str) -> list[Match]:
    return parse_matches_from_html(fixture_html, TEAM)


# --- Scraper tests ---


class TestScraper:
    def test_finds_upcoming_matches(self, matches: list[Match]) -> None:
        upcoming = [m for m in matches if m.is_upcoming]
        assert len(upcoming) == 2

    def test_upcoming_match_details(self, matches: list[Match]) -> None:
        upcoming = sorted([m for m in matches if m.is_upcoming], key=lambda m: m.timestamp)
        first = upcoming[0]
        assert first.opponent == "Fnatic"
        assert first.timestamp == 1738360800
        assert first.tournament == "LEC 2025 Spring"
        assert "LEC/2025/Spring" in first.url
        assert first.team == TEAM
        assert first.is_upcoming is True

    def test_upcoming_second_match(self, matches: list[Match]) -> None:
        upcoming = sorted([m for m in matches if m.is_upcoming], key=lambda m: m.timestamp)
        second = upcoming[1]
        assert second.opponent == "G2 Esports"
        assert second.timestamp == 1738447200

    def test_skips_items_without_timestamp(self, matches: list[Match]) -> None:
        # The fixture has 3 carousel items but one has no data-timestamp
        upcoming = [m for m in matches if m.is_upcoming]
        assert len(upcoming) == 2

    def test_finds_past_matches(self, matches: list[Match]) -> None:
        past = [m for m in matches if not m.is_upcoming]
        assert len(past) == 2

    def test_past_match_has_score(self, matches: list[Match]) -> None:
        """Past matches may include a score when present in the table."""
        past = [m for m in matches if not m.is_upcoming]
        for m in past:
            # Score field exists (may be None if not in fixture)
            assert hasattr(m, "score")
            if m.score is not None:
                # Validate score format: digits separated by : or -
                assert re.match(r"^\d+\s*[:|\-]\s*\d+$", m.score), f"Bad score format: {m.score}"
            # Opponent and tournament are present
            assert m.opponent
            assert m.tournament

    def test_upcoming_match_has_no_score(self, matches: list[Match]) -> None:
        """Upcoming matches should have no score."""
        upcoming = [m for m in matches if m.is_upcoming]
        for m in upcoming:
            assert m.score is None

    def test_past_match_details(self, matches: list[Match]) -> None:
        past = sorted([m for m in matches if not m.is_upcoming], key=lambda m: m.timestamp)
        assert past[0].opponent == "Team Vitality"
        assert past[0].timestamp == 1738188000
        assert past[1].opponent == "MAD Lions"
        assert past[1].timestamp == 1738274400

    def test_empty_html_returns_empty(self) -> None:
        matches = parse_matches_from_html("<html><body></body></html>", TEAM)
        assert matches == []


# --- Calendar generation tests ---


class TestCalendarGen:
    def test_creates_valid_ics(self, matches: list[Match]) -> None:
        cal = create_team_calendar(TEAM, matches)
        ics_bytes = cal.to_ical()
        assert ics_bytes.startswith(b"BEGIN:VCALENDAR")
        assert b"END:VCALENDAR" in ics_bytes

    def test_event_count(self, matches: list[Match]) -> None:
        cal = create_team_calendar(TEAM, matches)
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        assert len(events) == len(matches)

    def test_upcoming_event_has_alarm(self, matches: list[Match]) -> None:
        upcoming_only = [m for m in matches if m.is_upcoming]
        cal = create_team_calendar(TEAM, upcoming_only)
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        for event in events:
            alarms = [c for c in event.walk() if c.name == "VALARM"]
            assert len(alarms) == 1

    def test_past_event_has_no_alarm(self, matches: list[Match]) -> None:
        past_only = [m for m in matches if not m.is_upcoming]
        cal = create_team_calendar(TEAM, past_only)
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        for event in events:
            alarms = [c for c in event.walk() if c.name == "VALARM"]
            assert len(alarms) == 0

    def test_calendar_metadata(self, matches: list[Match]) -> None:
        cal = create_team_calendar(TEAM, matches)
        assert b"Los Ratones" in cal.to_ical()
        assert b"X-PUBLISHED-TTL" in cal.to_ical()

    def test_empty_calendar(self) -> None:
        cal = create_team_calendar(TEAM, [])
        ics_bytes = cal.to_ical()
        assert validate_ics(ics_bytes)
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        assert len(events) == 0


# --- Feed tests ---


class TestFeeds:
    def test_rss_feed_valid_xml(self, matches: list[Match]) -> None:
        rss = generate_rss_feed(TEAM, matches)
        assert rss.startswith("<?xml")
        assert "<feed" in rss
        assert "<entry>" in rss

    def test_rss_feed_entry_count(self, matches: list[Match]) -> None:
        rss = generate_rss_feed(TEAM, matches)
        assert rss.count("<entry>") == len(matches)

    def test_json_feed_structure(self, matches: list[Match]) -> None:
        feed = generate_json_feed(TEAM, matches)
        assert feed["version"] == "https://jsonfeed.org/version/1.1"
        assert "items" in feed
        assert len(feed["items"]) == len(matches)

    def test_json_feed_item_fields(self, matches: list[Match]) -> None:
        feed = generate_json_feed(TEAM, matches)
        item = feed["items"][0]
        assert "id" in item
        assert "title" in item
        assert "date_published" in item
        assert "tags" in item

    def test_empty_feeds(self) -> None:
        rss = generate_rss_feed(TEAM, [])
        assert "<entry>" not in rss

        feed = generate_json_feed(TEAM, [])
        assert len(feed["items"]) == 0


# --- Cache tests ---


class TestCache:
    def test_save_and_load(self, tmp_path: Path, matches: list[Match]) -> None:
        cal = create_team_calendar(TEAM, matches)
        ics_bytes = cal.to_ical()

        save_to_cache(tmp_path, "Los_Ratones", ics_bytes)
        loaded = load_cached_calendar(tmp_path, "Los_Ratones")
        assert loaded == ics_bytes

    def test_load_missing_returns_none(self, tmp_path: Path) -> None:
        assert load_cached_calendar(tmp_path, "Nonexistent") is None

    def test_validate_ics_valid(self) -> None:
        assert validate_ics(b"BEGIN:VCALENDAR\r\nEND:VCALENDAR")

    def test_validate_ics_invalid(self) -> None:
        assert not validate_ics(b"not a calendar")
        assert not validate_ics(b"")
