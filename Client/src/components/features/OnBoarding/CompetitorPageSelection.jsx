import { useEffect, useMemo, useRef, useState } from "react";
import {
  Home,
  Lock,
  Link2,
  ListTree,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  CircleDashed,
  MinusCircle,
  RotateCcw,
  ChevronDown,
  ExternalLink,
  X as XIcon,
} from "lucide-react";

import TreeNode from "../../ui/TreeNode";
import ManualPageUrlPicker from "../../shared/ManualPageUrlPicker";
import SearchSelect from "../../shared/SearchSelect";
import PageDiscoveryLoader from "../Loadings/PageDiscoveryLoader";

import { createTreeNode } from "../../../api/utils.api";
import { capProductPages, countProductPages } from "../../../utils/treeStats";

// Above this many products, we don't render a competitor catalog — browsing a
// giant list to find one match hangs the picker and is worse UX than just pasting
// the equivalent URL. At or below it, the catalog is small enough to browse.
const COMPETITOR_CATALOG_MAX = 100;
import useAuthStore from "../../../store/auth.store";

/* ────────────────────────────────────────────────────────────────
   IntelShift — Onboarding: pair competitor pages to your pages.

   Each page the user tracks gets one row, colour-coded by state:
     green  = matched to a competitor page
     amber  = still to do
     red    = deliberately skipped (no equivalent on this site)

   The colour carries the meaning so the copy can stay short. Three
   ways to fill a row — the recommended dropdown, the TreeNode
   browser, or a pasted URL — kept as icon buttons to reduce noise.
──────────────────────────────────────────────────────────────── */

/* ── URL helpers ───────────────────────────────────────────── */

/* Guarantees a scheme before the value is ever handed to new URL().
   A bare "sivanna.com.pk" throws there, which previously left the
   crawl with a broken origin. */
const withProtocol = (value) => {
  const raw = (value || "").trim();
  if (!raw) return raw;

  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("//")) return "https:" + raw;
  if (!raw.includes(".")) return raw;

  return "https://" + raw.replace(/^\/+/, "");
};

const safeOrigin = (raw) => {
  const normalised = withProtocol(raw);
  try {
    return new URL(normalised).origin;
  } catch {
    return normalised || "";
  }
};

const toUrlString = (page) =>
  typeof page === "string" ? page : page?.url || page?.href || page?.link || "";

const prettyPath = (raw) => {
  try {
    const u = new URL(raw);
    return u.pathname === "/" ? "/" : u.pathname.replace(/\/$/, "");
  } catch {
    return raw || "";
  }
};

/* Assets and non-page links we never want to offer as a comparison target. */
const ASSET_RE = /\.(css|js|mjs|png|jpe?g|gif|svg|webp|avif|ico|woff2?|ttf|eot|pdf|zip|mp4|webm|xml|json|txt)(\?|#|$)/i;

/* Resolve anything the crawl gives us (absolute, root-relative, or bare
   path) into an absolute same-origin URL, or null if it is not usable. */
const toAbsolute = (value, origin) => {
  if (typeof value !== "string") return null;

  const raw = value.trim();
  if (!raw || raw.startsWith("#") || raw.startsWith("mailto:")) return null;
  if (raw.startsWith("tel:") || raw.startsWith("javascript:")) return null;

  let resolved;
  try {
    resolved = new URL(raw, origin || undefined);
  } catch {
    return null;
  }

  if (resolved.protocol !== "http:" && resolved.protocol !== "https:") {
    return null;
  }

  // Same-origin only. This is the guard that keeps CDN assets, social
  // links and third-party scripts out of the picker.
  if (origin && resolved.origin !== origin) return null;
  if (ASSET_RE.test(resolved.pathname)) return null;
  // Synthetic tree-only group headers (e.g. /collections/grp-eyes) carry a path
  // for NESTING but aren't real pages — they 404. Never surface them as options.
  if (/\/grp-/i.test(resolved.pathname)) return null;

  resolved.hash = "";
  const out = resolved.toString().replace(/\/$/, "");
  return out || null;
};

/* ── Page-type inference ───────────────────────────────────────
   Drives both the recommendations and the mismatch warnings.
   Heuristic only, so it nudges but never blocks.
──────────────────────────────────────────────────────────────── */

const PAGE_TYPES = [
  { key: "pricing", label: "Pricing", patterns: ["pricing", "plans", "subscribe", "package"] },
  { key: "collection", label: "Collection", patterns: ["collection", "categor", "shop", "catalog", "range"] },
  { key: "product", label: "Product", patterns: ["product", "/p/", "item", "sku"] },
  { key: "features", label: "Features", patterns: ["feature", "platform", "solution", "capabilit"] },
  { key: "services", label: "Services", patterns: ["service", "what-we-do", "offering"] },
  { key: "about", label: "About", patterns: ["about", "company", "our-story", "who-we-are"] },
  { key: "blog", label: "Blog", patterns: ["blog", "article", "news", "insight", "journal"] },
  { key: "contact", label: "Contact", patterns: ["contact", "support", "help", "get-in-touch"] },
  { key: "case", label: "Case studies", patterns: ["case-stud", "customer", "success", "portfolio"] },
];

const inferType = (raw) => {
  const path = String(prettyPath(raw)).toLowerCase();
  if (path === "/" || path === "") return { key: "home", label: "Homepage" };
  for (const type of PAGE_TYPES) {
    if (type.patterns.some((p) => path.includes(p))) return type;
  }
  return { key: "other", label: "Other" };
};

/* ── Recommendation scoring ────────────────────────────────────
   0..1 confidence that a competitor URL is the counterpart of one
   of the user's pages.

   Matching is fuzzy on purpose. Two brands rarely use identical
   slugs — /collections/foundation vs /collections/foundations, or
   /about-us vs /company/about — so exact token equality misses the
   obvious pairs. We combine four signals:

     tokenSim  best-match alignment between slug words (stemmed,
               then character-similarity for near misses)
     slugSim   similarity of the whole meaningful path
     leafSim   similarity of the last segment, which usually carries
               the actual subject of the page
     typeMatch both pages inferred as the same kind of page

   Type agreement alone is capped below the auto-fill threshold, so
   a page is never pre-filled on "they are both category pages".
──────────────────────────────────────────────────────────────── */

const STOP_WORDS = new Set([
  "collections", "collection", "products", "product", "category",
  "categories", "shop", "pages", "page", "en", "us", "index", "html",
  "the", "and", "for", "our", "all",
]);

/* Crude but effective singulariser — enough to fold the plural
   variations brands use in slugs. */
const stem = (word) => {
  if (word.length <= 3) return word;
  if (word.endsWith("ies")) return word.slice(0, -3) + "y";
  if (/(ch|sh|ss|x|z)es$/.test(word)) return word.slice(0, -2);
  if (word.endsWith("es") && word.length > 4) return word.slice(0, -1);
  if (word.endsWith("s") && !word.endsWith("ss")) return word.slice(0, -1);
  return word;
};

/* Sørensen–Dice over character bigrams: forgiving of small spelling
   and suffix differences without matching unrelated words. */
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
  // If a path is nothing but structural words, keep them rather than
  // comparing two empty sets.
  return kept.length > 0 ? kept : tokens;
};

/* Generic commerce / SEO filler stripped from page NAMES before matching, so a
   title like "Buy Stylish Men Shirts Online in Pakistan" reduces to the words
   that actually identify the page ("men", "shirts"). Category words (men, women,
   kids, eyes, lips, foundation, …) are deliberately NOT here — they're signal. */
const NAME_FILLER = new Set([
  "buy", "shop", "online", "best", "top", "store", "stores", "official",
  "price", "prices", "pricing", "cheap", "affordable", "premium", "original",
  "authentic", "genuine", "quality", "your", "with", "from", "into", "home",
  "delivery", "free", "deals", "deal", "offers", "offer", "sale", "new",
  "latest", "shopping", "checkout", "order", "get", "find", "explore",
  "discover", "range", "brand", "website", "site", "pakistan", "india", "uae",
  "usa", "uk", "the", "and", "for", "our", "all", "in", "at", "on", "of", "to",
]);

/* Tokenise a page name/title, drop filler + structural words, stem the rest. */
const cleanNameTokens = (name) =>
  String(name || "")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length > 1 && !NAME_FILLER.has(t) && !STOP_WORDS.has(t))
    .map(stem);

/* Symmetric best-match similarity between two cleaned name-token sets. */
const nameSim = (aTokens, bTokens) =>
  aTokens.length && bTokens.length
    ? (directionalSim(aTokens, bTokens) + directionalSim(bTokens, aTokens)) / 2
    : 0;

/* Short, display-friendly page name — trims whitespace and truncates the long
   SEO titles some stores use so they don't blow out a dropdown row. */
const shortName = (s) => {
  const t = String(s || "").trim().replace(/\s+/g, " ");
  if (!t) return "";
  return t.length > 44 ? t.slice(0, 43).trimEnd() + "…" : t;
};

/* Combined "Name — /path" text for a page, so both the human name and the URL
   are visible. Falls back to just the path when the name is missing or is
   effectively the same as the slug (no point repeating it). */
const namePathText = (name, url) => {
  const path = prettyPath(url);
  const n = shortName(name);
  if (!n) return path;
  const slug = path.replace(/[^a-z0-9]+/gi, "").toLowerCase();
  const nn = n.replace(/[^a-z0-9]+/gi, "").toLowerCase();
  return nn && nn !== slug ? `${n} — ${path}` : path;
};

/* Open a page in a new tab, safely. */
const openPage = (url) => {
  if (url) window.open(url, "_blank", "noopener,noreferrer");
};

/* Average best-match similarity in one direction. */
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

const scoreMatch = (yourUrl, candidateUrl, yourName, candidateName) => {
  const aTokens = meaningful(tokenize(yourUrl));
  const bTokens = meaningful(tokenize(candidateUrl));

  // Symmetric so neither a longer nor a shorter path is favoured.
  const tokenSim =
    (directionalSim(aTokens, bTokens) + directionalSim(bTokens, aTokens)) / 2;

  const slugSim = diceSimilarity(aTokens.join(""), bTokens.join(""));

  const leafSim = tokenSimilarity(
    aTokens[aTokens.length - 1] || "",
    bTokens[bTokens.length - 1] || ""
  );

  // Slug lexical signal (0..0.75) — the original weighting, kept intact.
  const slugLexical = tokenSim * 0.4 + slugSim * 0.15 + leafSim * 0.2;

  // Name lexical signal — two brands often share the human-readable category
  // name ("Eye Makeup" ↔ "Eyes", "Men's Shirts" ↔ "Shirts for Men") even when
  // the slugs diverge. Filler words are stripped so SEO-bloated titles don't win
  // on noise. Scaled to the same 0..0.75 range as the slug signal.
  const nameLexical = nameSim(cleanNameTokens(yourName), cleanNameTokens(candidateName)) * 0.75;

  // Take whichever lexical signal is stronger: a solid match on EITHER the slug
  // or the name is a good pairing, and weakness on one side shouldn't drag it
  // down. When names are absent this collapses to the original slug-only score.
  const lexical = Math.max(slugLexical, nameLexical);

  const typeA = inferType(yourUrl);
  const typeB = inferType(candidateUrl);
  const typeMatch = typeA.key === typeB.key && typeA.key !== "other" ? 1 : 0;

  const score = lexical + typeMatch * 0.25;

  return Math.max(0, Math.min(1, score));
};

const SUGGEST_THRESHOLD = 0.2; // show as an alternative
const AUTOFILL_THRESHOLD = 0.5; // confident enough to pre-fill
/* A clear front-runner can be pre-filled below the absolute threshold. */
const AUTOFILL_LEAD_FLOOR = 0.35;
const AUTOFILL_LEAD_GAP = 0.15;

/* ── Extract pages from the crawl payload ──────────────────────
   The exact shape of createTreeNode's response is not guaranteed,
   so rather than assume one, walk the whole structure and collect
   every same-origin page URL we can find. Any string under a
   URL-ish key counts, as does any string that resolves to a
   same-origin page. Same-origin + asset filtering keeps it clean.
──────────────────────────────────────────────────────────────── */

const URL_KEYS = [
  "url", "href", "link", "loc", "path", "pathname",
  "fullUrl", "pageUrl", "address", "value",
];

const CONTAINER_KEYS = ["children", "nodes", "items", "pages", "child", "subpages"];

const collectPages = (root, origin) => {
  const found = new Map(); // url -> label
  const seen = new Set();

  const visit = (node, inheritedLabel) => {
    if (node == null) return;

    if (typeof node === "string") {
      const abs = toAbsolute(node, origin);
      if (abs && !found.has(abs)) found.set(abs, inheritedLabel || prettyPath(abs));
      return;
    }

    if (typeof node !== "object") return;

    // Guard against cycles in the payload
    if (seen.has(node)) return;
    seen.add(node);

    if (Array.isArray(node)) {
      node.forEach((child) => visit(child, inheritedLabel));
      return;
    }

    const label =
      node.title || node.name || node.label || node.text || inheritedLabel;

    // Explicit URL-ish keys first
    URL_KEYS.forEach((key) => {
      const abs = toAbsolute(node[key], origin);
      if (abs && !found.has(abs)) found.set(abs, label || prettyPath(abs));
    });

    // Then descend into everything else
    Object.keys(node).forEach((key) => {
      const value = node[key];
      if (value && typeof value === "object") {
        visit(value, CONTAINER_KEYS.includes(key) ? label : label);
      } else if (typeof value === "string" && !URL_KEYS.includes(key)) {
        // Catch path-like strings stored under unexpected key names
        if (value.startsWith("/") || value.startsWith("http")) {
          const abs = toAbsolute(value, origin);
          if (abs && !found.has(abs)) found.set(abs, label || prettyPath(abs));
        }
      }
    });
  };

  visit(root, null);

  return Array.from(found.entries())
    .map(([url, label]) => ({ url, label }))
    .sort((a, b) => prettyPath(a.url).localeCompare(prettyPath(b.url)));
};

/* ── "No equivalent" sentinel ──────────────────────────────────
   A page the user tracks may simply not exist on a given
   competitor's site — they may not sell that category, or may not
   publish pricing at all. That is a legitimate outcome and a real
   finding in its own right, not an error, so the user declares it
   explicitly rather than being forced to change their own page
   (which would also break pairing for every other competitor).
──────────────────────────────────────────────────────────────── */

const NO_EQUIVALENT = "__no_equivalent__";
const isNone = (value) => value === NO_EQUIVALENT;

/* ── Crawl cache ───────────────────────────────────────────────
   Keyed by origin, scoped to this page load. Promises are cached
   so two rapid mounts share one request. Browser-tab scoped, so
   nothing is ever shared between different users.
──────────────────────────────────────────────────────────────── */

const treeCache = new Map();

const fetchTree = (origin) => {
  if (treeCache.has(origin)) return treeCache.get(origin);

  const pending = createTreeNode(origin).catch((error) => {
    treeCache.delete(origin);
    throw error;
  });

  treeCache.set(origin, pending);
  return pending;
};

/* ── Responsive rules ──────────────────────────────────────────
   Inline styles cannot express media queries, so the parts that
   have to reflow on a phone are driven by these classes instead.
   Breakpoint is 640px.
──────────────────────────────────────────────────────────────── */

const matchPagesCss = `
.is-mp-notes{display:flex;flex-direction:column;gap:10px;padding:14px 16px;margin-bottom:14px;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius)}
.is-mp-notes > *{margin:0 !important}
.is-mp-controls{display:flex;align-items:center;gap:6px;padding-left:24px}
.is-mp-controls .is-mp-field{flex:1;min-width:0}
.is-mp-actions{display:flex;align-items:center;gap:6px;flex-shrink:0}
.is-mp-summary{display:flex;align-items:center;flex-wrap:wrap;gap:14px;margin-bottom:10px}
.is-mp-rowhead{display:flex;align-items:center;gap:8px;min-width:0}
@media (max-width:640px){
  .is-mp-controls{flex-direction:column;align-items:stretch;gap:8px;padding-left:0}
  /* Action icons sit in their own left-aligned row under the field, lining up
     with the dropdown and the suggested chips instead of floating right. */
  .is-mp-actions{justify-content:flex-start;gap:8px}
  .is-mp-notes{padding:12px 13px}
  .is-mp-rowhead{flex-wrap:wrap;gap:6px}
  .is-mp-indent{margin-left:0 !important}
  .is-mp-summary{gap:10px}
  .is-mp-count{margin-left:0 !important}
}
`;

/* ── Status system ─────────────────────────────────────────────
   One place to change how each state looks.

   NOTE ON "skipped": red normally signals an error, but skipping a
   page is a deliberate, valid choice — and a real finding. So it is
   drawn with a light tint and a dashed border, which reads as
   "intentionally excluded" rather than "something broke". To make it
   a plain neutral instead, swap the three colour values below for
   var(--text-light) / var(--bg) / var(--border).
──────────────────────────────────────────────────────────────── */

const STATUS = {
  matched: {
    label: "Matched",
    fg: "#1aaa63",
    tint: "rgba(38,222,129,0.08)",
    edge: "rgba(38,222,129,0.28)",
    bar: "var(--success)",
    dash: "solid",
  },
  pending: {
    label: "To do",
    fg: "#b88a00",
    tint: "rgba(254,211,48,0.13)",
    edge: "rgba(254,211,48,0.4)",
    bar: "var(--warning)",
    dash: "solid",
  },
  skipped: {
    label: "Skipped",
    fg: "var(--danger)",
    tint: "rgba(252,92,101,0.07)",
    edge: "rgba(252,92,101,0.32)",
    bar: "var(--danger)",
    dash: "dashed",
  },
};

const StatusIcon = ({ status, size = 16 }) => {
  const tone = STATUS[status];
  const common = { size, style: { color: tone.fg, flexShrink: 0 } };

  if (status === "matched") return <CheckCircle2 {...common} />;
  if (status === "skipped") return <MinusCircle {...common} />;
  return <CircleDashed {...common} />;
};

/* Mirrors .badge on the marketing site: uppercase, 11px, 800, with
   the same tinted-fill + matching-border treatment. */
const Pill = ({ children, fg, bg, edge, title }) => (
  <span
    title={title}
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      fontSize: 11,
      fontWeight: 800,
      letterSpacing: "0.06em",
      textTransform: "uppercase",
      padding: "5px 12px",
      borderRadius: 999,
      whiteSpace: "nowrap",
      flexShrink: 0,
      color: fg || "var(--text-light)",
      background: bg || "rgba(78,205,196,0.12)",
      border: "1px solid " + (edge || "rgba(78,205,196,0.2)"),
    }}
  >
    {children}
  </span>
);

/* Icon-only control. Three labelled buttons per row was too busy, so
   the actions are icons with tooltips and accessible names. */
const IconButton = ({ label, active, onClick, children, tone }) => (
  <button
    type="button"
    onClick={onClick}
    title={label}
    aria-label={label}
    style={{
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: 34,
      height: 34,
      flexShrink: 0,
      borderRadius: "var(--radius-sm)",
      cursor: "pointer",
      transition: "all 0.15s ease",
      background: active ? "var(--glow-teal)" : "var(--bg)",
      color: active ? "var(--secondary-dark)" : tone || "var(--text-light)",
      border:
        "1px solid " +
        (active
          ? "color-mix(in srgb, var(--secondary) 35%, transparent)"
          : "var(--border)"),
    }}
  >
    {children}
  </button>
);

const fieldStyle = {
  width: "100%",
  padding: "9px 11px",
  fontSize: 13,
  fontFamily: "inherit",
  color: "var(--text)",
  background: "var(--card)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-sm)",
  outline: "none",
};

/* The site's .eyebrow: teal, uppercase, tracked out. */
const captionStyle = {
  display: "inline-block",
  margin: 0,
  fontSize: 12,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "var(--secondary-dark)",
};

/* ── Component ─────────────────────────────────────────────── */

const CompetitorPageSelection = ({
  url,
  onPageSelection,
  isValid,
  // Optional — enables guided 1:1 mapping. Falls back to free selection
  // when not provided, so existing wiring keeps working.
  workspacePages = [],
  // { [url]: name } for the owner's pages, so matching can use real page names
  // and not just URL slugs. Optional — matching degrades to slug-only without it.
  workspaceTitles = {},
  workspaceName,
  competitorName,
  onMappingChange,
  // Supplied by ProcessStepper — every step stays mounted, so defer
  // the crawl until this step is actually on screen.
  isActive = true,
  // Controlled mode. When onboarding collects several competitors the
  // parent owns each one's pairings, so switching between competitors
  // never leaks one's choices into another.
  mappingValue,
  onMappingValueChange,
  competitorIndex = 0,
  competitorTotal = 1,
  // Owner-driven: only surface competitor product pages if the user tracks at
  // least one product on their own site. Otherwise products stay hidden here
  // (keeps the mapping dropdowns fast and clean for the collections-only case).
  ownerHasProducts = false,
}) => {
  const [treeData, setTreeData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [phase, setPhase] = useState("discovering"); // discovering → structuring
  // { total, large } — competitor product count and whether it's too big to browse.
  const [productCatalog, setProductCatalog] = useState({ total: 0, large: false });

  const [internalMapping, setInternalMapping] = useState({});

  const isControlled = mappingValue !== undefined;
  const mapping = isControlled ? mappingValue : internalMapping;

  const mappingRef = useRef(mapping);
  mappingRef.current = mapping;

  const setMapping = (updater) => {
    const next =
      typeof updater === "function" ? updater(mappingRef.current) : updater;

    if (isControlled) onMappingValueChange?.(next);
    else setInternalMapping(next);
  };

  const [autoFilled, setAutoFilled] = useState({});
  const [manualMode, setManualMode] = useState({});
  const [pickerRow, setPickerRow] = useState(null);
  const [showHelp, setShowHelp] = useState(false);

  // Fallback (free-selection) mode
  const [treeSelectedPages, setTreeSelectedPages] = useState([]);
  const [manualUrls, setManualUrls] = useState([]);

  const user = useAuthStore((state) => state.user);
  const limits = user?.subscription?.planId?.limits?.pagesPerCompetitor || 2;

  const onPageSelectionRef = useRef(onPageSelection);
  onPageSelectionRef.current = onPageSelection;
  const onMappingChangeRef = useRef(onMappingChange);
  onMappingChangeRef.current = onMappingChange;
  const autoAppliedRef = useRef(false);
  // "<origin>::<ownerHasProducts>" we've already crawled — so re-entering this step
  // (navigating back and forward) doesn't needlessly re-fetch and flicker the tree.
  const loadedKeyRef = useRef(null);

  const competitorOrigin = useMemo(() => safeOrigin(url), [url]);

  useEffect(() => {
    autoAppliedRef.current = false;
  }, [competitorOrigin]);

  const yourPages = useMemo(
    () =>
      (workspacePages || [])
        .map(toUrlString)
        .filter(Boolean)
        .filter((p) => prettyPath(p) !== "/"),
    [workspacePages]
  );

  const guided = yourPages.length > 0;

  useEffect(() => {
    if (!isActive || !url) return undefined;

    const loadKey = `${safeOrigin(url)}::${ownerHasProducts ? 1 : 0}`;
    // Same site + same product context already loaded — the user just came back to
    // this step. Keep the tree (and mapping) as-is instead of re-crawling.
    if (loadedKeyRef.current === loadKey) return undefined;

    let cancelled = false;

    let structureTimer;
    const fetchTreeData = async () => {
      try {
        setLoading(true);
        setPhase("discovering");
        const data = await fetchTree(safeOrigin(url));
        if (cancelled) return;
        loadedKeyRef.current = loadKey; // mark loaded so re-entry won't refetch
        // Size-gate the competitor's products:
        //   • owner tracks no products        → show none (collections only).
        //   • owner has products, catalog ≤100 → show the whole catalog (browsable).
        //   • owner has products, catalog >100 → show none; the user pastes/searches
        //     each product's matching URL instead (no hang, more accurate).
        const total = countProductPages(data);
        const largeCatalog = total > COMPETITOR_CATALOG_MAX;
        setProductCatalog({ total, large: largeCatalog });
        const productCap = ownerHasProducts && !largeCatalog ? total : 0;
        setTreeData(capProductPages(data, productCap));
        setPhase("structuring");
        structureTimer = setTimeout(() => {
          if (!cancelled) setLoading(false);
        }, 900);
      } catch (error) {
        console.error("Error fetching tree data:", error);
        if (!cancelled) setLoading(false);
      }
    };

    fetchTreeData();

    return () => {
      cancelled = true;
      if (structureTimer) clearTimeout(structureTimer);
    };
  }, [isActive, url, ownerHasProducts]);

  const options = useMemo(
    () => collectPages(treeData, competitorOrigin),
    [treeData, competitorOrigin]
  );

  // A very large discovered catalog is the mega-retailer / marketplace signal.
  const oversized = options.length > 300;

  useEffect(() => {
    if (!loading && treeData && options.length === 0) {
      console.warn(
        "[IntelShift] Could not extract page URLs from the crawl payload. " +
          "Use Browse or Paste URL to pair pages. Payload sample:",
        treeData
      );
    }
  }, [loading, treeData, options.length]);

  const suggestions = useMemo(() => {
    const out = {};
    yourPages.forEach((p) => {
      const yourName = workspaceTitles[p];
      out[p] = options
        .map((o) => ({ ...o, score: scoreMatch(p, o.url, yourName, o.label) }))
        .filter((o) => o.score >= SUGGEST_THRESHOLD)
        .sort((a, b) => b.score - a.score)
        .slice(0, 3);
    });
    return out;
  }, [yourPages, options, workspaceTitles]);

  /* Pre-fill confident matches once, when the crawl lands. */
  useEffect(() => {
    if (!guided || autoAppliedRef.current || options.length === 0) return;

    const next = {};
    const taken = new Set();

    yourPages.forEach((p) => {
      if (mappingRef.current[p]) return; // never override an explicit choice

      const ranked = (suggestions[p] || []).filter((s) => !taken.has(s.url));
      const top = ranked[0];
      const runnerUp = ranked[1];

      const confident = top && top.score >= AUTOFILL_THRESHOLD;
      const clearWinner =
        top &&
        top.score >= AUTOFILL_LEAD_FLOOR &&
        (!runnerUp || top.score - runnerUp.score >= AUTOFILL_LEAD_GAP);

      const best = confident || clearWinner ? top : null;

      if (best) {
        next[p] = best.url;
        taken.add(best.url);
      }
    });

    autoAppliedRef.current = true;

    if (Object.keys(next).length > 0) {
      setMapping((prev) => ({ ...next, ...prev }));
      setAutoFilled(next);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guided, options, yourPages, suggestions]);

  const guidedSelection = useMemo(
    () => yourPages.map((p) => mapping[p]).filter((v) => v && !isNone(v)),
    [yourPages, mapping]
  );

  const freeSelection = useMemo(
    () => [...treeSelectedPages, ...manualUrls],
    [treeSelectedPages, manualUrls]
  );

  const selection = guided ? guidedSelection : freeSelection;

  useEffect(() => {
    onPageSelectionRef.current?.(selection);
  }, [selection]);

  useEffect(() => {
    if (!guided) return;
    onMappingChangeRef.current?.(
      yourPages.map((p) => {
        const value = mapping[p];
        return {
          workspaceUrl: p,
          competitorUrl: value && !isNone(value) ? value : null,
          status: !value ? "pending" : isNone(value) ? "no_equivalent" : "matched",
        };
      })
    );
  }, [guided, yourPages, mapping]);

  /* ── Guards ──────────────────────────────────────────────── */

  // Inline rather than a Swal popup: this step is mounted from the start,
  // so an alert here would fire before the user has even reached it.
  if (!url) {
    return (
      <div style={{ color: "var(--text-light)", fontSize: 14 }}>
        Add the competitor&apos;s website URL in the previous step to match
        pages.
      </div>
    );
  }

  if (loading) return <PageDiscoveryLoader variant={phase === "structuring" ? "structuring" : "competitor"} />;

  /* ── Derived state ───────────────────────────────────────── */

  const statusOf = (page) => {
    const value = mapping[page];
    if (!value) return "pending";
    return isNone(value) ? "skipped" : "matched";
  };

  const totalRows = yourPages.length;
  const matchedCount = guidedSelection.length;
  const skippedCount = yourPages.filter((p) => isNone(mapping[p])).length;
  const resolvedCount = matchedCount + skippedCount;
  const pendingCount = totalRows - resolvedCount;

  const allResolved = guided ? resolvedCount === totalRows : true;
  const hasRealMatch = guided ? matchedCount > 0 : true;
  const canFinish = Boolean(isValid) && allResolved && hasRealMatch;
  const hasOptions = options.length > 0;
  const autoFilledCount = Object.keys(autoFilled).filter(
    (k) => mapping[k] === autoFilled[k]
  ).length;

  const setRow = (yourUrl, competitorUrl) => {
    setMapping((prev) => ({ ...prev, [yourUrl]: competitorUrl || undefined }));
    setAutoFilled((prev) => {
      if (!(yourUrl in prev)) return prev;
      const next = { ...prev };
      delete next[yourUrl];
      return next;
    });
  };

  const toggleNoEquivalent = (yourUrl) =>
    setMapping((prev) => ({
      ...prev,
      [yourUrl]: isNone(prev[yourUrl]) ? undefined : NO_EQUIVALENT,
    }));

  /* TreeNode hands back an array of URL strings. Take the last one picked
     so clicking a different page simply replaces the choice. */
  const handlePickerSelection = (yourUrl, selected) => {
    const list = Array.isArray(selected) ? selected : [selected];
    const picked = list.map(toUrlString).filter(Boolean).pop();
    if (!picked) return;
    setRow(yourUrl, picked);
    setPickerRow(null);
  };

  const usedElsewhere = (yourUrl, candidate) =>
    Object.entries(mapping).some(
      ([k, v]) => k !== yourUrl && v && !isNone(v) && v === candidate
    );

  const competitorLabel =
    competitorName || competitorOrigin.replace(/^https?:\/\//, "");

  /* ── Render ──────────────────────────────────────────────── */

  return (
    <div style={{ fontFamily: "var(--font-sans)" }}>
      <style>{matchPagesCss}</style>

      {/* ── Heading ───────────────────────────────────────────── */}
      {competitorTotal > 1 && (
        <p style={{ ...captionStyle, marginBottom: 6 }}>
          Competitor {competitorIndex + 1} of {competitorTotal}
        </p>
      )}

      <h2
        style={{
          fontSize: 20,
          fontWeight: 600,
          letterSpacing: "-0.025em",
          marginBottom: 6,
          color: "var(--primary)",
        }}
      >
        Match their pages to yours
      </h2>

      <p
        style={{
          fontSize: 14,
          color: "var(--text-light)",
          margin: "0 0 4px",
          lineHeight: 1.6,
        }}
      >
        Match each page to the one that does the same job on{" "}
        <strong style={{ color: "var(--text)" }}>{competitorLabel}</strong> — that&apos;s
        what makes the comparison sharp.
      </p>

      {oversized && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 10,
            padding: "0.75rem 1rem",
            margin: "0.75rem 0 0",
            background: "color-mix(in srgb, var(--danger, #dc2626) 7%, var(--card))",
            border: "1px solid color-mix(in srgb, var(--danger, #dc2626) 32%, transparent)",
            borderRadius: "var(--radius)",
          }}
        >
          <AlertTriangle
            size={15}
            style={{ color: "var(--danger, #dc2626)", marginTop: 1, flexShrink: 0 }}
          />
          <p style={{ margin: 0, fontSize: 12, lineHeight: 1.6, color: "var(--text)" }}>
            <strong>{competitorLabel} has a very large catalog ({options.length}+ pages).</strong>{" "}
            It looks like a marketplace or mega-retailer, which IntelShift doesn&apos;t
            fully support — pick just a few key pages, and expect a lighter comparison.
          </p>
        </div>
      )}

      {ownerHasProducts && productCatalog.large && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 10,
            padding: "0.75rem 1rem",
            margin: "0.75rem 0 0",
            background: "var(--bg)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
          }}
        >
          <Link2
            size={15}
            style={{ color: "var(--primary)", marginTop: 1, flexShrink: 0 }}
          />
          <p style={{ margin: 0, fontSize: 12, lineHeight: 1.6, color: "var(--text)" }}>
            <strong>{competitorLabel} carries {productCatalog.total.toLocaleString()}+ products</strong>{" "}
            — too many to browse here. For each product you track, paste or search{" "}
            their matching product&apos;s URL on the row below (their collection pages
            are still fully browsable).
          </p>
        </div>
      )}

      {/* Detail is available, but folded away by default */}
      <button
        type="button"
        onClick={() => setShowHelp((v) => !v)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          margin: "0 0 1.25rem",
          padding: 0,
          border: "none",
          background: "transparent",
          color: "var(--secondary-dark)",
          fontFamily: "inherit",
          fontSize: 12,
          fontWeight: 600,
          cursor: "pointer",
        }}
      >
        Why this matters
        <ChevronDown
          size={13}
          style={{
            transform: showHelp ? "rotate(180deg)" : "none",
            transition: "transform 0.15s ease",
          }}
        />
      </button>

      {showHelp && (
        <p
          style={{
            margin: "0 0 1.25rem",
            padding: "0.75rem 1rem",
            background: "var(--bg)",
            borderRadius: "var(--radius-sm)",
            borderLeft: "3px solid var(--secondary)",
            fontSize: 12.5,
            lineHeight: 1.65,
            color: "var(--text)",
          }}
        >
          Comparisons only run between the pages you pair here — pricing with
          pricing, a category with the equivalent category. A loose match
          produces a weak, generic report, so skip a page rather than force it.
        </p>
      )}

      {guided ? (
        <>
          {/* ── Summary bar: the counts, not a wall of chips ──── */}
          <div
            style={{
              padding: "0.875rem 1.125rem",
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              marginBottom: "1.25rem",
            }}
          >
            <div className="is-mp-summary">
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 12.5,
                  fontWeight: 600,
                  color: STATUS.matched.fg,
                }}
              >
                <CheckCircle2 size={14} />
                {matchedCount} matched
              </span>

              {pendingCount > 0 && (
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: 12.5,
                    fontWeight: 600,
                    color: STATUS.pending.fg,
                  }}
                >
                  <CircleDashed size={14} />
                  {pendingCount} to do
                </span>
              )}

              {skippedCount > 0 && (
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: 12.5,
                    fontWeight: 600,
                    color: STATUS.skipped.fg,
                  }}
                >
                  <MinusCircle size={14} />
                  {skippedCount} skipped
                </span>
              )}

              <span
                className="is-mp-count"
                style={{
                  marginLeft: "auto",
                  fontSize: 12,
                  color: "var(--text-light)",
                }}
              >
                {resolvedCount}/{totalRows}
              </span>
            </div>

            {/* Proportional progress, colour-matched to the rows */}
            <div
              style={{
                display: "flex",
                height: 5,
                borderRadius: 999,
                overflow: "hidden",
                background: "var(--border)",
              }}
            >
              {matchedCount > 0 && (
                <div
                  style={{
                    width: (matchedCount / totalRows) * 100 + "%",
                    background: STATUS.matched.bar,
                  }}
                />
              )}
              {skippedCount > 0 && (
                <div
                  style={{
                    width: (skippedCount / totalRows) * 100 + "%",
                    background: STATUS.skipped.bar,
                  }}
                />
              )}
            </div>
          </div>

          {/* Important callout — what to do when there's no counterpart.
              Pulled out as its own highlighted section so it stands apart
              from the row legend and short notices. */}
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              padding: "12px 14px",
              marginBottom: 14,
              borderRadius: "var(--radius)",
              background: "color-mix(in srgb, var(--accent) 6%, transparent)",
              border: "1px solid color-mix(in srgb, var(--accent) 22%, transparent)",
            }}
          >
            <MinusCircle
              size={16}
              style={{ marginTop: 1, flexShrink: 0, color: "var(--accent)" }}
            />
            <div>
              <p
                style={{
                  margin: 0,
                  fontSize: 11,
                  fontWeight: 800,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  color: "var(--accent)",
                }}
              >
                Important
              </p>
              <p
                style={{
                  margin: "3px 0 0",
                  fontSize: 12.5,
                  lineHeight: 1.55,
                  color: "var(--text-light)",
                }}
              >
                No counterpart in their store? Mark it{" "}
                <strong style={{ color: "var(--text)" }}>no equivalent</strong>{" "}
                rather than pairing it with an unrelated page — a bad pair
                produces a misleading comparison, while a skipped one is reported
                as a gap.
              </p>
            </div>
          </div>

          {/* Remaining standing guidance (row-icon legend + short notices). */}
          <div className="is-mp-notes">
          {/* ── What the row icons do ─────────────────────────── */}
          <p
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: "8px 16px",
              margin: "0 0 12px",
              fontSize: 12,
              color: "var(--text-light)",
            }}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
              <ListTree size={13} style={{ color: "var(--secondary)" }} /> Browse their store
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
              <Link2 size={13} style={{ color: "var(--primary)" }} /> Paste a URL
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
              <MinusCircle size={13} style={{ color: "var(--accent)" }} /> No equivalent
            </span>
          </p>

          {/* ── Short notices ─────────────────────────────────── */}
          {autoFilledCount > 0 && (
            <p
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                margin: "0 0 12px",
                fontSize: 12.5,
                color: "var(--text-light)",
              }}
            >
              <Sparkles size={13} style={{ color: "var(--secondary-dark)" }} />
              {autoFilledCount} match{autoFilledCount === 1 ? "" : "es"}{" "}
              pre-filled — worth a quick check.
            </p>
          )}

          {!hasOptions && (
            <p
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 8,
                margin: "0 0 12px",
                padding: "0.65rem 0.85rem",
                background: STATUS.pending.tint,
                border: "1px solid " + STATUS.pending.edge,
                borderRadius: "var(--radius-sm)",
                fontSize: 12.5,
                lineHeight: 1.55,
                color: "var(--text)",
              }}
            >
              <AlertTriangle
                size={13}
                style={{ color: STATUS.pending.fg, marginTop: 2, flexShrink: 0 }}
              />
              <span>
                We couldn&apos;t read {competitorLabel}&apos;s pages — it may block
                automated access, or run on a platform we can&apos;t fully read.
                You can still <strong>paste</strong> specific page URLs below, or go{" "}
                <strong>Back</strong> and pick a different competitor.
              </span>
            </p>
          )}

          {allResolved && !hasRealMatch && (
            <p
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 8,
                margin: "0 0 12px",
                padding: "0.65rem 0.85rem",
                background: STATUS.skipped.tint,
                border: "1px solid " + STATUS.skipped.edge,
                borderRadius: "var(--radius-sm)",
                fontSize: 12.5,
                lineHeight: 1.55,
                color: "var(--text)",
              }}
            >
              <AlertTriangle
                size={13}
                style={{ color: STATUS.skipped.fg, marginTop: 2, flexShrink: 0 }}
              />
              Nothing to compare — {competitorLabel} may not be a good match.
              Try a closer competitor.
            </p>
          )}
          </div>

          {/* ── Homepage row (locked) ─────────────────────────── */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "0.75rem 1rem",
              background: "var(--card)",
              borderRadius: "var(--radius)",
              border: "1px solid " + STATUS.matched.edge,
              borderLeft: "3px solid " + STATUS.matched.bar,
              marginBottom: 10,
            }}
          >
            <Home size={15} style={{ color: STATUS.matched.fg, flexShrink: 0 }} />

            <span
              style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}
            >
              Homepage
            </span>

            <ArrowRight
              size={13}
              style={{ color: "var(--text-light)", flexShrink: 0 }}
            />

            <span
              style={{
                fontSize: 12.5,
                color: "var(--text-light)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {competitorOrigin}/
            </span>

            <span style={{ marginLeft: "auto" }}>
              <Pill title="Paired automatically">
                <Lock size={10} />
                Auto
              </Pill>
            </span>
          </div>

          {/* ── One row per tracked page ─────────────────────── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {yourPages.map((yourUrl) => {
              const status = statusOf(yourUrl);
              const tone = STATUS[status];

              const rawValue = mapping[yourUrl];
              const markedNone = status === "skipped";
              const chosen = markedNone ? "" : rawValue || "";

              const ownerName = shortName(workspaceTitles[yourUrl]);
              const yourType = inferType(yourUrl);
              // A product row against a too-large competitor catalog: there's no
              // browsable product list, so steer it straight to paste/search.
              const guidedProductPaste =
                productCatalog.large && yourType.key === "product";
              const theirType = chosen ? inferType(chosen) : null;
              const typeMismatch =
                Boolean(chosen) &&
                theirType &&
                yourType.key !== "other" &&
                theirType.key !== "other" &&
                yourType.key !== theirType.key;
              const duplicate = Boolean(chosen) && usedElsewhere(yourUrl, chosen);

              const isManual =
                !markedNone &&
                (Boolean(manualMode[yourUrl]) || !hasOptions || guidedProductPaste);
              const isPicking = !markedNone && pickerRow === yourUrl;
              const isSuggested = autoFilled[yourUrl] === chosen && chosen;

              const ranked = suggestions[yourUrl] || [];
              const alternatives = ranked.filter((s) => s.url !== chosen);

              return (
                <div
                  key={yourUrl}
                  style={{
                    padding: "0.875rem 1rem",
                    background: tone.tint,
                    borderRadius: "var(--radius)",
                    border: "1px " + tone.dash + " " + tone.edge,
                    borderLeft: "3px solid " + tone.bar,
                    transition: "background 0.15s ease, border-color 0.15s ease",
                  }}
                >
                  {/* Row 1 — your page + state */}
                  <div
                    className="is-mp-rowhead"
                    style={{ marginBottom: markedNone ? 0 : 9 }}
                  >
                    <StatusIcon status={status} />

                    <span
                      title={yourUrl}
                      style={{
                        fontSize: 13.5,
                        fontWeight: 600,
                        color: "var(--text)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        flexShrink: 1,
                      }}
                    >
                      {ownerName || prettyPath(yourUrl)}
                    </span>

                    {ownerName && (
                      <span
                        title={yourUrl}
                        style={{
                          fontSize: 11.5,
                          color: "var(--text-light)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          flexShrink: 2,
                        }}
                      >
                        {prettyPath(yourUrl)}
                      </span>
                    )}

                    <IconButton
                      label="Open your page in a new tab"
                      tone="var(--text-light)"
                      onClick={() => openPage(yourUrl)}
                    >
                      <ExternalLink size={13} />
                    </IconButton>

                    <Pill>{yourType.label}</Pill>

                    {isSuggested && (
                      <Pill title="Pre-filled by IntelShift AI — please review">
                        <Sparkles size={10} />
                        Suggested
                      </Pill>
                    )}

                    <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                      {markedNone && (
                        <IconButton
                          label="Undo skip — match this page instead"
                          onClick={() => toggleNoEquivalent(yourUrl)}
                          tone={tone.fg}
                        >
                          <RotateCcw size={15} />
                        </IconButton>
                      )}
                    </span>
                  </div>

                  {/* Row 2 — the control, or the skipped note */}
                  {markedNone ? (
                    <p
                      style={{
                        margin: "6px 0 0 24px",
                        fontSize: 12,
                        color: "var(--text-light)",
                      }}
                    >
                      No equivalent in this store — skipped for this competitor
                      only.
                    </p>
                  ) : (
                    <div className="is-mp-controls">
                      <div className="is-mp-field">
                        {isManual ? (
                          <input
                            type="url"
                            value={chosen}
                            placeholder={competitorOrigin + "/example-page"}
                            onChange={(e) => setRow(yourUrl, e.target.value.trim())}
                            style={fieldStyle}
                          />
                        ) : (
                          <SearchSelect
                            value={chosen}
                            options={options.map((o) => ({ value: o.url, label: namePathText(o.label, o.url) }))}
                            placeholder="Choose their matching page…"
                            suggested={ranked.map((r) => r.url)}
                            onChange={(v) => setRow(yourUrl, v)}
                          />
                        )}
                      </div>

                      <div className="is-mp-actions">
                      {chosen && !isNone(chosen) && (
                        <IconButton
                          label="Open their matched page in a new tab"
                          tone="var(--secondary)"
                          onClick={() => openPage(chosen)}
                        >
                          <ExternalLink size={15} />
                        </IconButton>
                      )}

                      <IconButton
                        label={isPicking ? "Close browser" : "Browse their store"}
                        active={isPicking}
                        tone="var(--secondary)"
                        onClick={() => setPickerRow(isPicking ? null : yourUrl)}
                      >
                        {isPicking ? <XIcon size={15} /> : <ListTree size={15} />}
                      </IconButton>

                      {hasOptions && (
                        <IconButton
                          label={isManual ? "Choose from list" : "Paste a URL"}
                          active={isManual}
                          tone="var(--primary)"
                          onClick={() =>
                            setManualMode((prev) => ({
                              ...prev,
                              [yourUrl]: !prev[yourUrl],
                            }))
                          }
                        >
                          <Link2 size={15} />
                        </IconButton>
                      )}

                      <IconButton
                        label="No equivalent in their store"
                        tone="var(--accent)"
                        onClick={() => {
                          if (pickerRow === yourUrl) setPickerRow(null);
                          toggleNoEquivalent(yourUrl);
                        }}
                      >
                        <MinusCircle size={15} />
                      </IconButton>
                      </div>
                    </div>
                  )}

                  {/* Inline TreeNode picker */}
                  {isPicking && (
                    <div
                      className="is-mp-indent"
                      style={{
                        marginTop: 9,
                        marginLeft: 24,
                        padding: "0.75rem 0.875rem",
                        background: "var(--card)",
                        border: "1px solid var(--border)",
                        borderRadius: "var(--radius-sm)",
                      }}
                    >
                      <p
                        style={{
                          margin: "0 0 8px",
                          fontSize: 11.5,
                          color: "var(--text-light)",
                        }}
                      >
                        Pick their match for{" "}
                        <strong style={{ color: "var(--text)" }}>
                          {prettyPath(yourUrl)}
                        </strong>
                      </p>

                      <TreeNode
                        key={"picker-" + yourUrl}
                        data={treeData}
                        selectionLimit={1}
                        homepage={false}
                        onSelectionChange={(selected) =>
                          handlePickerSelection(yourUrl, selected)
                        }
                      />
                    </div>
                  )}

                  {/* Quick-pick alternatives */}
                  {!markedNone &&
                    !isManual &&
                    !isPicking &&
                    alternatives.length > 0 && (
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          flexWrap: "wrap",
                          gap: 5,
                          marginTop: 8,
                          marginLeft: 24,
                        }}
                      >
                        <Sparkles
                          size={11}
                          style={{ color: "var(--text-light)", flexShrink: 0 }}
                        />
                        {alternatives.map((alt) => (
                          <button
                            key={alt.url}
                            type="button"
                            onClick={() => setRow(yourUrl, alt.url)}
                            title={
                              (alt.label ? alt.label + " · " : "") +
                              alt.url +
                              " · " +
                              Math.round(alt.score * 100) +
                              "%"
                            }
                            style={{
                              fontSize: 11,
                              fontWeight: 600,
                              fontFamily: "inherit",
                              padding: "3px 9px",
                              borderRadius: 999,
                              background: "var(--card)",
                              border: "1px solid var(--border)",
                              color: "var(--text)",
                              cursor: "pointer",
                              maxWidth: 200,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {shortName(alt.label) || prettyPath(alt.url)}
                          </button>
                        ))}
                      </div>
                    )}

                  {/* Row feedback — one short line */}
                  {(typeMismatch || duplicate) && (
                    <p
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        margin: "8px 0 0 24px",
                        fontSize: 11.5,
                        color: STATUS.pending.fg,
                      }}
                    >
                      <AlertTriangle size={12} style={{ flexShrink: 0 }} />
                      {duplicate
                        ? "Already paired with another page."
                        : "Type mismatch — that looks like a " +
                          theirType.label.toLowerCase() +
                          " page."}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </>
      ) : (
        /* ── Fallback: original free-selection UI ──────────────── */
        <>
          {!hasOptions && (
            <p
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 8,
                margin: "0 0 12px",
                padding: "0.7rem 0.9rem",
                background: STATUS.pending.tint,
                border: "1px solid " + STATUS.pending.edge,
                borderRadius: "var(--radius-sm)",
                fontSize: 12.5,
                lineHeight: 1.55,
                color: "var(--text)",
              }}
            >
              <AlertTriangle
                size={13}
                style={{ color: STATUS.pending.fg, marginTop: 2, flexShrink: 0 }}
              />
              <span>
                We couldn&apos;t read {competitorLabel}&apos;s pages — it may block
                automated access, or run on a platform we can&apos;t fully read. You
                can still <strong>paste</strong> specific page URLs below, or go{" "}
                <strong>Back</strong> and pick a different competitor.
              </span>
            </p>
          )}

          <TreeNode
            data={treeData}
            selectionLimit={limits}
            homepage={false}
            onSelectionChange={setTreeSelectedPages}
          />

          <ManualPageUrlPicker
            urls={manualUrls}
            onUrlsChange={setManualUrls}
            existingUrls={treeSelectedPages}
            selectedCount={treeSelectedPages.length}
            selectionLimit={limits}
          />
        </>
      )}

      {/* ── Status line. Buttons live in the stepper footer. ──── */}
      <p
        style={{
          margin: "1.5rem 0 0",
          paddingTop: "1rem",
          borderTop: "1px solid var(--border)",
          fontSize: 12,
          color: "var(--text-light)",
        }}
      >
        {canFinish
          ? skippedCount > 0
            ? skippedCount +
              " page" +
              (skippedCount === 1 ? "" : "s") +
              " skipped for this competitor. Ready to continue."
            : "All pages matched. Ready to continue."
          : guided && pendingCount > 0
          ? pendingCount +
            " page" +
            (pendingCount === 1 ? "" : "s") +
            " left — match it, or mark it as having no equivalent."
          : guided && !hasRealMatch
          ? "At least one page needs a real match to continue."
          : "Complete the required fields to continue."}
      </p>
    </div>
  );
};

export default CompetitorPageSelection;
