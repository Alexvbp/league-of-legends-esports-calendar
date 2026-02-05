/**
 * Cloudflare Pages Function — Serves team data from R2.
 *
 * Catches all /data/* requests and serves JSON files from R2 storage.
 * Falls back to ASSETS (static files) if the object isn't found in R2.
 */

interface Env {
  DATA_BUCKET: R2Bucket;
  ASSETS: Fetcher;
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const url = new URL(context.request.url);
  // Extract the path after /data/ (e.g. "teams.json", "fnatic.json")
  const pathSegments = context.params.path;
  const key = Array.isArray(pathSegments)
    ? pathSegments.join("/")
    : pathSegments;

  if (!key) {
    return new Response("Not found", { status: 404 });
  }

  // Try R2 first
  const object = await context.env.DATA_BUCKET.get(key);
  if (object) {
    return new Response(object.body, {
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "public, max-age=300",
        "Access-Control-Allow-Origin": "*",
      },
    });
  }

  // Fall back to static assets (for leagues.json or during migration)
  const assetUrl = new URL(`/data/${key}`, url.origin);
  return context.env.ASSETS.fetch(assetUrl.toString());
};
