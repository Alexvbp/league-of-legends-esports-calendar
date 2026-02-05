import { describe, it, expect, beforeAll } from "vitest";
import { onRequest } from "../functions/api/calendar";

// --- Test fixtures ---

const FUTURE_TS = Math.floor(Date.now() / 1000) + 86400; // tomorrow
const PAST_TS = Math.floor(Date.now() / 1000) - 86400; // yesterday

interface TeamData {
  team: {
    name: string;
    slug: string;
    short_name: string;
    emoji: string;
    game: string;
    liquipedia_url: string;
  };
  matches: {
    timestamp: number;
    opponent: string;
    tournament: string;
    url: string;
    is_upcoming: boolean;
    score?: string;
  }[];
  generated_utc: string;
}

const TEAM_A: TeamData = {
  team: {
    name: "Fnatic",
    slug: "Fnatic",
    short_name: "FNC",
    emoji: "\u{1F1EA}\u{1F1FA}",
    game: "leagueoflegends",
    liquipedia_url: "https://liquipedia.net/leagueoflegends/Fnatic",
  },
  matches: [
    {
      timestamp: FUTURE_TS,
      opponent: "G2 Esports",
      tournament: "LEC 2025 Spring",
      url: "https://liquipedia.net/leagueoflegends/LEC/2025",
      is_upcoming: true,
    },
    {
      timestamp: PAST_TS,
      opponent: "MAD Lions",
      tournament: "LEC 2025 Spring",
      url: "https://liquipedia.net/leagueoflegends/LEC/2025",
      is_upcoming: false,
      score: "2 : 1",
    },
  ],
  generated_utc: new Date().toISOString(),
};

const TEAM_B: TeamData = {
  team: {
    name: "G2 Esports",
    slug: "G2_Esports",
    short_name: "G2",
    emoji: "\u{1F1EA}\u{1F1FA}",
    game: "leagueoflegends",
    liquipedia_url: "https://liquipedia.net/leagueoflegends/G2_Esports",
  },
  matches: [
    {
      timestamp: FUTURE_TS,
      opponent: "Fnatic",
      tournament: "LEC 2025 Spring",
      url: "https://liquipedia.net/leagueoflegends/LEC/2025",
      is_upcoming: true,
    },
  ],
  generated_utc: new Date().toISOString(),
};

// --- Mock Cloudflare context ---

function createMockContext(
  urlStr: string,
  teamDataMap: Record<string, TeamData>,
  method = "GET"
) {
  const request = new Request(urlStr, { method });
  const env = {
    DATA_BUCKET: {
      get: async (key: string) => {
        const slug = key.replace(/\.json$/, "");
        const data = teamDataMap[slug];
        if (data) {
          return {
            json: async () => data,
            text: async () => JSON.stringify(data),
            body: new ReadableStream(),
          };
        }
        return null;
      },
    } as unknown as R2Bucket,
    ASSETS: {
      fetch: async () => new Response("Not found", { status: 404 }),
    } as unknown as Fetcher,
  };

  return {
    request,
    env,
    params: {},
    functionPath: "/api/calendar",
    waitUntil: () => {},
    passThroughOnException: () => {},
    next: () => Promise.resolve(new Response()),
    data: {},
  } as unknown as Parameters<typeof onRequest>[0];
}

// =====================================================================
// ICS Generation Tests
// =====================================================================
describe("ICS generation", () => {
  it("produces valid ICS output", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    expect(resp.status).toBe(200);

    const body = await resp.text();
    expect(body).toContain("BEGIN:VCALENDAR");
    expect(body).toContain("END:VCALENDAR");
    expect(body).toContain("VERSION:2.0");
    expect(body).toContain("BEGIN:VEVENT");
    expect(body).toContain("END:VEVENT");
  });

  it("generates correct event count", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    const body = await resp.text();

    const eventCount = (body.match(/BEGIN:VEVENT/g) || []).length;
    expect(eventCount).toBe(2); // one upcoming + one past
  });

  it("generates UIDs with alphabetically sorted team names", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    const body = await resp.text();

    // Extract UIDs
    const uids = (body.match(/UID:.+/g) || []);
    expect(uids.length).toBeGreaterThan(0);

    // UID should contain team slugs in alphabetical order
    // "fnatic" vs opponent "g2-esports" → sorted: ["fnatic", "g2-esports"]
    const futureUid = uids.find((u) => u.includes(String(FUTURE_TS)));
    expect(futureUid).toContain("fnatic-vs-g2-esports");
  });

  it("includes VALARM for upcoming matches with default reminder", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    const body = await resp.text();

    expect(body).toContain("BEGIN:VALARM");
    expect(body).toContain("TRIGGER:-PT30M");
  });

  it("does not include VALARM for past matches", async () => {
    // Create team with only past matches
    const pastOnly: TeamData = {
      ...TEAM_A,
      matches: [TEAM_A.matches[1]], // past match only
    };
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic",
      { fnatic: pastOnly }
    );
    const resp = await onRequest(ctx);
    const body = await resp.text();

    expect(body).not.toContain("BEGIN:VALARM");
  });

  it("includes TRANSP:TRANSPARENT for past matches", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    const body = await resp.text();

    expect(body).toContain("TRANSP:TRANSPARENT");
  });

  it("includes score in description for completed matches", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    const body = await resp.text();

    expect(body).toContain("Score: 2 : 1");
  });
});

// =====================================================================
// Configurable Reminder Tests
// =====================================================================
describe("Configurable reminder", () => {
  it("uses custom reminder value in VALARM trigger", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic&reminder=60",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    const body = await resp.text();

    expect(body).toContain("TRIGGER:-PT60M");
    expect(body).not.toContain("TRIGGER:-PT30M");
  });

  it("omits VALARM when reminder=0", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic&reminder=0",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    const body = await resp.text();

    expect(body).not.toContain("BEGIN:VALARM");
  });

  it("rejects invalid reminder values", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic&reminder=-1",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    expect(resp.status).toBe(400);
  });

  it("rejects reminder > 1440", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic&reminder=1441",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    expect(resp.status).toBe(400);
  });

  it("rejects non-numeric reminder", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic&reminder=abc",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    expect(resp.status).toBe(400);
  });
});

// =====================================================================
// JSON Feed Tests
// =====================================================================
describe("JSON Feed", () => {
  it("produces valid JSON Feed structure", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic&format=json",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    expect(resp.status).toBe(200);

    const feed = await resp.json() as Record<string, unknown>;
    expect(feed.version).toBe("https://jsonfeed.org/version/1.1");
    expect(feed.title).toContain("Fnatic");
    expect(feed.items).toBeDefined();
    expect(Array.isArray(feed.items)).toBe(true);
  });

  it("includes correct fields on items", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic&format=json",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    const feed = await resp.json() as Record<string, unknown>;
    const items = feed.items as Record<string, unknown>[];

    for (const item of items) {
      expect(item.id).toBeDefined();
      expect(item.title).toBeDefined();
      expect(item.date_published).toBeDefined();
      expect(item.url).toBeDefined();
      expect(item.tags).toBeDefined();
      expect(item.content_text).toBeDefined();
    }
  });

  it("sorts items by date descending", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic&format=json",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    const feed = await resp.json() as Record<string, unknown>;
    const items = feed.items as { date_published: string }[];

    for (let i = 1; i < items.length; i++) {
      const prev = new Date(items[i - 1].date_published).getTime();
      const curr = new Date(items[i].date_published).getTime();
      expect(prev).toBeGreaterThanOrEqual(curr);
    }
  });
});

// =====================================================================
// Atom RSS Tests
// =====================================================================
describe("Atom RSS", () => {
  it("produces valid XML structure", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic&format=rss",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    expect(resp.status).toBe(200);

    const body = await resp.text();
    expect(body).toContain('<?xml version="1.0"');
    expect(body).toContain("<feed xmlns=");
    expect(body).toContain("<entry>");
    expect(body).toContain("</entry>");
    expect(body).toContain("</feed>");
  });
});

// =====================================================================
// Parameter Validation Tests
// =====================================================================
describe("Parameter validation", () => {
  it("returns 400 when teams parameter is missing", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar",
      {}
    );
    const resp = await onRequest(ctx);
    expect(resp.status).toBe(400);
    const body = await resp.text();
    expect(body).toContain("teams");
  });

  it("returns 400 for invalid slugs", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=../etc/passwd",
      {}
    );
    const resp = await onRequest(ctx);
    expect(resp.status).toBe(400);
    const body = await resp.text();
    expect(body).toContain("Invalid team slug");
  });

  it("returns 400 for unknown format", async () => {
    const ctx = createMockContext(
      "https://example.com/api/calendar?teams=Fnatic&format=xml",
      { fnatic: TEAM_A }
    );
    const resp = await onRequest(ctx);
    expect(resp.status).toBe(400);
  });
});
