// =====================================================================
// State
// =====================================================================
let allTeams = [];
let leagues = [];
let leagueTeamMap = {};      // league name → [team slugs]
let teamLeagueMap = {};      // team slug → league name
let selectedSlugs = JSON.parse(localStorage.getItem('selectedTeams') || '[]');
let teamDataCache = {};
let activeTournamentFilter = { upcoming: null, past: null };
let teamSearchQuery = '';
let activeRegionFilter = null;
let countdownInterval = null;
let mobileActiveTab = 'schedule';
let reminderMinutes = parseInt(localStorage.getItem('reminderMinutes') || '30', 10);

// Emoji → region label mapping
const EMOJI_REGIONS = {
    '\u{1F1EA}\u{1F1FA}': 'Europe',
    '\u{1F1F0}\u{1F1F7}': 'Korea',
    '\u{1F1E8}\u{1F1F3}': 'China',
    '\u{1F1FA}\u{1F1F8}': 'NA',
    '\u{1F1E7}\u{1F1F7}': 'Brazil',
    '\u{1F1FB}\u{1F1F3}': 'Vietnam',
    '\u{1F1EF}\u{1F1F5}': 'Japan',
    '\u{1F30F}': 'Pacific',
    '\u{1F30E}': 'LATAM',
    '\u{1F400}': 'Europe',
};

// Region → league mapping (from leagues.json regions)
const REGION_TO_LEAGUE = {
    'Europe': 'LEC',
    'Korea': 'LCK',
    'China': 'LPL',
    'North America': 'LCS',
    'NA': 'LCS',
    'Pacific': 'PCS',
    'Vietnam': 'VCS',
    'Brazil': 'CBLOL',
    'Latin America': 'LLA',
    'LATAM': 'LLA',
    'Japan': 'LJL',
};

// =====================================================================
// Init
// =====================================================================
async function init() {
    try {
        const teamsResp = await fetch('/data/teams.json');
        if (!teamsResp.ok) throw new Error('Failed to load teams');
        const manifest = await teamsResp.json();
        allTeams = manifest.teams;

        // Leagues fetch is best-effort — if it fails (e.g. file not in public/),
        // we fall back to building leagues from emoji→region mapping alone.
        try {
            const leaguesResp = await fetch('/data/leagues.json');
            if (leaguesResp.ok) {
                const ct = leaguesResp.headers.get('content-type') || '';
                if (ct.includes('json')) {
                    const leaguesData = await leaguesResp.json();
                    leagues = leaguesData.leagues || [];
                }
            }
        } catch (_) {
            // leagues stays empty — buildLeagueMapping handles this
        }

        // Build league→teams mapping
        buildLeagueMapping();

        document.getElementById('loading').style.display = 'none';
        document.getElementById('layout').style.display = '';

        const validSlugs = new Set(allTeams.map(t => t.slug));
        selectedSlugs = selectedSlugs.filter(s => validSlugs.has(s));

        render();

        if (manifest.generated_utc) {
            const d = new Date(manifest.generated_utc);
            document.getElementById('footer-updated').textContent =
                'Last updated: ' + d.toLocaleString();
        }
    } catch (e) {
        document.getElementById('loading').textContent =
            'Failed to load team data. Please try again later.';
    }
}

function buildLeagueMapping() {
    // Map each team to a league based on emoji → region → league
    leagueTeamMap = {};
    teamLeagueMap = {};

    // If leagues.json didn't load, use hardcoded league order
    if (leagues.length === 0) {
        leagues = [
            { name: 'LEC' }, { name: 'LCK' }, { name: 'LPL' }, { name: 'LCS' },
            { name: 'PCS' }, { name: 'VCS' }, { name: 'CBLOL' }, { name: 'LLA' }, { name: 'LJL' }
        ];
    }

    for (const league of leagues) {
        leagueTeamMap[league.name] = [];
    }

    for (const team of allTeams) {
        const emojiRegion = EMOJI_REGIONS[team.emoji];
        let leagueName = null;

        if (emojiRegion) {
            leagueName = REGION_TO_LEAGUE[emojiRegion];
        }

        if (!leagueName) {
            // Fallback: try matching team region from any league
            leagueName = 'Other';
        }

        if (!leagueTeamMap[leagueName]) {
            leagueTeamMap[leagueName] = [];
        }
        leagueTeamMap[leagueName].push(team.slug);
        teamLeagueMap[team.slug] = leagueName;
    }

    // Remove empty leagues
    for (const key of Object.keys(leagueTeamMap)) {
        if (leagueTeamMap[key].length === 0) delete leagueTeamMap[key];
    }
}

// =====================================================================
// Rendering
// =====================================================================
function render() {
    renderLeagueChips();
    renderTeamBrowse();
    renderSelectedTeams();
    renderHeaderStrip();
    renderSubscribeBar();
    loadAndRenderMatches();
    saveSelection();
    updateNoTeamsState();
}

function updateNoTeamsState() {
    const noTeams = document.getElementById('no-teams-state');
    const upcoming = document.getElementById('upcoming-section');
    const past = document.getElementById('past-section');
    if (selectedSlugs.length === 0) {
        noTeams.style.display = '';
        upcoming.style.display = 'none';
        past.style.display = 'none';
    } else {
        noTeams.style.display = 'none';
    }
}

// --- League Chips ---
function renderLeagueChips() {
    const container = document.getElementById('league-chips');
    const selectedSet = new Set(selectedSlugs);

    // Order: leagues from leagues.json first, then "Other" if it exists
    const orderedLeagues = leagues.map(l => l.name).filter(n => leagueTeamMap[n]);
    if (leagueTeamMap['Other']) orderedLeagues.push('Other');

    let html = '';
    for (const name of orderedLeagues) {
        const teams = leagueTeamMap[name] || [];
        const allSelected = teams.length > 0 && teams.every(s => selectedSet.has(s));
        const someSelected = teams.some(s => selectedSet.has(s));
        const cls = allSelected ? ' active' : (someSelected ? ' partial' : '');
        html += `<span class="league-chip${cls}" data-league="${esc(name)}">${esc(name)}<span class="chip-count">${teams.length}</span></span>`;
    }
    container.innerHTML = html;
}

// --- Team Browse (league-grouped accordion) ---
function renderTeamBrowse() {
    const container = document.getElementById('team-browse');
    const selectedSet = new Set(selectedSlugs);

    // Region filter pills
    const allAvailable = allTeams.filter(t => !selectedSet.has(t.slug));
    const regionCounts = {};
    for (const t of allAvailable) {
        const region = EMOJI_REGIONS[t.emoji] || 'Other';
        regionCounts[region] = (regionCounts[region] || 0) + 1;
    }
    const regions = Object.keys(regionCounts).sort();
    let regionHTML = `<span class="region-tag${!activeRegionFilter ? ' active' : ''}" data-region="">All</span>`;
    for (const r of regions) {
        regionHTML += `<span class="region-tag${activeRegionFilter === r ? ' active' : ''}" data-region="${esc(r)}">${esc(r)}</span>`;
    }
    document.getElementById('region-filters').innerHTML = regionHTML;

    // Filter teams
    let filteredTeams = allAvailable;
    if (teamSearchQuery) {
        const q = teamSearchQuery.toLowerCase();
        filteredTeams = filteredTeams.filter(t =>
            t.name.toLowerCase().includes(q) ||
            t.short_name.toLowerCase().includes(q) ||
            t.slug.toLowerCase().includes(q)
        );
    }
    if (activeRegionFilter) {
        filteredTeams = filteredTeams.filter(t =>
            (EMOJI_REGIONS[t.emoji] || 'Other') === activeRegionFilter
        );
    }

    // Group filtered teams by league
    const groups = {};
    for (const t of filteredTeams) {
        const league = teamLeagueMap[t.slug] || 'Other';
        if (!groups[league]) groups[league] = [];
        groups[league].push(t);
    }

    // Order leagues
    const orderedLeagues = leagues.map(l => l.name).filter(n => groups[n]);
    if (groups['Other']) orderedLeagues.push('Other');

    if (filteredTeams.length === 0) {
        container.innerHTML = '<div class="empty-state" style="padding:1rem">No teams match your filter</div>';
        return;
    }

    let html = '';
    for (const leagueName of orderedLeagues) {
        const teams = groups[leagueName] || [];
        if (teams.length === 0) continue;

        const allInLeague = leagueTeamMap[leagueName] || [];
        const selectedInLeague = allInLeague.filter(s => selectedSet.has(s)).length;
        const addAllLabel = selectedInLeague === allInLeague.length ? 'Remove All' :
                           selectedInLeague > 0 ? `Add ${allInLeague.length - selectedInLeague} more` : 'Add All';

        html += `<div class="league-group">
            <div class="league-group-header" data-league-toggle="${esc(leagueName)}">
                <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                <span class="league-label">${esc(leagueName)}</span>
                <span class="league-count">${teams.length} team${teams.length !== 1 ? 's' : ''}</span>
                <span class="add-all-btn" data-add-all="${esc(leagueName)}">${addAllLabel}</span>
            </div>
            <div class="league-group-body" style="max-height:500px">
                ${teams.map(t => `<div class="team-card${selectedSet.has(t.slug) ? ' selected' : ''}" data-slug="${esc(t.slug)}">
                    ${teamIcon(t)}
                    <span class="name">${esc(t.short_name)}</span>
                </div>`).join('')}
            </div>
        </div>`;
    }
    container.innerHTML = html;
}

// --- Selected Teams ---
function renderSelectedTeams() {
    const list = document.getElementById('selected-list');
    const badge = document.getElementById('selected-count-badge');
    badge.textContent = selectedSlugs.length || '';

    if (selectedSlugs.length === 0) {
        list.innerHTML = '<div class="selected-empty">Click teams or leagues to add them</div>';
        return;
    }

    let html = '';
    for (const slug of selectedSlugs) {
        const team = allTeams.find(t => t.slug === slug);
        if (!team) continue;
        html += `<span class="selected-pill" data-slug="${esc(slug)}">
            ${teamIcon(team)} ${esc(team.short_name)}
            <span class="remove-x" data-remove="${esc(slug)}">&times;</span>
        </span>`;
    }
    html += `<button class="clear-all-btn" id="clear-all-btn">Clear all</button>`;
    list.innerHTML = html;
}

// --- Header Team Strip ---
function renderHeaderStrip() {
    const strip = document.getElementById('header-strip');
    const count = document.getElementById('header-count');

    if (selectedSlugs.length === 0) {
        strip.innerHTML = '';
        count.textContent = '';
        return;
    }

    let html = '';
    for (const slug of selectedSlugs) {
        const team = allTeams.find(t => t.slug === slug);
        if (!team) continue;
        html += `<span class="header-pill" data-slug="${esc(slug)}">
            ${teamIcon(team)} ${esc(team.short_name)}
            <span class="remove-x" data-remove="${esc(slug)}">&times;</span>
        </span>`;
    }
    strip.innerHTML = html;
    count.textContent = selectedSlugs.length + ' team' + (selectedSlugs.length !== 1 ? 's' : '');
}

// --- Subscribe Bar ---
function buildCalendarUrl() {
    const base = window.location.origin;
    const teamsParam = selectedSlugs.join(',');
    let url = base + '/api/calendar?teams=' + encodeURIComponent(teamsParam);
    if (reminderMinutes !== 30) {
        url += '&reminder=' + reminderMinutes;
    }
    return url;
}

function renderSubscribeBar() {
    const bar = document.getElementById('subscribe-bar');
    const countEl = document.getElementById('sub-count');

    if (selectedSlugs.length === 0) {
        bar.classList.remove('visible');
        return;
    }

    bar.classList.add('visible');
    countEl.textContent = '\u00b7 ' + selectedSlugs.length + ' team' + (selectedSlugs.length !== 1 ? 's' : '');

    const icsUrl = buildCalendarUrl();
    const webcalUrl = icsUrl.replace(/^https?:/, 'webcal:');
    const googleUrl = 'https://calendar.google.com/calendar/r?cid=' + encodeURIComponent(webcalUrl);
    const rssUrl = icsUrl + '&format=rss';
    const jsonUrl = icsUrl + '&format=json';

    document.getElementById('subscribe-url').textContent = icsUrl;
    document.getElementById('btn-webcal').href = webcalUrl;
    document.getElementById('btn-google').href = googleUrl;
    document.getElementById('link-rss').href = rssUrl;
    document.getElementById('link-json').href = jsonUrl;

    // Set reminder dropdown value
    const reminderSelect = document.getElementById('reminder-select');
    if (reminderSelect) {
        reminderSelect.value = String(reminderMinutes);
    }

    updateFilteredSubscribe();
}

function updateFilteredSubscribe() {
    const filterDiv = document.getElementById('tournament-subscribe');
    const activeFilter = activeTournamentFilter.upcoming || activeTournamentFilter.past;

    if (!activeFilter) {
        filterDiv.style.display = 'none';
        return;
    }

    filterDiv.style.display = '';
    const icsUrl = buildCalendarUrl();
    const filteredUrl = icsUrl + '&tournament=' + encodeURIComponent(activeFilter);
    const webcalFiltered = filteredUrl.replace(/^https?:/, 'webcal:');

    document.getElementById('tournament-filter-label').textContent = activeFilter;
    document.getElementById('subscribe-url-filtered').textContent = filteredUrl;
    document.getElementById('btn-webcal-filtered').href = webcalFiltered;
}

// =====================================================================
// Matches
// =====================================================================
async function loadAndRenderMatches() {
    if (selectedSlugs.length === 0) return;

    const allUpcoming = [];
    const allPast = [];
    const now = Math.floor(Date.now() / 1000); // Current timestamp in seconds

    for (const slug of selectedSlugs) {
        let data = teamDataCache[slug];
        if (!data) {
            try {
                const resp = await fetch('/data/' + slug.toLowerCase() + '.json');
                if (resp.ok) {
                    data = await resp.json();
                    teamDataCache[slug] = data;
                }
            } catch {}
        }
        if (!data) continue;

        for (const m of data.matches) {
            const entry = { ...m, team: data.team };
            // Dynamically determine if match is upcoming or past based on current time
            // Consider match as past if it ended (timestamp + 2 hours)
            const matchEndTime = m.timestamp + (2 * 60 * 60); // +2 hours
            if (now < matchEndTime) {
                allUpcoming.push(entry);
            } else {
                allPast.push(entry);
            }
        }
    }

    allUpcoming.sort((a, b) => a.timestamp - b.timestamp);
    allPast.sort((a, b) => b.timestamp - a.timestamp);

    document.getElementById('upcoming-section').style.display = '';
    document.getElementById('past-section').style.display = '';

    renderHero(allUpcoming);
    renderMatchSection('upcoming', allUpcoming, true);
    renderMatchSection('past', allPast.slice(0, 30), false);
}

// --- Hero Card ---
function renderHero(upcoming) {
    const container = document.getElementById('hero-container');

    if (upcoming.length === 0) {
        container.innerHTML = '';
        if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
        return;
    }

    const next = upcoming[0];
    const d = new Date(next.timestamp * 1000);
    const now = Date.now();
    const diff = next.timestamp * 1000 - now;
    const matchDuration = 2 * 60 * 60 * 1000; // 2 hours in milliseconds
    const timeSinceStart = now - next.timestamp * 1000;
    const isLive = timeSinceStart >= 0 && timeSinceStart < matchDuration;

    container.innerHTML = `<div class="hero-card">
        <div class="hero-label">Next Match</div>
        <div class="hero-matchup">${teamIcon(next.team)} ${esc(next.team.short_name)} <span style="color:var(--text-muted);font-weight:400">vs</span> ${opponentIcon(next.opponent)}${esc(next.opponent)}</div>
        <div class="hero-tournament">${esc(next.tournament)}</div>
        <div id="hero-countdown-wrap">
            ${isLive ? '<span class="hero-live">LIVE NOW</span>' : renderCountdown(Math.max(0, diff))}
        </div>
    </div>`;

    // Start countdown
    if (countdownInterval) clearInterval(countdownInterval);
    if (!isLive) {
        countdownInterval = setInterval(function() {
            const currentNow = Date.now();
            const remaining = next.timestamp * 1000 - currentNow;
            const currentTimeSinceStart = currentNow - next.timestamp * 1000;
            const currentIsLive = currentTimeSinceStart >= 0 && currentTimeSinceStart < matchDuration;

            const wrap = document.getElementById('hero-countdown-wrap');
            if (!wrap) { clearInterval(countdownInterval); return; }

            if (currentIsLive) {
                wrap.innerHTML = '<span class="hero-live">LIVE NOW</span>';
                // Keep interval running to update when match ends
            } else if (remaining <= 0 && currentTimeSinceStart >= matchDuration) {
                // Match has ended, reload the matches to move it to past section
                clearInterval(countdownInterval);
                loadAndRenderMatches();
            } else {
                wrap.innerHTML = renderCountdown(Math.max(0, remaining));
            }
        }, 1000);
    } else {
        // Match is currently live, keep checking for when it ends
        countdownInterval = setInterval(function() {
            const currentNow = Date.now();
            const currentTimeSinceStart = currentNow - next.timestamp * 1000;

            if (currentTimeSinceStart >= matchDuration) {
                // Match has ended, reload the matches to move it to past section
                clearInterval(countdownInterval);
                loadAndRenderMatches();
            }
        }, 1000);
    }
}

function renderCountdown(ms) {
    const totalSec = Math.floor(ms / 1000);
    const days = Math.floor(totalSec / 86400);
    const hours = Math.floor((totalSec % 86400) / 3600);
    const mins = Math.floor((totalSec % 3600) / 60);
    const secs = totalSec % 60;

    let html = '<div class="hero-countdown">';
    if (days > 0) html += `<div class="countdown-unit"><div class="countdown-value">${days}</div><div class="countdown-label">days</div></div>`;
    html += `<div class="countdown-unit"><div class="countdown-value">${String(hours).padStart(2,'0')}</div><div class="countdown-label">hours</div></div>`;
    html += `<div class="countdown-unit"><div class="countdown-value">${String(mins).padStart(2,'0')}</div><div class="countdown-label">mins</div></div>`;
    html += `<div class="countdown-unit"><div class="countdown-value">${String(secs).padStart(2,'0')}</div><div class="countdown-label">secs</div></div>`;
    html += '</div>';
    return html;
}

// --- Match Section ---
function renderMatchSection(type, matches, isUpcoming) {
    const filterContainer = document.getElementById('tournament-filter-' + type);
    const matchContainer = document.getElementById(type + '-container');

    if (matches.length === 0) {
        filterContainer.innerHTML = '';
        matchContainer.innerHTML = '<div class="empty-state">No ' +
            (isUpcoming ? 'upcoming' : 'recent') + ' matches</div>';
        return;
    }

    // Extract tournaments
    const tournamentCounts = {};
    for (const m of matches) {
        const baseTournament = normalizeTournament(m.tournament);
        tournamentCounts[baseTournament] = (tournamentCounts[baseTournament] || 0) + 1;
    }
    const tournaments = Object.keys(tournamentCounts).sort();

    // Filter tags
    const activeFilter = activeTournamentFilter[type];
    let filterHTML = '';
    if (tournaments.length > 1) {
        filterHTML += `<span class="tournament-tag${!activeFilter ? ' active' : ''}" data-filter-type="${type}" data-tournament="">All <span class="count">${matches.length}</span></span>`;
        for (const t of tournaments) {
            filterHTML += `<span class="tournament-tag${activeFilter === t ? ' active' : ''}" data-filter-type="${type}" data-tournament="${esc(t)}">${esc(t)} <span class="count">${tournamentCounts[t]}</span></span>`;
        }
    }
    filterContainer.innerHTML = filterHTML;

    // Filter
    const filtered = activeFilter
        ? matches.filter(m => normalizeTournament(m.tournament) === activeFilter)
        : matches;

    // Group by day
    const dayGroups = {};
    for (const m of filtered) {
        const d = new Date(m.timestamp * 1000);
        const dayKey = d.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' });
        if (!dayGroups[dayKey]) dayGroups[dayKey] = { date: d, matches: [] };
        dayGroups[dayKey].matches.push(m);
    }

    const today = new Date();
    const todayStr = today.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' });

    let html = '';
    for (const [dayLabel, group] of Object.entries(dayGroups)) {
        const isToday = dayLabel === todayStr;
        html += `<div class="day-group${isToday ? ' is-today' : ''}">
            <div class="day-header">
                <span class="day-label">${esc(dayLabel)}</span>
                ${isToday ? '<span class="today-badge">TODAY</span>' : ''}
                <span class="day-count">${group.matches.length} match${group.matches.length !== 1 ? 'es' : ''}</span>
            </div>
            <div class="match-cards">
                ${group.matches.map(m => matchCardHTML(m, isUpcoming)).join('')}
            </div>
        </div>`;
    }

    matchContainer.innerHTML = html;
}

function matchCardHTML(m, isUpcoming) {
    const d = new Date(m.timestamp * 1000);
    const timeStr = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    const now = Date.now();
    const diff = m.timestamp * 1000 - now;
    const relTime = getRelativeTime(diff);

    let badgeHTML = '';
    if (isUpcoming) {
        const matchDuration = 2 * 60 * 60 * 1000; // 2 hours in milliseconds
        const timeSinceStart = now - m.timestamp * 1000;
        const isLive = timeSinceStart >= 0 && timeSinceStart < matchDuration;

        if (isLive) {
            badgeHTML = '<span class="match-badge match-badge-live">LIVE</span>';
        } else {
            badgeHTML = '<span class="match-badge match-badge-upcoming">Upcoming</span>';
        }
    } else {
        badgeHTML = '<span class="match-badge match-badge-past">Played</span>';
    }

    const linkAttr = m.url ? `data-url="${esc(m.url)}"` : '';
    const linkIcon = m.url ? '<span class="match-card-link"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></span>' : '';

    return `<div class="match-card" ${linkAttr}>
        <div>
            <div class="match-card-time">${timeStr}</div>
            <div class="match-card-relative">${esc(relTime)}</div>
        </div>
        <div>
            <div class="match-card-teams">${teamIcon(m.team)} ${esc(m.team.short_name)} <span class="vs">vs</span> ${opponentIcon(m.opponent)}${esc(m.opponent)}</div>
            <div class="match-card-tournament">${esc(m.tournament)}</div>
        </div>
        <div class="match-card-meta">
            ${badgeHTML}
            ${linkIcon}
        </div>
    </div>`;
}

function getRelativeTime(diffMs) {
    const absDiff = Math.abs(diffMs);
    const isFuture = diffMs > 0;

    if (absDiff < 60000) return isFuture ? 'now' : 'just now';
    if (absDiff < 3600000) {
        const m = Math.floor(absDiff / 60000);
        return isFuture ? 'in ' + m + 'm' : m + 'm ago';
    }
    if (absDiff < 86400000) {
        const h = Math.floor(absDiff / 3600000);
        return isFuture ? 'in ' + h + 'h' : h + 'h ago';
    }
    const d = Math.floor(absDiff / 86400000);
    return isFuture ? 'in ' + d + 'd' : d + 'd ago';
}

function normalizeTournament(name) {
    return name.replace(/\s*-\s*(Week|Day|Round|Match\s*Day)\s*\d+.*$/i, '').trim();
}

// =====================================================================
// Actions
// =====================================================================
function toggleTeam(slug) {
    const idx = selectedSlugs.indexOf(slug);
    if (idx >= 0) {
        selectedSlugs.splice(idx, 1);
    } else {
        selectedSlugs.push(slug);
    }
    activeTournamentFilter = { upcoming: null, past: null };
    teamDataCache = {};
    render();
}

function toggleLeague(leagueName) {
    const teams = leagueTeamMap[leagueName] || [];
    if (teams.length === 0) return;

    const selectedSet = new Set(selectedSlugs);
    const allSelected = teams.every(s => selectedSet.has(s));

    if (allSelected) {
        // Remove all league teams
        selectedSlugs = selectedSlugs.filter(s => !teams.includes(s));
    } else {
        // Add missing league teams
        for (const s of teams) {
            if (!selectedSet.has(s)) selectedSlugs.push(s);
        }
    }
    activeTournamentFilter = { upcoming: null, past: null };
    teamDataCache = {};
    render();
}

function addAllLeague(leagueName) {
    const teams = leagueTeamMap[leagueName] || [];
    const selectedSet = new Set(selectedSlugs);
    const allInLeagueSelected = teams.every(s => selectedSet.has(s));

    if (allInLeagueSelected) {
        selectedSlugs = selectedSlugs.filter(s => !teams.includes(s));
    } else {
        for (const s of teams) {
            if (!selectedSet.has(s)) selectedSlugs.push(s);
        }
    }
    activeTournamentFilter = { upcoming: null, past: null };
    teamDataCache = {};
    render();
}

function clearAll() {
    selectedSlugs = [];
    activeTournamentFilter = { upcoming: null, past: null };
    teamDataCache = {};
    render();
}

function setTournamentFilter(type, tournament) {
    activeTournamentFilter[type] = tournament;
    loadAndRenderMatches();
    updateFilteredSubscribe();
}

function setRegionFilter(region) {
    activeRegionFilter = region;
    renderTeamBrowse();
}

function saveSelection() {
    localStorage.setItem('selectedTeams', JSON.stringify(selectedSlugs));
}

function setReminder(minutes) {
    reminderMinutes = minutes;
    localStorage.setItem('reminderMinutes', String(minutes));
    renderSubscribeBar();
}

function copyUrl() {
    const url = document.getElementById('subscribe-url').textContent;
    navigator.clipboard.writeText(url).then(function() {
        const btn = document.getElementById('btn-copy');
        const orig = btn.innerHTML;
        btn.textContent = 'Copied!';
        setTimeout(function() { btn.innerHTML = orig; }, 2000);
    });
}

function copyFilteredUrl() {
    const url = document.getElementById('subscribe-url-filtered').textContent;
    navigator.clipboard.writeText(url).then(function() {
        const btn = document.getElementById('btn-copy-filtered');
        btn.textContent = 'Copied!';
        setTimeout(function() { btn.textContent = 'Copy filtered URL'; }, 2000);
    });
}

function esc(text) {
    if (text == null) return '';
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}

function teamIcon(team) {
    if (team.logo_url) {
        // Proxy Liquipedia images to bypass hotlink protection
        const proxyUrl = `/image-proxy?url=${encodeURIComponent(team.logo_url)}`;
        return `<img src="${esc(proxyUrl)}" alt="${esc(team.short_name)}" class="team-logo" onerror="this.style.display='none';this.nextElementSibling.style.display='inline'"><span class="emoji" style="display:none">${esc(team.emoji)}</span>`;
    }
    return `<span class="emoji">${esc(team.emoji)}</span>`;
}

function findTeamByName(name) {
    // Try exact match first
    let team = allTeams.find(t => t.name === name);
    if (team) return team;

    // Try case-insensitive match
    const lowerName = name.toLowerCase();
    team = allTeams.find(t => t.name.toLowerCase() === lowerName);
    if (team) return team;

    // Try short name match
    team = allTeams.find(t => t.short_name === name);
    if (team) return team;

    return null;
}

function opponentIcon(opponentName) {
    const team = findTeamByName(opponentName);
    if (team && team.logo_url) {
        const proxyUrl = `/image-proxy?url=${encodeURIComponent(team.logo_url)}`;
        return `<img src="${esc(proxyUrl)}" alt="${esc(opponentName)}" class="team-logo" onerror="this.style.display='none'">`;
    }
    // No logo found, return nothing (just show opponent name)
    return '';
}

// =====================================================================
// Panel toggle (tablet/mobile)
// =====================================================================
function togglePanel() {
    const panel = document.getElementById('panel');
    const overlay = document.getElementById('panel-overlay');
    panel.classList.toggle('open');
    overlay.classList.toggle('visible');
}

function closePanel() {
    document.getElementById('panel').classList.remove('open');
    document.getElementById('panel-overlay').classList.remove('visible');
}

// =====================================================================
// Mobile tabs
// =====================================================================
function setMobileTab(tab) {
    mobileActiveTab = tab;
    document.body.classList.remove('mobile-view-teams', 'mobile-view-subscribe');

    // Update tab active state
    document.querySelectorAll('.mobile-tab').forEach(function(el) {
        el.classList.toggle('active', el.dataset.tab === tab);
    });

    if (tab === 'teams') {
        document.body.classList.add('mobile-view-teams');
        document.getElementById('panel').classList.add('open');
    } else {
        document.getElementById('panel').classList.remove('open');
    }

    if (tab === 'subscribe') {
        const bar = document.getElementById('subscribe-bar');
        bar.classList.add('expanded');
    }
}

// =====================================================================
// Event Delegation
// =====================================================================
document.addEventListener('click', function(e) {
    // Mobile menu toggle
    if (e.target.closest('#mobile-menu-btn')) {
        togglePanel();
        return;
    }

    // Panel overlay close
    if (e.target.closest('#panel-overlay')) {
        closePanel();
        return;
    }

    // League chip click
    const leagueChip = e.target.closest('.league-chip');
    if (leagueChip && leagueChip.dataset.league) {
        toggleLeague(leagueChip.dataset.league);
        return;
    }

    // League group header toggle
    const leagueToggle = e.target.closest('[data-league-toggle]');
    if (leagueToggle && !e.target.closest('[data-add-all]')) {
        const body = leagueToggle.nextElementSibling;
        const isCollapsed = body.classList.contains('collapsed');
        body.classList.toggle('collapsed');
        leagueToggle.classList.toggle('collapsed');
        return;
    }

    // Add all button
    const addAll = e.target.closest('[data-add-all]');
    if (addAll) {
        addAllLeague(addAll.dataset.addAll);
        return;
    }

    // Team card click (browse panel)
    const teamCard = e.target.closest('.team-card');
    if (teamCard && teamCard.dataset.slug) {
        toggleTeam(teamCard.dataset.slug);
        return;
    }

    // Remove from selected (pill × button)
    const removeBtn = e.target.closest('[data-remove]');
    if (removeBtn) {
        toggleTeam(removeBtn.dataset.remove);
        return;
    }

    // Clear all
    if (e.target.closest('#clear-all-btn')) {
        clearAll();
        return;
    }

    // Region filter
    const regionTag = e.target.closest('.region-tag');
    if (regionTag && regionTag.dataset.region !== undefined) {
        setRegionFilter(regionTag.dataset.region || null);
        return;
    }

    // Tournament filter
    const tournamentTag = e.target.closest('.tournament-tag');
    if (tournamentTag && tournamentTag.dataset.filterType !== undefined) {
        setTournamentFilter(tournamentTag.dataset.filterType, tournamentTag.dataset.tournament || null);
        return;
    }

    // Match card click → open URL
    const matchCard = e.target.closest('.match-card');
    if (matchCard && matchCard.dataset.url) {
        window.open(matchCard.dataset.url, '_blank', 'noopener');
        return;
    }

    // Subscribe bar toggle
    if (e.target.closest('#subscribe-toggle')) {
        document.getElementById('subscribe-bar').classList.toggle('expanded');
        return;
    }

    // Copy URL buttons
    if (e.target.closest('#btn-copy')) {
        copyUrl();
        return;
    }
    if (e.target.closest('#btn-copy-filtered')) {
        copyFilteredUrl();
        return;
    }

    // Mobile tabs
    const mobileTab = e.target.closest('.mobile-tab');
    if (mobileTab && mobileTab.dataset.tab) {
        setMobileTab(mobileTab.dataset.tab);
        return;
    }
});

// Search input + reminder dropdown
document.addEventListener('input', function(e) {
    if (e.target.id === 'team-search') {
        teamSearchQuery = e.target.value;
        renderTeamBrowse();
    }
});

document.addEventListener('change', function(e) {
    if (e.target.id === 'reminder-select') {
        setReminder(parseInt(e.target.value, 10));
    }
});

// =====================================================================
// Start
// =====================================================================
init();
