// The InfraAtlas API proxy: routes /api/* and /mcp on the site's domain to the backend's
// Lambda Function URL, adds the shared secret (the Lambda refuses requests without it when
// REQUIRE_PROXY=true), applies the rate-limiting binding to questions first, and returns the
// response body as a stream so Server-Sent Events arrive one by one.

interface RateLimit {
  limit(options: { key: string }): Promise<{ success: boolean }>;
}

export interface Env {
  FUNCTION_URL: string;
  PROXY_SECRET: string;
  ASK_LIMIT: RateLimit;
}

const json = (status: number, body: unknown): Response =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    if (!path.startsWith("/api/") && path !== "/mcp" && !path.startsWith("/mcp/")) {
      return json(404, { detail: "Not Found" });
    }
    const ip = request.headers.get("cf-connecting-ip") ?? "unknown";
    if (path === "/api/ask" && request.method === "POST") {
      const { success } = await env.ASK_LIMIT.limit({ key: ip });
      if (!success) return json(429, { detail: "too many questions from this address; try again in a minute" });
    }
    const target = new URL(path + url.search, env.FUNCTION_URL);
    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.set("x-atlas-proxy", env.PROXY_SECRET);
    headers.set("x-forwarded-for", ip);
    const upstream = await fetch(target.toString(), {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
      redirect: "manual",
    });
    // a new Response around the same body stream: nothing is buffered
    const out = new Headers(upstream.headers);
    if (out.get("content-type")?.startsWith("text/event-stream")) out.set("cache-control", "no-cache, no-transform");
    return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: out });
  },
};
