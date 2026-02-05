import { describe, it, expect } from "vitest";
import { onRequest } from "../functions/image-proxy";

// --- Mock Cloudflare context ---

function createMockContext(urlStr: string, method = "GET") {
  const request = new Request(urlStr, { method });
  const env = {
    ASSETS: {} as unknown as Fetcher,
  };

  return {
    request,
    env,
    params: {},
    functionPath: "/image-proxy",
    waitUntil: () => {},
    passThroughOnException: () => {},
    next: () => Promise.resolve(new Response()),
    data: {},
  } as unknown as Parameters<typeof onRequest>[0];
}

describe("Image proxy", () => {
  it("rejects non-Liquipedia URLs with 403", async () => {
    const ctx = createMockContext(
      "https://example.com/image-proxy?url=https://evil.com/image.png"
    );
    const resp = await onRequest(ctx);
    expect(resp.status).toBe(403);
    const body = await resp.text();
    expect(body).toContain("Liquipedia");
  });

  it("returns 400 when url parameter is missing", async () => {
    const ctx = createMockContext("https://example.com/image-proxy");
    const resp = await onRequest(ctx);
    expect(resp.status).toBe(400);
    const body = await resp.text();
    expect(body).toContain("url");
  });
});
