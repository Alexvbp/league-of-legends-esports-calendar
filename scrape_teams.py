#!/usr/bin/env python3
"""
Esports Calendar — Team Discovery

Scrapes major LoL league pages on Liquipedia to discover all active teams
and writes them to teams.json. Run before generate_data.py to keep the
team roster up to date.

Usage:
    python scrape_teams.py              # Scrape all leagues in leagues.json
    python scrape_teams.py --dry-run    # Print discovered teams without writing
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

USER_AGENT = "EsportsCalendarBot/2.0 (GitHub Actions calendar feed)"
HEADERS = {"User-Agent": USER_AGENT}
REQUEST_DELAY = 2  # seconds between Liquipedia requests (be respectful)

# Common team abbreviations — add known mappings here.
# Teams not listed get an auto-generated short name.
SHORT_NAMES: dict[str, str] = {
    "Fnatic": "FNC",
    "G2 Esports": "G2",
    "GIANTX": "GX",
    "Karmine Corp": "KC",
    "Karmine Corp Blue": "KCB",
    "Los Ratones": "LR",
    "Movistar KOI": "KOI",
    "Natus Vincere": "NAVI",
    "Shifters": "SFT",
    "SK Gaming": "SK",
    "Team Heretics": "TH",
    "Team Vitality": "VIT",
    "MAD Lions": "MAD",
    "Rogue": "RGE",
    "Excel Esports": "XL",
    "Team BDS": "BDS",
    "T1": "T1",
    "Gen.G": "GEN",
    "Hanwha Life Esports": "HLE",
    "DRX": "DRX",
    "Dplus KIA": "DK",
    "KT Rolster": "KT",
    "Kwangdong Freecs": "KDF",
    "Nongshim RedForce": "NS",
    "OKSavingsBank BRION": "BRO",
    "FearX": "FOX",
    "BNK FearX": "FOX",
    "Bilibili Gaming": "BLG",
    "JD Gaming": "JDG",
    "LNG Esports": "LNG",
    "Top Esports": "TES",
    "Weibo Gaming": "WBG",
    "Royal Never Give Up": "RNG",
    "Edward Gaming": "EDG",
    "FunPlus Phoenix": "FPX",
    "Team Liquid": "TL",
    "Cloud9": "C9",
    "FlyQuest": "FLY",
    "100 Thieves": "100T",
    "NRG": "NRG",
    "Dignitas": "DIG",
    "Immortals": "IMT",
    "Shopify Rebellion": "SR",
    "LOUD": "LOUD",
    "paiN Gaming": "PNG",
    "FURIA": "FUR",
    "RED Canids": "RED",
    "Isurus": "ISG",
    "Estral Esports": "EST",
    "DetonatioN FocusMe": "DFM",
    "Fukuoka SoftBank HAWKS gaming": "SHG",
    "Sengoku Gaming": "SG",
    "Invictus Gaming": "IG",
    "Isurus Gaming": "ISU",
    "Six Karma": "6K",
    "Gen.G Esports": "GEN",
    "EDward Gaming": "EDG",
    "Oh My God": "OMG",
    "LGD Gaming": "LGD",
    "Ultra Prime": "UP",
    "Team WE": "WE",
    "Ninjas in Pyjamas": "NIP",
    "ThunderTalk Gaming": "TT",
    "Dplus": "DK",
    "FEARX": "FOX",
    "SOOPers": "SP",
    "BRION": "BRO",
    "Sentinels": "SEN",
    "Disguised": "DSG",
    "LYON": "LYN",
    "Infinity": "INF",
    "All Knights": "AK",
    "Leviatán": "LEV",
    "Keyd Stars": "KYS",
    "Fluxo W7M": "FW7",
    "LOS": "LOS",
    "PaiN Gaming": "PNG",
    "V3 Esports": "V3",
    "Clocks": "CLK",
    "Yang Yang Gaming": "YYG",
    "Team Flash": "FL",
    "Saigon Dino": "SGD",
    "Saigon Secret": "SS",
    "Apex Predator": "APX",
    "GenZ Gaming": "GNZ",
    "Mila Gaming": "MIL",
    "Never Give Up": "NGU",
    "Vikings Esports Academy": "VEA",
    "CyberCore Esports": "CCE",
}

# Simple emoji mapping per league region.
REGION_EMOJI: dict[str, str] = {
    "Europe": "🇪🇺",
    "Korea": "🇰🇷",
    "China": "🇨🇳",
    "North America": "🇺🇸",
    "Pacific": "🌏",
    "Vietnam": "🇻🇳",
    "Brazil": "🇧🇷",
    "Latin America": "🌎",
    "Japan": "🇯🇵",
}


def load_leagues(path: str = "leagues.json") -> list[dict]:
    with open(path) as f:
        return json.load(f)["leagues"]


def generate_short_name(name: str) -> str:
    """Generate a short name from a team name if not in the known mapping."""
    if name in SHORT_NAMES:
        return SHORT_NAMES[name]
    # Try first letters of each word
    words = name.split()
    if len(words) >= 2:
        return "".join(w[0].upper() for w in words[:3])
    # Just use first 3 chars
    return name[:3].upper()


def find_current_tournaments(soup: BeautifulSoup, league_url: str, league_slug: str) -> list[str]:
    """Find candidate tournament URLs from a league main page.

    Returns multiple candidates sorted by recency (most recent first).
    Scoped to the specific league to avoid matching other leagues.
    """
    pattern = re.compile(
        rf"/leagueoflegends/{re.escape(league_slug)}/202[4-9]", re.IGNORECASE
    )

    seen: set[str] = set()
    candidates: list[str] = []
    for link in soup.find_all("a", href=True):
        href = link["href"].split("#")[0]  # Strip anchors
        if pattern.match(href) and href not in seen:
            seen.add(href)
            candidates.append(href)

    # Sort: prefer most recent year, then alphabetically (Spring before Summer)
    candidates.sort(reverse=True)

    return [f"https://liquipedia.net{c}" for c in candidates]


def scrape_teams_from_page(url: str, game: str) -> list[dict]:
    """Scrape team names and slugs from a Liquipedia page.

    Looks for team links in participant/team sections using multiple strategies.
    """
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    teams: dict[str, str] = {}  # slug -> name

    # Strategy 1: Look for teamcard elements (common Liquipedia pattern)
    for card in soup.find_all(["div", "span"], class_=lambda c: c and "teamcard" in c):
        team_link = card.find("a", href=re.compile(f"/{game}/[A-Z]"))
        if team_link:
            slug = team_link["href"].split(f"/{game}/")[-1].split("/")[0]
            name = team_link.get("title", team_link.get_text(strip=True))
            if slug and name and not _is_excluded(slug):
                teams[slug] = name

    # Strategy 2: Look for team-template-text (another common pattern)
    for el in soup.find_all(class_=lambda c: c and "team-template-text" in c):
        link = el.find("a", href=True)
        if link:
            href = link["href"]
            if f"/{game}/" in href:
                slug = href.split(f"/{game}/")[-1].split("/")[0]
                name = link.get("title", link.get_text(strip=True))
                if slug and name and not _is_excluded(slug):
                    teams[slug] = name

    # Strategy 3: Find the "Participants" section and extract team links below it
    if not teams:
        for heading in soup.find_all(["h2", "h3"]):
            text = heading.get_text(strip=True).lower()
            if "participant" in text or "teams" in text:
                # Scan siblings until next heading
                sibling = heading.find_next_sibling()
                while sibling and sibling.name not in ("h2", "h3"):
                    for link in (sibling.find_all("a", href=True) if isinstance(sibling, Tag) else []):
                        href = link["href"]
                        if f"/{game}/" in href and "/" not in href.split(f"/{game}/")[-1]:
                            slug = href.split(f"/{game}/")[-1]
                            name = link.get("title", link.get_text(strip=True))
                            if slug and name and not _is_excluded(slug) and len(name) > 1:
                                teams[slug] = name
                    sibling = sibling.find_next_sibling() if isinstance(sibling, Tag) else None

    return [{"slug": slug, "name": name} for slug, name in teams.items()]


def _is_excluded(slug: str) -> bool:
    """Exclude non-team pages (players, tournaments, events, etc.)."""
    excluded_prefixes = (
        "LEC", "LCK", "LPL", "LCS", "PCS", "VCS", "CBLOL", "LLA", "LJL",
        "LTA", "LFL", "ERL", "TCL", "NLC", "LVP",
        "Portal:", "Category:", "Template:", "Season_", "Patch_",
        "All-Star", "All_Star", "Mid-Season", "World_Championship",
        "Rift_Rivals", "Worlds", "MSI", "index.php",
    )
    if any(slug.startswith(p) for p in excluded_prefixes):
        return True
    # Exclude red links (non-existent pages)
    if "redlink" in slug or "action=edit" in slug or "index.php" in slug:
        return True
    # Exclude URL-encoded slugs (broken links)
    if "%" in slug and "%C" not in slug.upper():
        return True
    # Exclude if slug looks like a year/tournament path
    if re.match(r"^\d{4}", slug):
        return True
    # Exclude slugs with slashes (sub-pages, not team pages)
    if "/" in slug:
        return True
    # Exclude very short slugs (likely abbreviations of tournaments)
    if len(slug) <= 2:
        return True
    return False


def scrape_league(league: dict) -> list[dict]:
    """Scrape all active teams from a league's current tournament page.

    Tries multiple tournament URLs until one yields teams.
    Only uses tournament pages (not the main league page) to avoid
    picking up historical teams.
    """
    print(f"\n  Fetching {league['name']} ({league['region']})...")
    resp = requests.get(league["url"], headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    league_slug = league["url"].rstrip("/").split("/")[-1]
    tournament_urls = find_current_tournaments(soup, league["url"], league_slug)

    if not tournament_urls:
        print("    No tournament pages found — skipping")
        return []

    # Try each tournament URL until we find one with teams
    for tournament_url in tournament_urls[:5]:  # Try up to 5 candidates
        print(f"    Trying: {tournament_url}")
        time.sleep(REQUEST_DELAY)
        try:
            teams = scrape_teams_from_page(tournament_url, league["game"])
            if teams:
                print(f"    Found {len(teams)} teams")
                return teams
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                print(f"    404 — trying next")
                continue
            print(f"    ERROR: {e}")
        except Exception as e:
            print(f"    ERROR: {e}")

    print("    No teams found from any tournament page")
    return []


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    leagues = load_leagues()
    print(f"Scanning {len(leagues)} leagues for teams...")

    all_teams: dict[str, dict] = {}  # slug -> team config

    for league in leagues:
        try:
            teams = scrape_league(league)
            emoji = REGION_EMOJI.get(league["region"], "🎮")

            for t in teams:
                if t["slug"] not in all_teams:
                    all_teams[t["slug"]] = {
                        "name": t["name"],
                        "slug": t["slug"],
                        "short_name": generate_short_name(t["name"]),
                        "emoji": emoji,
                        "game": league["game"],
                    }

            time.sleep(REQUEST_DELAY)
        except Exception as e:
            print(f"    ERROR: {e}")

    # Sort by name
    sorted_teams = sorted(all_teams.values(), key=lambda t: t["name"])
    result = {"teams": sorted_teams}

    print(f"\nDiscovered {len(sorted_teams)} teams across {len(leagues)} leagues")
    for t in sorted_teams:
        print(f"  {t['emoji']} {t['short_name']:>5}  {t['name']} ({t['slug']})")

    if dry_run:
        print("\n[Dry run — teams.json not written]")
        return 0

    # Merge with existing teams.json to preserve manual overrides
    existing_path = Path("teams.json")
    if existing_path.exists():
        with open(existing_path) as f:
            existing = json.load(f)
        existing_map = {t["slug"]: t for t in existing.get("teams", [])}
        # Keep manual overrides (short_name, emoji) for existing teams
        for t in sorted_teams:
            if t["slug"] in existing_map:
                old = existing_map[t["slug"]]
                t["short_name"] = old.get("short_name", t["short_name"])
                t["emoji"] = old.get("emoji", t["emoji"])

    with open("teams.json", "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nWritten {len(sorted_teams)} teams to teams.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
