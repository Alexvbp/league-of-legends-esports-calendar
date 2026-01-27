"""HTML page generation with team selector, subscribe buttons, and timezone support."""

from __future__ import annotations

import json
from datetime import datetime, timezone


def generate_index_html(all_team_data: dict, generated_utc: str | None = None) -> str:
    """Generate the index HTML page.

    all_team_data format:
    {
        "Team_Slug": {
            "config": {"name": ..., "short_name": ..., "emoji": ..., "slug": ...},
            "upcoming": [{"timestamp": int, "opponent": str, "tournament": str, "url": str}, ...],
            "past": [...],
            "cached": bool  # optional, True if data is from cache
        }
    }
    """
    if generated_utc is None:
        generated_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    teams_json = json.dumps(all_team_data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Esports Match Calendar</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 1.5rem;
            background: #0f0f1a;
            color: #e0e0e0;
            line-height: 1.6;
        }}
        h1 {{ color: #fff; margin-bottom: 0.5rem; font-size: 1.75rem; }}
        h2 {{ color: #ccc; margin: 1.5rem 0 0.75rem; font-size: 1.25rem; }}
        a {{ color: #7dd3fc; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}

        /* Team selector */
        .team-cards {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin: 1rem 0;
        }}
        .team-card {{
            background: #1a1a2e;
            border: 2px solid #2a2a4a;
            border-radius: 8px;
            padding: 0.75rem 1.25rem;
            cursor: pointer;
            transition: border-color 0.2s, background 0.2s;
            user-select: none;
        }}
        .team-card:hover {{ border-color: #7dd3fc; }}
        .team-card.selected {{
            border-color: #7dd3fc;
            background: #16213e;
        }}
        .team-card .emoji {{ font-size: 1.5rem; margin-right: 0.5rem; }}
        .team-card .name {{ font-weight: 600; }}

        /* Subscribe section */
        .subscribe-box {{
            background: #1a1a2e;
            padding: 1.25rem;
            border-radius: 8px;
            margin: 1rem 0;
        }}
        .url-box {{
            background: #0a0a16;
            padding: 0.6rem 0.75rem;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.85rem;
            word-break: break-all;
            margin: 0.5rem 0;
            color: #7dd3fc;
        }}
        .subscribe-buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.75rem;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-size: 0.875rem;
            font-weight: 500;
            text-decoration: none;
            border: none;
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        .btn:hover {{ opacity: 0.85; text-decoration: none; }}
        .btn-webcal {{ background: #2563eb; color: #fff; }}
        .btn-google {{ background: #16a34a; color: #fff; }}
        .btn-copy {{
            background: #374151;
            color: #e0e0e0;
            font-family: inherit;
        }}

        /* Feed links */
        .feed-links {{
            display: flex;
            gap: 1rem;
            margin: 0.5rem 0;
            font-size: 0.85rem;
        }}
        .feed-links a {{
            padding: 0.25rem 0.5rem;
            background: #1a1a2e;
            border-radius: 4px;
        }}

        /* Match tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 0.75rem 0;
        }}
        th, td {{
            padding: 0.6rem 0.75rem;
            text-align: left;
            border-bottom: 1px solid #222;
        }}
        th {{ background: #1a1a2e; color: #999; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
        tbody tr:hover {{ background: #16213e; }}

        .badge {{
            display: inline-block;
            padding: 0.15rem 0.5rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-upcoming {{ background: #1e3a5f; color: #7dd3fc; }}
        .badge-past {{ background: #2a2a3a; color: #888; }}

        .empty {{ color: #666; font-style: italic; padding: 1.5rem; text-align: center; }}
        .cached-notice {{
            background: #4a3000;
            color: #fbbf24;
            padding: 0.5rem 0.75rem;
            border-radius: 4px;
            font-size: 0.85rem;
            margin: 0.5rem 0;
        }}
        .footer {{
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #222;
            color: #666;
            font-size: 0.8rem;
        }}

        @media (max-width: 600px) {{
            body {{ padding: 1rem; }}
            th, td {{ padding: 0.4rem; font-size: 0.85rem; }}
            .subscribe-buttons {{ flex-direction: column; }}
            .btn {{ justify-content: center; }}
        }}
    </style>
</head>
<body>
    <h1>Esports Match Calendar</h1>
    <p>Auto-updating calendar feeds for your favorite teams. Select a team to subscribe.</p>

    <h2>Teams</h2>
    <div class="team-cards" id="team-cards"></div>

    <div id="subscribe-section" style="display:none">
        <h2>Subscribe</h2>
        <div class="subscribe-box">
            <p>Add to your calendar app:</p>
            <div class="url-box" id="ics-url"></div>
            <div class="subscribe-buttons">
                <a id="btn-webcal" class="btn btn-webcal" href="#">
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M3.5 0a.5.5 0 0 1 .5.5V1h8V.5a.5.5 0 0 1 1 0V1h1a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2h1V.5a.5.5 0 0 1 .5-.5M1 4v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V4z"/></svg>
                    webcal:// Subscribe
                </a>
                <a id="btn-google" class="btn btn-google" href="#" target="_blank" rel="noopener">
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M8 0a8 8 0 1 0 0 16A8 8 0 0 0 8 0M4.5 7.5a.5.5 0 0 1 0-1h5.793L8.146 4.354a.5.5 0 1 1 .708-.708l3 3a.5.5 0 0 1 0 .708l-3 3a.5.5 0 0 1-.708-.708L10.293 7.5z"/></svg>
                    Add to Google Calendar
                </a>
                <button id="btn-copy" class="btn btn-copy" onclick="copyUrl()">
                    Copy URL
                </button>
            </div>
            <p style="margin-top:0.75rem;font-size:0.8rem;color:#888">
                The calendar updates automatically every few hours. Your app will sync changes.
            </p>
        </div>

        <div class="feed-links">
            <a id="feed-rss" href="#">RSS Feed</a>
            <a id="feed-json" href="#">JSON Feed</a>
            <a id="feed-liquipedia" href="#" target="_blank" rel="noopener">Liquipedia</a>
        </div>
    </div>

    <div id="cached-notice" class="cached-notice" style="display:none">
        Data may be stale — using cached version due to a recent fetch error.
    </div>

    <div id="matches-section" style="display:none">
        <h2>Upcoming Matches</h2>
        <div id="upcoming-table"></div>

        <h2>Recent Matches <span style="font-size:0.8rem;color:#888;font-weight:normal">(spoiler-free)</span></h2>
        <div id="past-table"></div>
    </div>

    <div class="footer">
        <p>Last updated: <span id="last-updated">{generated_utc}</span></p>
        <p>Data sourced from <a href="https://liquipedia.net" target="_blank" rel="noopener">Liquipedia</a>.
           Calendar feeds available in ICS, RSS, and JSON formats.</p>
    </div>

    <script>
    const TEAMS = {teams_json};
    const GENERATED = "{generated_utc}";

    // State
    let selectedTeam = localStorage.getItem('selectedTeam') || Object.keys(TEAMS)[0] || null;

    function getBaseUrl() {{
        return window.location.href.replace(/\\/index\\.html$/, '').replace(/\\/$/, '');
    }}

    function init() {{
        renderTeamCards();
        if (selectedTeam && TEAMS[selectedTeam]) {{
            selectTeam(selectedTeam);
        }}
        // Format last updated in local time
        const el = document.getElementById('last-updated');
        if (el && GENERATED) {{
            const d = new Date(GENERATED);
            el.textContent = d.toLocaleString();
        }}
    }}

    function renderTeamCards() {{
        const container = document.getElementById('team-cards');
        container.innerHTML = '';
        for (const [slug, data] of Object.entries(TEAMS)) {{
            const card = document.createElement('div');
            card.className = 'team-card' + (slug === selectedTeam ? ' selected' : '');
            card.innerHTML = '<span class="emoji">' + escapeHtml(data.config.emoji) + '</span><span class="name">' + escapeHtml(data.config.name) + '</span>';
            card.onclick = () => selectTeam(slug);
            container.appendChild(card);
        }}
    }}

    function selectTeam(slug) {{
        selectedTeam = slug;
        localStorage.setItem('selectedTeam', slug);
        renderTeamCards();

        const data = TEAMS[slug];
        if (!data) return;

        const base = getBaseUrl();
        const icsUrl = base + '/' + slug.toLowerCase() + '.ics';
        const webcalUrl = icsUrl.replace(/^https?:/, 'webcal:');
        const googleUrl = 'https://calendar.google.com/calendar/r?cid=' + encodeURIComponent(icsUrl);
        const rssUrl = base + '/' + slug.toLowerCase() + '.xml';
        const jsonUrl = base + '/' + slug.toLowerCase() + '.json';

        document.getElementById('ics-url').textContent = icsUrl;
        document.getElementById('btn-webcal').href = webcalUrl;
        document.getElementById('btn-google').href = googleUrl;
        document.getElementById('feed-rss').href = rssUrl;
        document.getElementById('feed-json').href = jsonUrl;
        document.getElementById('feed-liquipedia').href = 'https://liquipedia.net/' + (data.config.game || 'leagueoflegends') + '/' + slug;

        document.getElementById('subscribe-section').style.display = '';
        document.getElementById('matches-section').style.display = '';

        // Cached notice
        document.getElementById('cached-notice').style.display = data.cached ? '' : 'none';

        renderMatchTable('upcoming-table', data.upcoming, true, data.config);
        renderMatchTable('past-table', data.past, false, data.config);
    }}

    function renderMatchTable(containerId, matches, isUpcoming, config) {{
        const container = document.getElementById(containerId);
        if (!matches || matches.length === 0) {{
            container.innerHTML = '<div class="empty">No ' + (isUpcoming ? 'upcoming' : 'recent') + ' matches</div>';
            return;
        }}

        let html = '<table><thead><tr><th>Date</th><th>Time</th><th>Match</th><th>Tournament</th></tr></thead><tbody>';
        for (const m of matches) {{
            const d = new Date(m.timestamp * 1000);
            const dateStr = d.toLocaleDateString(undefined, {{ month: 'short', day: 'numeric', year: 'numeric' }});
            const timeStr = d.toLocaleTimeString(undefined, {{ hour: '2-digit', minute: '2-digit' }});
            const badge = isUpcoming ? '<span class="badge badge-upcoming">Upcoming</span>' : '<span class="badge badge-past">Played</span>';
            const opponent = escapeHtml(m.opponent);
            const tournament = m.url
                ? '<a href="' + escapeHtml(m.url) + '" target="_blank" rel="noopener">' + escapeHtml(m.tournament) + '</a>'
                : escapeHtml(m.tournament);

            html += '<tr>';
            html += '<td>' + dateStr + '</td>';
            html += '<td>' + timeStr + '</td>';
            html += '<td>' + escapeHtml(config.emoji) + ' ' + escapeHtml(config.short_name) + ' vs ' + opponent + ' ' + badge + '</td>';
            html += '<td>' + tournament + '</td>';
            html += '</tr>';
        }}
        html += '</tbody></table>';
        container.innerHTML = html;
    }}

    function copyUrl() {{
        const url = document.getElementById('ics-url').textContent;
        navigator.clipboard.writeText(url).then(() => {{
            const btn = document.getElementById('btn-copy');
            btn.textContent = 'Copied!';
            setTimeout(() => {{ btn.textContent = 'Copy URL'; }}, 2000);
        }});
    }}

    function escapeHtml(text) {{
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }}

    init();
    </script>
</body>
</html>"""
