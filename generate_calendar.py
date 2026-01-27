#!/usr/bin/env python3
"""
Los Ratones Match Calendar Generator
Scrapes upcoming match data from Liquipedia and generates an ICS calendar file.

Run manually or via GitHub Actions for auto-updates.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from icalendar import Calendar, Event, Alarm
from pathlib import Path


def fetch_match_data():
    """Fetch and parse match data from Liquipedia."""
    url = "https://liquipedia.net/leagueoflegends/Los_Ratones"
    headers = {
        "User-Agent": "LosRatonesCalendarBot/1.0 (GitHub Actions calendar feed)"
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    matches = []

    # Find all carousel items (upcoming matches)
    carousel_items = soup.find_all("div", class_="carousel-item")

    for item in carousel_items:
        # Get timestamp
        timer = item.find("span", class_="timer-object")
        if not timer or not timer.get("data-timestamp"):
            continue

        timestamp = int(timer.get("data-timestamp"))

        # Get tournament name
        tournament_span = item.find("span", class_="match-info-tournament-name")
        tournament_name = (
            tournament_span.get_text(strip=True) if tournament_span else "LEC Match"
        )

        tournament_link = tournament_span.find("a") if tournament_span else None
        tournament_url = (
            f"https://liquipedia.net{tournament_link['href']}" if tournament_link else ""
        )

        # Get opponent (second team, not Los Ratones)
        opponent_rows = item.find_all("div", class_="match-info-opponent-row")
        opponent = None

        for row in opponent_rows:
            team_link = row.find(
                "a",
                href=lambda x: x
                and "/leagueoflegends/" in x
                and "Los_Ratones" not in x,
            )
            if team_link:
                opponent = team_link.get("title", team_link.get_text(strip=True))
                break

        if opponent:
            matches.append(
                {
                    "timestamp": timestamp,
                    "opponent": opponent,
                    "tournament": tournament_name,
                    "url": tournament_url,
                }
            )

    return matches


def create_ics_calendar(matches):
    """Create an ICS calendar from match data."""
    cal = Calendar()
    cal.add("prodid", "-//Los Ratones Match Calendar//liquipedia.net//")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", "Los Ratones Matches")
    cal.add("x-wr-timezone", "Europe/Amsterdam")

    for match in matches:
        event = Event()

        # Convert timestamp to datetime
        dt = datetime.fromtimestamp(match["timestamp"], tz=timezone.utc)

        # Event details
        summary = f"🐀 LR vs {match['opponent']}"
        event.add("summary", summary)
        event.add("dtstart", dt)
        event.add("dtend", dt + timedelta(hours=2))

        description = f"Tournament: {match['tournament']}"
        if match["url"]:
            description += f"\n\nMore info: {match['url']}"
        event.add("description", description)

        if match["url"]:
            event.add("url", match["url"])

        # Create unique ID
        uid = f"los-ratones-{match['timestamp']}-{match['opponent'].replace(' ', '-').replace('_', '-')}@liquipedia.net"
        event.add("uid", uid)

        # Add alarm 30 minutes before
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add(
            "description",
            f"Los Ratones vs {match['opponent']} starts in 30 minutes!",
        )
        alarm.add("trigger", timedelta(minutes=-30))
        event.add_component(alarm)

        cal.add_component(event)

    return cal


def main():
    print("🐀 Fetching Los Ratones match data from Liquipedia...")
    matches = fetch_match_data()

    print(f"📅 Found {len(matches)} upcoming matches:")
    for m in matches:
        dt = datetime.fromtimestamp(m["timestamp"], tz=timezone.utc)
        print(f"   • {dt.strftime('%Y-%m-%d %H:%M UTC')} vs {m['opponent']}")

    # Create calendar
    cal = create_ics_calendar(matches)

    # Ensure output directory exists
    output_dir = Path("public")
    output_dir.mkdir(exist_ok=True)

    # Save calendar
    output_file = output_dir / "los_ratones.ics"
    with open(output_file, "wb") as f:
        f.write(cal.to_ical())

    print(f"\n✅ Calendar saved to: {output_file}")
    print(f"   Contains {len(matches)} events")

    # Also create a simple index.html for GitHub Pages
    index_html = output_dir / "index.html"
    with open(index_html, "w") as f:
        f.write(generate_index_html(matches))
    print(f"📄 Index page saved to: {index_html}")


def generate_index_html(matches):
    """Generate a simple HTML page with calendar subscription info."""
    matches_html = ""
    for m in matches:
        dt = datetime.fromtimestamp(m["timestamp"], tz=timezone.utc)
        matches_html += f"""
        <tr>
            <td>{dt.strftime('%b %d, %Y')}</td>
            <td>{dt.strftime('%H:%M')} UTC</td>
            <td>vs {m['opponent']}</td>
            <td>{m['tournament']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Los Ratones Match Calendar</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
            background: #1a1a2e;
            color: #eee;
        }}
        h1 {{ color: #fff; }}
        .emoji {{ font-size: 2rem; }}
        a {{ color: #7dd3fc; }}
        .subscribe-box {{
            background: #16213e;
            padding: 1.5rem;
            border-radius: 8px;
            margin: 1.5rem 0;
        }}
        .url-box {{
            background: #0f0f23;
            padding: 0.75rem;
            border-radius: 4px;
            font-family: monospace;
            word-break: break-all;
            margin: 0.5rem 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}
        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #333;
        }}
        th {{ background: #16213e; }}
        .updated {{
            color: #888;
            font-size: 0.875rem;
            margin-top: 2rem;
        }}
    </style>
</head>
<body>
    <h1><span class="emoji">🐀</span> Los Ratones Match Calendar</h1>
    
    <div class="subscribe-box">
        <h2>📅 Subscribe to Calendar</h2>
        <p>Add this URL to your calendar app (Google Calendar, Apple Calendar, Outlook, etc.):</p>
        <div class="url-box" id="cal-url"></div>
        <p><small>The calendar updates automatically every 6 hours.</small></p>
    </div>

    <h2>Upcoming Matches</h2>
    <table>
        <thead>
            <tr>
                <th>Date</th>
                <th>Time</th>
                <th>Match</th>
                <th>Tournament</th>
            </tr>
        </thead>
        <tbody>
            {matches_html if matches_html else '<tr><td colspan="4">No upcoming matches scheduled</td></tr>'}
        </tbody>
    </table>

    <p class="updated">Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
    
    <p>Data sourced from <a href="https://liquipedia.net/leagueoflegends/Los_Ratones">Liquipedia</a>.</p>

    <script>
        // Dynamically set the calendar URL based on current domain
        const calUrl = window.location.href.replace('index.html', '').replace(/\\/$/, '') + '/los_ratones.ics';
        document.getElementById('cal-url').textContent = calUrl;
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
