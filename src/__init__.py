"""Esports Calendar — shared data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TeamConfig:
    """Configuration for a team to track."""

    name: str
    slug: str
    short_name: str
    emoji: str
    game: str
    logo_url: str | None = None

    @property
    def liquipedia_url(self) -> str:
        return f"https://liquipedia.net/{self.game}/{self.slug}"


@dataclass
class Match:
    """A single match (upcoming or past)."""

    timestamp: int
    opponent: str
    tournament: str
    url: str
    team: TeamConfig
    is_upcoming: bool
    score: str | None = None
