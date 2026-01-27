# Esports Match Calendar

Auto-updating ICS, RSS, and JSON calendar feeds for esports teams, powered by [Liquipedia](https://liquipedia.net) data and GitHub Pages.

Pre-configured for [Los Ratones](https://liquipedia.net/leagueoflegends/Los_Ratones) — add any team by editing `teams.json`.

## Features

- ICS calendar feed (works with Google Calendar, Apple Calendar, Outlook, etc.)
- Upcoming and past matches (spoiler-free — no scores shown)
- RSS (Atom) and JSON feeds
- Multi-team support via `teams.json`
- Web interface with team selector, one-click subscribe buttons, and local timezone display
- Pushover notifications on errors
- Automatic caching — serves last known good calendar if a scrape fails
- Auto-updates every 3 hours via GitHub Actions

## Subscribe

Once deployed, visit your GitHub Pages URL to pick a team and subscribe. Direct ICS link:

```
https://YOUR_USERNAME.github.io/los-ratones-calendar/los_ratones.ics
```

Works with:
- **Google Calendar** — Settings > Add calendar > From URL
- **Apple Calendar** — File > New Calendar Subscription
- **Outlook** — Add calendar > Subscribe from web
- **Any app** that supports ICS/iCal feeds

The web page also provides `webcal://` and Google Calendar one-click subscribe buttons.

## Quick Setup

### 1. Create the Repository

Fork this repo or create a new one and copy the files.

### 2. Enable GitHub Pages

1. Go to **Settings** > **Pages**
2. Under "Build and deployment", select **GitHub Actions**
3. Save

### 3. (Optional) Configure Pushover Notifications

To get notified when calendar generation fails:

1. Create a [Pushover](https://pushover.net) account and application
2. In your repo, go to **Settings** > **Secrets and variables** > **Actions**
3. Add secrets: `PUSHOVER_USER_KEY` and `PUSHOVER_API_TOKEN`

### 4. Run the Workflow

The calendar updates automatically every 3 hours. To trigger immediately:

1. Go to **Actions** tab
2. Select "Update Calendar"
3. Click **Run workflow**

## Add More Teams

Edit `teams.json`:

```json
{
  "teams": [
    {
      "name": "Los Ratones",
      "slug": "Los_Ratones",
      "short_name": "LR",
      "emoji": "\ud83d\udc00",
      "game": "leagueoflegends"
    },
    {
      "name": "Fnatic",
      "slug": "Fnatic",
      "short_name": "FNC",
      "emoji": "\ud83d\udfe0",
      "game": "leagueoflegends"
    }
  ]
}
```

The `slug` must match the Liquipedia URL path (e.g., `https://liquipedia.net/leagueoflegends/Fnatic` uses slug `Fnatic`).

## Local Development

```bash
# Install
pip install -e ".[dev]"

# Generate feeds
python generate_calendar.py
# Output in ./public/

# Run tests
pytest
```

## Project Structure

```
.github/workflows/update-calendar.yml   # GitHub Actions (3h cron + manual)
src/
  __init__.py          # Data models (TeamConfig, Match)
  scraper.py           # Liquipedia scraping (upcoming + past)
  calendar_gen.py      # ICS generation
  feeds.py             # RSS (Atom) + JSON Feed generation
  html_gen.py          # Web page with team selector
  notify.py            # Pushover error notifications
  cache.py             # Calendar caching / fallback
tests/
  fixtures/            # Saved HTML for offline testing
  test_scraper.py      # Tests for scraping, calendar, feeds, cache
teams.json             # Team configuration
generate_calendar.py   # Entry point
pyproject.toml         # Python project config
```

## Output Feeds

For each team in `teams.json`, the build produces:

| File | Format | Use |
|------|--------|-----|
| `{slug}.ics` | iCalendar | Calendar app subscription |
| `{slug}.xml` | Atom RSS | RSS reader subscription |
| `{slug}.json` | JSON Feed | Programmatic access |
| `index.html` | HTML | Web interface |

## License

MIT
