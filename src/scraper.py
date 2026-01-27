"""Liquipedia scraper for upcoming and past matches."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup, Tag

from src import Match, TeamConfig

USER_AGENT = "EsportsCalendarBot/2.0 (GitHub Actions calendar feed)"


def fetch_team_matches(team: TeamConfig) -> list[Match]:
    """Fetch upcoming and past matches for a team from Liquipedia."""
    url = team.liquipedia_url
    headers = {"User-Agent": USER_AGENT}

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    upcoming = _parse_upcoming_matches(soup, team)
    past = _parse_past_matches(soup, team)

    return upcoming + past


def parse_matches_from_html(html: str, team: TeamConfig) -> list[Match]:
    """Parse matches from raw HTML (used by tests)."""
    soup = BeautifulSoup(html, "html.parser")
    upcoming = _parse_upcoming_matches(soup, team)
    past = _parse_past_matches(soup, team)
    return upcoming + past


def _parse_upcoming_matches(soup: BeautifulSoup, team: TeamConfig) -> list[Match]:
    """Parse upcoming matches from carousel items."""
    matches: list[Match] = []
    carousel_items = soup.find_all("div", class_="carousel-item")

    for item in carousel_items:
        match = _parse_carousel_item(item, team)
        if match:
            matches.append(match)

    return matches


def _parse_carousel_item(item: Tag, team: TeamConfig) -> Match | None:
    """Parse a single carousel item into a Match."""
    timer = item.find("span", class_="timer-object")
    if not timer or not timer.get("data-timestamp"):
        return None

    timestamp = int(timer.get("data-timestamp"))

    tournament_span = item.find("span", class_="match-info-tournament-name")
    tournament_name = (
        tournament_span.get_text(strip=True) if tournament_span else "Match"
    )

    tournament_link = tournament_span.find("a") if tournament_span else None
    tournament_url = (
        f"https://liquipedia.net{tournament_link['href']}" if tournament_link else ""
    )

    opponent = _extract_opponent(item, team)
    if not opponent:
        return None

    return Match(
        timestamp=timestamp,
        opponent=opponent,
        tournament=tournament_name,
        url=tournament_url,
        team=team,
        is_upcoming=True,
    )


def _extract_opponent(item: Tag, team: TeamConfig) -> str | None:
    """Extract opponent name from match element, filtering out the tracked team."""
    opponent_rows = item.find_all("div", class_="match-info-opponent-row")
    for row in opponent_rows:
        team_link = row.find(
            "a",
            href=lambda x: x
            and f"/{team.game}/" in x
            and team.slug not in x,
        )
        if team_link:
            return team_link.get("title", team_link.get_text(strip=True))
    return None


def _parse_past_matches(soup: BeautifulSoup, team: TeamConfig) -> list[Match]:
    """Parse past/recent matches from results tables.

    Liquipedia team pages typically have a 'Results' section with a wikitable.
    We extract date, tournament, and opponent — intentionally skipping scores
    to avoid spoilers.
    """
    matches: list[Match] = []

    # Strategy 1: Find tables under a "Results" heading
    results_table = _find_results_table(soup)
    if results_table:
        matches = _parse_results_table(results_table, team)

    # Strategy 2: Look for recent-matches-list or match-row elements
    if not matches:
        matches = _parse_recent_matches_list(soup, team)

    return matches


def _find_results_table(soup: BeautifulSoup) -> Tag | None:
    """Find the results table on the page."""
    # Look for heading containing "Results"
    for heading in soup.find_all(["h2", "h3"]):
        heading_text = heading.get_text(strip=True)
        if "results" in heading_text.lower() or "recent" in heading_text.lower():
            # Find the next table after this heading
            sibling = heading.find_next_sibling()
            while sibling:
                if sibling.name == "table":
                    return sibling
                # Also check inside wrapper divs
                if sibling.name == "div":
                    table = sibling.find("table")
                    if table:
                        return table
                # Stop if we hit another heading
                if sibling.name in ("h2", "h3"):
                    break
                sibling = sibling.find_next_sibling()

    # Fallback: look for any wikitable with match-like columns
    for table in soup.find_all("table", class_="wikitable"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if any(h in headers for h in ("date", "opponent", "vs", "vs.")):
            return table

    return None


def _parse_results_table(table: Tag, team: TeamConfig) -> list[Match]:
    """Parse a results wikitable into Match objects (no scores)."""
    matches: list[Match] = []
    headers: list[str] = []

    header_row = table.find("tr")
    if header_row:
        headers = [th.get_text(strip=True).lower() for th in header_row.find_all("th")]

    # Map column indices
    date_idx = _find_col_index(headers, ["date"])
    tournament_idx = _find_col_index(headers, ["tournament", "event"])
    opponent_idx = _find_col_index(headers, ["opponent", "vs", "vs.", "vs. opponent"])

    rows = table.find_all("tr")[1:]  # Skip header row
    for row in rows:
        cells = row.find_all(["td", "th"])
        if len(cells) < max(filter(lambda x: x >= 0, [date_idx, tournament_idx, opponent_idx]), default=0) + 1:
            continue

        # Extract date
        timestamp = _parse_date_cell(cells, date_idx)
        if not timestamp:
            continue

        # Extract tournament
        tournament_name = "Match"
        tournament_url = ""
        if tournament_idx >= 0 and tournament_idx < len(cells):
            tournament_cell = cells[tournament_idx]
            tournament_name = tournament_cell.get_text(strip=True) or "Match"
            link = tournament_cell.find("a")
            if link and link.get("href"):
                href = link["href"]
                if not href.startswith("http"):
                    href = f"https://liquipedia.net{href}"
                tournament_url = href

        # Extract opponent
        opponent = "TBD"
        if opponent_idx >= 0 and opponent_idx < len(cells):
            opponent_cell = cells[opponent_idx]
            opp_link = opponent_cell.find("a")
            if opp_link:
                opponent = opp_link.get("title", opp_link.get_text(strip=True))
            else:
                opponent = opponent_cell.get_text(strip=True) or "TBD"

        # Skip if opponent is the tracked team itself
        if team.slug.replace("_", " ").lower() in opponent.lower():
            continue

        matches.append(Match(
            timestamp=timestamp,
            opponent=opponent,
            tournament=tournament_name,
            url=tournament_url,
            team=team,
            is_upcoming=False,
        ))

    return matches


def _parse_recent_matches_list(soup: BeautifulSoup, team: TeamConfig) -> list[Match]:
    """Fallback: parse recent matches from list/panel structures."""
    matches: list[Match] = []

    # Look for panel boxes with recent results
    for panel in soup.find_all("div", class_="panel-box"):
        heading = panel.find(class_="panel-box-heading")
        if not heading or "result" not in heading.get_text(strip=True).lower():
            continue

        body = panel.find(class_="panel-box-body")
        if not body:
            continue

        # Parse match entries within the panel
        for match_div in body.find_all("div", recursive=False):
            timer = match_div.find("span", class_="timer-object")
            if not timer or not timer.get("data-timestamp"):
                continue

            timestamp = int(timer.get("data-timestamp"))
            opponent = _extract_opponent(match_div, team)
            if not opponent:
                # Try finding any team link that isn't our team
                for link in match_div.find_all("a"):
                    href = link.get("href", "")
                    if f"/{team.game}/" in href and team.slug not in href:
                        opponent = link.get("title", link.get_text(strip=True))
                        break

            if opponent:
                tournament_span = match_div.find("span", class_="match-info-tournament-name")
                tournament_name = tournament_span.get_text(strip=True) if tournament_span else "Match"

                matches.append(Match(
                    timestamp=timestamp,
                    opponent=opponent,
                    tournament=tournament_name,
                    url="",
                    team=team,
                    is_upcoming=False,
                ))

    return matches


def _find_col_index(headers: list[str], candidates: list[str]) -> int:
    """Find column index matching any candidate name."""
    for i, h in enumerate(headers):
        if any(c in h for c in candidates):
            return i
    return -1


def _parse_date_cell(cells: list[Tag], date_idx: int) -> int | None:
    """Parse a date cell into a Unix timestamp."""
    if date_idx < 0 or date_idx >= len(cells):
        return None

    cell = cells[date_idx]

    # Check for timer-object with data-timestamp (most reliable)
    timer = cell.find("span", class_="timer-object")
    if timer and timer.get("data-timestamp"):
        return int(timer["data-timestamp"])

    # Try parsing date text
    date_text = cell.get_text(strip=True)
    # Remove timezone abbreviations for parsing
    date_text = re.sub(r"\s+(CET|CEST|UTC|EST|PST|GMT)\s*$", "", date_text)

    for fmt in (
        "%B %d, %Y - %H:%M",
        "%Y-%m-%d %H:%M",
        "%b %d, %Y - %H:%M",
        "%Y-%m-%d",
        "%B %d, %Y",
    ):
        try:
            dt = datetime.strptime(date_text, fmt)
            dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue

    return None
