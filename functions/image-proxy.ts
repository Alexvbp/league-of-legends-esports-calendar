/**
 * Image proxy to bypass Liquipedia hotlink protection.
 *
 * Usage: /image-proxy?url=https://liquipedia.net/commons/images/...
 */

interface Env {
  ASSETS: Fetcher;
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const url = new URL(context.request.url);
  const imageUrl = url.searchParams.get("url");

  // Validate image URL
  if (!imageUrl) {
    return new Response("Missing 'url' parameter", { status: 400 });
  }

  // Only allow Liquipedia images
  if (!imageUrl.startsWith("https://liquipedia.net/")) {
    return new Response("Only Liquipedia images are allowed", { status: 403 });
  }

  try {
    // Fetch the image from Liquipedia
    const response = await fetch(imageUrl, {
      headers: {
        "User-Agent": "EsportsCalendarBot/2.0",
        // Don't send Referer header
      },
    });

    if (!response.ok) {
      return new Response("Failed to fetch image", { status: response.status });
    }

    // Return the image with appropriate headers
    return new Response(response.body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("Content-Type") || "image/png",
        "Cache-Control": "public, max-age=86400", // Cache for 24 hours
        "Access-Control-Allow-Origin": "*",
      },
    });
  } catch (error) {
    console.error("Image proxy error:", error);
    return new Response("Internal server error", { status: 500 });
  }
};
