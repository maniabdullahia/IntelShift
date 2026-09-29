import axios from "axios";

/* ────────────────────────────────────────────────────────────────
   Provider-agnostic web search.

   Used to ground competitor suggestions in REAL URLs instead of
   guessing domains. Configure via env:

     SEARCH_PROVIDER = ddg | brave | serpapi | google
     (default: auto — a paid provider if its key is set, else DDG)

     BRAVE_API_KEY      (for brave)
     SERPAPI_KEY        (for serpapi)
     GOOGLE_CSE_KEY + GOOGLE_CSE_ID   (for google programmable search)

   "ddg" (DuckDuckGo HTML) needs NO key and is the free default. It's an
   unofficial endpoint, so it can rate-limit — fine for onboarding volume,
   and callers fall back to the model's domain when a lookup returns [].
──────────────────────────────────────────────────────────────── */

const BROWSER_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";

// Resolve the active provider. Honor SEARCH_PROVIDER when its backing is set;
// otherwise auto-pick SearXNG (if SEARXNG_URL is set) → a paid provider whose
// key exists → keyless DuckDuckGo, so search ALWAYS works out of the box.
function provider() {
  const p = (process.env.SEARCH_PROVIDER || "").trim().toLowerCase();
  if (p === "searxng" && process.env.SEARXNG_URL) return "searxng";
  if (p === "brave" && process.env.BRAVE_API_KEY) return "brave";
  if (p === "serpapi" && process.env.SERPAPI_KEY) return "serpapi";
  if (p === "google" && process.env.GOOGLE_CSE_KEY && process.env.GOOGLE_CSE_ID) return "google";
  if (p === "ddg") return "ddg";

  if (process.env.SEARXNG_URL) return "searxng";
  if (process.env.BRAVE_API_KEY) return "brave";
  if (process.env.SERPAPI_KEY) return "serpapi";
  if (process.env.GOOGLE_CSE_KEY && process.env.GOOGLE_CSE_ID) return "google";
  return "ddg";
}

// Search is always available now (DDG needs no key).
export function searchConfigured() {
  return true;
}

/**
 * Run a web search. Returns [{ title, url, description }].
 * @param {string} query
 * @param {{count?: number, country?: string}} opts  country = ISO-2 (e.g. "PK")
 */
let _loggedProvider = false;
export async function webSearch(query, { count = 8, country } = {}) {
  if (!query) return [];
  const active = provider();
  // One-time visibility into which provider actually resolved, so a mis-set env
  // (or a server that wasn't restarted) is obvious instead of silently using DDG.
  if (!_loggedProvider) {
    _loggedProvider = true;
    console.log(
      `🔎 [webSearch] active provider=${active} | ` +
      `SEARCH_PROVIDER=${process.env.SEARCH_PROVIDER || "(unset)"} ` +
      `SEARXNG_URL=${process.env.SEARXNG_URL || "(unset)"}`
    );
  }
  try {
    switch (active) {
      case "searxng":
        return await searxngSearch(query, count, country);
      case "brave":
        return await braveSearch(query, count, country);
      case "serpapi":
        return await serpApiSearch(query, count, country);
      case "google":
        return await googleCseSearch(query, count, country);
      case "ddg":
      default:
        return await ddgSearch(query, count, country);
    }
  } catch (err) {
    console.error(`webSearch(${active}) error:`, err?.response?.status || err?.message || err);
    // SearXNG down/unreachable → fall back to keyless DDG so suggestions still work.
    if (active === "searxng") {
      try {
        return await ddgSearch(query, count, country);
      } catch {
        /* give up */
      }
    }
    return [];
  }
}

// SearXNG (self-hosted metasearch, no key). Set SEARXNG_URL to the instance base,
// e.g. http://localhost:8080. Requires JSON format enabled and the limiter off
// (search.formats: [html, json]  +  server.limiter: false) in settings.yml.
async function searxngSearch(query, count) {
  const base = String(process.env.SEARXNG_URL || "").replace(/\/+$/, "");
  // Send only what a plain browser/curl request sends. Adding `language` (or a
  // region locale) makes some SearXNG engines drop out and return an empty set,
  // which is exactly the "200 but 0 results" we were seeing. The query already
  // carries the region (e.g. "… Pakistan"), so nothing is lost.
  const res = await axios.get(`${base}/search`, {
    params: { q: query, format: "json" },
    headers: { "User-Agent": BROWSER_UA, Accept: "application/json" },
    timeout: 20000,
    validateStatus: () => true,
  });
  if (res.status !== 200 || !res.data || typeof res.data !== "object") {
    console.error(
      `searxng: status=${res.status} — check SEARXNG_URL, JSON format enabled, and limiter off`
    );
    throw new Error(`searxng status ${res.status}`);
  }
  const results = Array.isArray(res.data.results) ? res.data.results : [];
  if (!results.length) {
    const dead = (res.data.unresponsive_engines || [])
      .map((e) => (Array.isArray(e) ? e.join(": ") : e))
      .join(", ");
    console.log(`  [searxng] 0 results — unresponsive engines: ${dead || "none reported"}`);
  } else {
    console.log(`  [searxng] results=${results.length} q="${String(query).slice(0, 60)}"`);
  }
  return results.slice(0, count).map((r) => ({
    title: r.title,
    url: r.url,
    description: r.content,
  }));
}

// DuckDuckGo — no API key. Tries the lite endpoint first (most permissive for
// server-side requests), then the html endpoint via POST. Returns result URLs.
async function ddgSearch(query, count, country) {
  const kl = country ? `${country.toLowerCase()}-en` : undefined;

  const parse = (html) => {
    const out = [];
    const seen = new Set();
    const push = (u) => {
      if (!u) return;
      let url = u.startsWith("//") ? "https:" + u : u;
      if (!/^https?:\/\//i.test(url)) return;
      // ignore DDG's own/ad links
      if (/duckduckgo\.com|duckduckgo\.com\/y\.js/i.test(url)) return;
      if (seen.has(url)) return;
      seen.add(url);
      out.push({ title: "", url, description: "" });
    };
    let m;
    // 1) redirect links: ...uddg=<encoded real url>
    const redir = /[?&]uddg=([^"&]+)/g;
    while ((m = redir.exec(html)) && out.length < count) {
      try {
        push(decodeURIComponent(m[1]));
      } catch {
        /* skip */
      }
    }
    // 2) direct result anchors (lite + html layouts)
    if (out.length < count) {
      const direct = /<a[^>]+class="[^"]*result[^"]*"[^>]*href="([^"]+)"/g;
      while ((m = direct.exec(html)) && out.length < count) push(m[1]);
    }
    // 3) lite layout: result links are plain <a rel="nofollow" href="http...">
    if (!out.length) {
      const plain = /<a\b[^>]+href="(https?:\/\/[^"]+)"[^>]*>/g;
      while ((m = plain.exec(html)) && out.length < count) push(m[1]);
    }
    return out;
  };

  const headers = {
    "User-Agent": BROWSER_UA,
    Accept: "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    Origin: "https://lite.duckduckgo.com",
    Referer: "https://lite.duckduckgo.com/",
  };

  // Attempt 1 — lite endpoint (POST form).
  let html = "";
  try {
    const body = new URLSearchParams({ q: query, kl: kl || "" }).toString();
    const r = await axios.post("https://lite.duckduckgo.com/lite/", body, {
      headers,
      timeout: 12000,
      validateStatus: () => true,
    });
    html = typeof r.data === "string" ? r.data : "";
    const out = parse(html);
    if (out.length) return out;
    console.error(`ddg lite: status=${r.status} len=${html.length} parsed=0`);
  } catch (e) {
    console.error("ddg lite error:", e?.message || e);
  }

  // Attempt 2 — html endpoint (POST form).
  try {
    const body = new URLSearchParams({ q: query, kl: kl || "" }).toString();
    const r = await axios.post("https://html.duckduckgo.com/html/", body, {
      headers: { ...headers, Origin: "https://html.duckduckgo.com", Referer: "https://html.duckduckgo.com/" },
      timeout: 12000,
      validateStatus: () => true,
    });
    html = typeof r.data === "string" ? r.data : "";
    const out = parse(html);
    if (!out.length) console.error(`ddg html: status=${r.status} len=${html.length} parsed=0`);
    return out;
  } catch (e) {
    console.error("ddg html error:", e?.message || e);
    return [];
  }
}

async function braveSearch(query, count, country) {
  const res = await axios.get("https://api.search.brave.com/res/v1/web/search", {
    params: { q: query, count, country: country || undefined },
    headers: {
      "X-Subscription-Token": process.env.BRAVE_API_KEY,
      Accept: "application/json",
    },
    timeout: 10000,
  });
  const results = res.data?.web?.results || [];
  return results.map((r) => ({
    title: r.title,
    url: r.url,
    description: r.description,
  }));
}

async function serpApiSearch(query, count, country) {
  const res = await axios.get("https://serpapi.com/search.json", {
    params: {
      q: query,
      num: count,
      gl: country ? country.toLowerCase() : undefined,
      engine: "google",
      api_key: process.env.SERPAPI_KEY,
    },
    timeout: 10000,
  });
  const results = res.data?.organic_results || [];
  return results.map((r) => ({
    title: r.title,
    url: r.link,
    description: r.snippet,
  }));
}

async function googleCseSearch(query, count, country) {
  const res = await axios.get("https://www.googleapis.com/customsearch/v1", {
    params: {
      q: query,
      num: Math.min(count, 10),
      gl: country ? country.toLowerCase() : undefined,
      key: process.env.GOOGLE_CSE_KEY,
      cx: process.env.GOOGLE_CSE_ID,
    },
    timeout: 10000,
  });
  const results = res.data?.items || [];
  return results.map((r) => ({
    title: r.title,
    url: r.link,
    description: r.snippet,
  }));
}
