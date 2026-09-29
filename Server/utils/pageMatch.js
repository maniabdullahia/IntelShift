/*
|--------------------------------------------------------------------------
| PAGE MATCHING (server port of the onboarding auto-matcher)
|--------------------------------------------------------------------------
| Scores how likely a competitor page is the counterpart of one of the owner's
| pages, using URL-path signals. Mirrors the client logic in
| CompetitorPageSelection.jsx so backfilled mappings match what onboarding
| would have produced. Fuzzy on purpose — brands rarely use identical slugs.
*/

const prettyPath = (raw) => {
  try {
    const u = new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`);
    return u.pathname === "/" ? "/" : u.pathname.replace(/\/$/, "");
  } catch {
    return raw || "";
  }
};

export const isHomepagePath = (raw) => {
  const p = prettyPath(raw);
  return p === "/" || p === "";
};

const STOP_WORDS = new Set([
  "collections", "collection", "products", "product", "category",
  "categories", "shop", "pages", "page", "en", "us", "index", "html",
  "the", "and", "for", "our", "all",
]);

const stem = (word) => {
  if (word.length <= 3) return word;
  if (word.endsWith("ies")) return word.slice(0, -3) + "y";
  if (/(ch|sh|ss|x|z)es$/.test(word)) return word.slice(0, -2);
  if (word.endsWith("es") && word.length > 4) return word.slice(0, -1);
  if (word.endsWith("s") && !word.endsWith("ss")) return word.slice(0, -1);
  return word;
};

const diceSimilarity = (a, b) => {
  if (!a || !b) return 0;
  if (a === b) return 1;
  if (a.length < 2 || b.length < 2) return a === b ? 1 : 0;

  const bigrams = (str) => {
    const out = new Map();
    for (let i = 0; i < str.length - 1; i += 1) {
      const g = str.slice(i, i + 2);
      out.set(g, (out.get(g) || 0) + 1);
    }
    return out;
  };

  const aGrams = bigrams(a);
  const bGrams = bigrams(b);
  let intersection = 0;
  aGrams.forEach((count, gram) => {
    intersection += Math.min(count, bGrams.get(gram) || 0);
  });
  return (2 * intersection) / (a.length - 1 + (b.length - 1));
};

const tokenSimilarity = (a, b) => {
  const sa = stem(a);
  const sb = stem(b);
  if (sa === sb) return 1;
  return diceSimilarity(sa, sb);
};

const tokenize = (raw) =>
  String(prettyPath(raw))
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length > 1);

const meaningful = (tokens) => {
  const kept = tokens.filter((t) => !STOP_WORDS.has(t));
  return kept.length > 0 ? kept : tokens;
};

const directionalSim = (from, to) => {
  if (from.length === 0 || to.length === 0) return 0;
  const total = from.reduce((sum, token) => {
    let best = 0;
    to.forEach((other) => {
      const sim = tokenSimilarity(token, other);
      if (sim > best) best = sim;
    });
    return sum + best;
  }, 0);
  return total / from.length;
};

const PAGE_TYPE_PATTERNS = [
  ["pricing", ["pricing", "plans", "subscribe", "package"]],
  ["collection", ["collection", "categor", "shop", "catalog", "range"]],
  ["product", ["product", "/p/", "item", "sku"]],
  ["features", ["feature", "platform", "solution", "capabilit"]],
  ["services", ["service", "what-we-do", "offering"]],
  ["about", ["about", "company", "our-story", "who-we-are"]],
  ["blog", ["blog", "article", "news", "insight", "journal"]],
  ["contact", ["contact", "support", "help", "get-in-touch"]],
  ["case", ["case-stud", "customer", "success", "portfolio"]],
];

const inferTypeKey = (raw) => {
  const path = String(prettyPath(raw)).toLowerCase();
  if (path === "/" || path === "") return "home";
  for (const [key, patterns] of PAGE_TYPE_PATTERNS) {
    if (patterns.some((p) => path.includes(p))) return key;
  }
  return "other";
};

/** 0..1 confidence that competitorUrl is the counterpart of ownerUrl. */
export const scoreMatch = (ownerUrl, competitorUrl) => {
  const aTokens = meaningful(tokenize(ownerUrl));
  const bTokens = meaningful(tokenize(competitorUrl));

  const tokenSim = (directionalSim(aTokens, bTokens) + directionalSim(bTokens, aTokens)) / 2;
  const slugSim = diceSimilarity(aTokens.join(""), bTokens.join(""));
  const leafSim = tokenSimilarity(
    aTokens[aTokens.length - 1] || "",
    bTokens[bTokens.length - 1] || ""
  );
  const typeA = inferTypeKey(ownerUrl);
  const typeB = inferTypeKey(competitorUrl);
  const typeMatch = typeA === typeB && typeA !== "other" ? 1 : 0;

  const score = tokenSim * 0.4 + slugSim * 0.15 + leafSim * 0.2 + typeMatch * 0.25;
  return Math.max(0, Math.min(1, score));
};

// Confident enough to auto-apply during backfill (matches onboarding's pre-fill).
export const AUTOFILL_THRESHOLD = 0.5;

/**
 * Greedy best-match of competitor pages to owner pages.
 * @param {string[]} ownerUrls
 * @param {string[]} competitorUrls
 * @returns {Map<string,string>} competitorUrl -> ownerUrl (confident matches only)
 */
export const matchCompetitorPages = (ownerUrls, competitorUrls) => {
  const result = new Map();
  const ownerNonHome = ownerUrls.filter((u) => !isHomepagePath(u));
  const ownerHome = ownerUrls.find((u) => isHomepagePath(u));

  for (const compUrl of competitorUrls) {
    if (isHomepagePath(compUrl)) {
      if (ownerHome) result.set(compUrl, ownerHome);
      continue;
    }
    let best = null;
    let bestScore = 0;
    for (const ownerUrl of ownerNonHome) {
      const s = scoreMatch(ownerUrl, compUrl);
      if (s > bestScore) {
        bestScore = s;
        best = ownerUrl;
      }
    }
    if (best && bestScore >= AUTOFILL_THRESHOLD) result.set(compUrl, best);
  }
  return result;
};
