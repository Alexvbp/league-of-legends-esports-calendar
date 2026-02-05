/**
 * Cloudflare Pages Function — Dynamic calendar feed generation.
 *
 * GET /api/calendar?teams=Los_Ratones,Fnatic&format=ics|json|rss
 *
 * Reads per-team JSON data from R2 storage (with ASSETS fallback)
 * and merges them into a single ICS, JSON Feed, or Atom RSS response.
 */

interface Env {
  ASSETS: Fetcher;
  DATA_BUCKET: R2Bucket;
}

interface TeamInfo {
  name: string;
  slug: string;
  short_name: string;
  emoji: string;
  game: string;
  liquipedia_url: string;
  logo_url?: string;
}

interface MatchData {
  timestamp: number;
  opponent: string;
  tournament: string;
  url: string;
  is_upcoming: boolean;
}

interface TeamData {
  team: TeamInfo;
  matches: MatchData[];
  generated_utc: string;
}

const SLUG_PATTERN = /^[a-zA-Z0-9_-]+$/;

// --- Request handling ---

export const onRequest: PagesFunction<Env> = async (context) => {
  if (context.request.method === "OPTIONS") {
    return corsResponse(new Response(null, { status: 204 }));
  }

  if (context.request.method !== "GET") {
    return corsResponse(new Response("Method not allowed", { status: 405 }));
  }

  const url = new URL(context.request.url);
  const teamsParam = url.searchParams.get("teams") || "";
  const format = url.searchParams.get("format") || "ics";
  const tournamentFilter = url.searchParams.get("tournament") || "";

  // Reminder: minutes before match (0 = no reminder, default = 30, max = 1440)
  const reminderParam = url.searchParams.get("reminder");
  let reminderMinutes = 30;
  if (reminderParam !== null) {
    const parsed = parseInt(reminderParam, 10);
    if (isNaN(parsed) || parsed < 0 || parsed > 1440) {
      return corsResponse(
        new Response(
          "Invalid 'reminder' parameter. Must be an integer between 0 and 1440.",
          { status: 400 }
        )
      );
    }
    reminderMinutes = parsed;
  }

  const slugs = teamsParam
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  if (slugs.length === 0) {
    return corsResponse(
      new Response(
        "Missing 'teams' parameter. Usage: /api/calendar?teams=Los_Ratones,Fnatic",
        { status: 400 }
      )
    );
  }

  // Validate slugs to prevent path traversal
  for (const slug of slugs) {
    if (!SLUG_PATTERN.test(slug)) {
      return corsResponse(
        new Response(`Invalid team slug: ${slug}`, { status: 400 })
      );
    }
  }

  // Load team data from R2 (with ASSETS fallback)
  const teamDataList: TeamData[] = [];
  for (const slug of slugs) {
    try {
      const key = `${slug.toLowerCase()}.json`;
      let data: TeamData | null = null;

      // Try R2 first
      if (context.env.DATA_BUCKET) {
        const object = await context.env.DATA_BUCKET.get(key);
        if (object) {
          data = (await object.json()) as TeamData;
        }
      }

      // Fall back to ASSETS
      if (!data) {
        const assetUrl = new URL(`/data/${key}`, url.origin);
        const resp = await context.env.ASSETS.fetch(assetUrl.toString());
        if (resp.ok) {
          data = (await resp.json()) as TeamData;
        }
      }

      if (data) {
        teamDataList.push(data);
      }
    } catch {
      // Skip teams that can't be loaded
    }
  }

  if (teamDataList.length === 0) {
    return corsResponse(
      new Response("No data found for the requested teams", { status: 404 })
    );
  }

  // Filter by tournament if specified (case-insensitive substring match)
  if (tournamentFilter) {
    const filter = tournamentFilter.toLowerCase();
    for (const teamData of teamDataList) {
      teamData.matches = teamData.matches.filter((m) =>
        m.tournament.toLowerCase().includes(filter)
      );
    }
  }

  switch (format) {
    case "ics":
      return corsResponse(
        new Response(generateICS(teamDataList, reminderMinutes), {
          headers: {
            "Content-Type": "text/calendar; charset=utf-8",
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": 'inline; filename="esports-calendar.ics"',
          },
        })
      );
    case "json":
      return corsResponse(
        new Response(JSON.stringify(generateJSONFeed(teamDataList, url)), {
          headers: {
            "Content-Type": "application/feed+json; charset=utf-8",
            "Cache-Control": "public, max-age=3600",
          },
        })
      );
    case "rss":
      return corsResponse(
        new Response(generateAtomFeed(teamDataList, url), {
          headers: {
            "Content-Type": "application/atom+xml; charset=utf-8",
            "Cache-Control": "public, max-age=3600",
          },
        })
      );
    default:
      return corsResponse(
        new Response("Unknown format. Use: ics, json, or rss", { status: 400 })
      );
  }
};

function corsResponse(response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set("Access-Control-Allow-Origin", "*");
  headers.set("Access-Control-Allow-Methods", "GET, OPTIONS");
  headers.set("Access-Control-Allow-Headers", "Content-Type");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

// --- ICS generation (RFC 5545) ---

function generateICS(teams: TeamData[], reminderMinutes: number): string {
  const teamNames = teams.map((t) => t.team.name).join(", ");
  const lines: string[] = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    `PRODID:-//Esports Calendar//${teamNames}//`,
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    `X-WR-CALNAME:${teamNames} Matches`,
    "X-PUBLISHED-TTL:PT4H",
  ];

  for (const teamData of teams) {
    const { team } = teamData;
    for (const match of teamData.matches) {
      lines.push(...generateVEvent(team, match, reminderMinutes));
    }
  }

  lines.push("END:VCALENDAR");
  return lines.join("\r\n") + "\r\n";
}

function generateVEvent(team: TeamInfo, match: MatchData, reminderMinutes: number): string[] {
  const start = formatICSDate(match.timestamp);
  const end = formatICSDate(match.timestamp + 2 * 60 * 60); // +2 hours
  const opponentSlug = match.opponent
    .replace(/\s+/g, "-")
    .replace(/_/g, "-")
    .toLowerCase();

  // Create canonical UID: sort teams alphabetically to avoid duplicates
  // when both teams are selected in the same calendar
  const teams = [team.slug.toLowerCase(), opponentSlug].sort();
  const uid = `${teams[0]}-vs-${teams[1]}-${match.timestamp}@esports-calendar`;

  const summary = icsEscape(`${team.emoji} ${team.short_name} vs ${match.opponent}`);
  let description = icsEscape(`Tournament: ${match.tournament}`);
  if (match.url) {
    description += icsEscape(`\\n\\nMore info: ${match.url}`);
  }
  if (!match.is_upcoming) {
    description += icsEscape("\\n\\n(Completed match)");
  }

  const lines: string[] = [
    "BEGIN:VEVENT",
    `UID:${uid}`,
    `DTSTART:${start}`,
    `DTEND:${end}`,
    `SUMMARY:${summary}`,
    `DESCRIPTION:${description}`,
    "STATUS:CONFIRMED",
  ];

  if (match.url) {
    lines.push(`URL:${match.url}`);
  }

  if (!match.is_upcoming) {
    lines.push("TRANSP:TRANSPARENT");
  }

  // Alarm for upcoming matches only (when reminder > 0)
  if (match.is_upcoming && reminderMinutes > 0) {
    lines.push(
      "BEGIN:VALARM",
      "ACTION:DISPLAY",
      `DESCRIPTION:${icsEscape(`${team.name} vs ${match.opponent} starts in ${reminderMinutes} minutes!`)}`,
      `TRIGGER:-PT${reminderMinutes}M`,
      "END:VALARM"
    );
  }

  lines.push("END:VEVENT");
  return lines;
}

function formatICSDate(timestamp: number): string {
  const d = new Date(timestamp * 1000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}T` +
    `${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}Z`
  );
}

function icsEscape(text: string): string {
  return text.replace(/[\\;,]/g, (c) => "\\" + c);
}

// --- JSON Feed v1.1 ---

function generateJSONFeed(
  teams: TeamData[],
  requestUrl: URL
): Record<string, unknown> {
  const items = [];
  for (const teamData of teams) {
    const { team } = teamData;
    for (const match of teamData.matches) {
      const dt = new Date(match.timestamp * 1000).toISOString();
      const opponentSlug = match.opponent
        .replace(/\s+/g, "-")
        .toLowerCase();
      items.push({
        id: `${team.slug.toLowerCase()}-${match.timestamp}-${opponentSlug}`,
        title: `${team.emoji} ${team.short_name} vs ${match.opponent}`,
        date_published: dt,
        url: match.url || team.liquipedia_url,
        tags: [
          match.is_upcoming ? "upcoming" : "completed",
          match.tournament,
        ],
        content_text: `${match.is_upcoming ? "Upcoming" : "Completed"} — ${match.tournament}`,
      });
    }
  }

  items.sort(
    (a, b) =>
      new Date(b.date_published).getTime() -
      new Date(a.date_published).getTime()
  );

  const teamNames = teams.map((t) => t.team.name).join(", ");
  return {
    version: "https://jsonfeed.org/version/1.1",
    title: `${teamNames} Match Schedule`,
    home_page_url: requestUrl.origin,
    feed_url: requestUrl.toString(),
    description: `Upcoming and recent matches for ${teamNames}`,
    items,
  };
}

// --- Atom RSS ---

function generateAtomFeed(teams: TeamData[], requestUrl: URL): string {
  const now = new Date().toISOString();
  const teamNames = teams.map((t) => t.team.name).join(", ");
  const teamSlugs = teams.map((t) => t.team.slug.toLowerCase()).join("-");

  let entries = "";
  const allMatches: { team: TeamInfo; match: MatchData }[] = [];
  for (const teamData of teams) {
    for (const match of teamData.matches) {
      allMatches.push({ team: teamData.team, match });
    }
  }
  allMatches.sort((a, b) => b.match.timestamp - a.match.timestamp);

  for (const { team, match } of allMatches) {
    const dt = new Date(match.timestamp * 1000).toISOString();
    const status = match.is_upcoming ? "Upcoming" : "Completed";
    const title = xmlEscape(
      `${team.emoji} ${team.short_name} vs ${match.opponent}`
    );
    const tournament = xmlEscape(match.tournament);
    const opponentSlug = match.opponent
      .replace(/\s+/g, "-")
      .toLowerCase();
    const entryId = `${team.slug.toLowerCase()}-${match.timestamp}-${opponentSlug}`;

    entries += `  <entry>
    <id>urn:esports-calendar:${entryId}</id>
    <title>${title}</title>
    <updated>${dt}</updated>
    <summary>${status} — ${tournament}</summary>
    <link href="${xmlEscape(match.url)}" rel="alternate"/>
    <category term="${status.toLowerCase()}"/>
  </entry>\n`;
  }

  return `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:esports-calendar:${xmlEscape(teamSlugs)}</id>
  <title>${xmlEscape(teamNames)} Match Schedule</title>
  <subtitle>Upcoming and recent matches</subtitle>
  <updated>${now}</updated>
  <link href="${xmlEscape(requestUrl.toString())}" rel="self" type="application/atom+xml"/>
  <generator>esports-calendar</generator>
${entries}</feed>
`;
}

function xmlEscape(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}
