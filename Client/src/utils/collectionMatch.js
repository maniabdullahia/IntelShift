// Shared collection-matching stack — used by the onboarding selection modal AND
// the tracked-pages manager so the tuned scoring/segments live in ONE place.

export const slugOf = (u) => {
    const s = String(u || "").split(/[?#]/)[0].replace(/\/+$/, "");
    return (s.split("/").filter(Boolean).pop() || "").toLowerCase();
};

const stem = (w) => (w.length > 3 && w.endsWith("s") ? w.slice(0, -1) : w);

// Retail synonym map — lexical matching can't know "sunblock" == "sunscreen", so
// we fold known equivalents to one canonical word BEFORE scoring. Keys/values are
// post-stem (trailing "s" already dropped). Extend as new synonym pairs surface.
const SYNONYMS = {
    sunblock: "sunscreen", spf: "sunscreen", suncare: "sunscreen", sunprotection: "sunscreen", sunprotect: "sunscreen",
    moisturiser: "moisturizer", hydrator: "moisturizer", moisturize: "moisturizer", moisturis: "moisturizer",
    perfume: "fragrance", scent: "fragrance", cologne: "fragrance", edp: "fragrance", edt: "fragrance",
    corrector: "concealer",
    lipcolor: "lipstick", lipcolour: "lipstick", lippie: "lipstick",
    kajal: "kohl", kaajal: "kohl",
    facewash: "cleanser", cleanse: "cleanser",
    nailpolish: "nail", nailpaint: "nail", nailenamel: "nail",
    haircare: "hair", skincare: "skin", bodycare: "body",
};
const canon = (w) => SYNONYMS[w] || w;
export const tokenize = (s) =>
    String(s || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter((w) => w.length > 2).map(stem).map(canon);

// ── Audience-segment grouping ───────────────────────────────────────────────
const SEG_ALIASES = {
    mens: "men", man: "men", male: "men", gents: "men", gent: "men", gentlemen: "men", menswear: "men",
    womens: "women", woman: "women", female: "women", ladies: "women", lady: "women", womenswear: "women",
    boys: "boys", boy: "boys",
    girls: "girls", girl: "girls",
    kids: "kids", kid: "kids", children: "kids", childrens: "kids", child: "kids", junior: "kids", juniors: "kids",
    baby: "baby", babies: "baby", infant: "baby", infants: "baby", toddler: "baby",
    unisex: "unisex",
};
export const SEG_CURATED = new Set(["men", "women", "boys", "girls", "kids", "baby", "unisex"]);
export const SEG_ORDER = ["men", "women", "boys", "girls", "kids", "baby", "unisex"];
const SEG_DISPLAY = { men: "Men", women: "Women", boys: "Boys", girls: "Girls", kids: "Kids", baby: "Baby", unisex: "Unisex" };
export const segNorm = (tok) => {
    const t = String(tok || "").toLowerCase().replace(/[^a-z]/g, "");
    if (!t) return "";
    if (SEG_ALIASES[t]) return SEG_ALIASES[t];
    const d = t.length > 3 && t.endsWith("s") ? t.slice(0, -1) : t;
    return SEG_ALIASES[d] || t;
};
export const segDisplay = (seg) => SEG_DISPLAY[seg] || (seg ? seg.charAt(0).toUpperCase() + seg.slice(1) : "");
export const audienceSeg = (o) => {
    const name = String(o?.name || o?.handle || "");
    const slug = slugOf(o?.url) || "";
    const words = [...name.split(/[\s\-_/]+/), ...slug.split(/[\s\-_/]+/)].filter(Boolean);
    for (const w of words) { const s = segNorm(w); if (SEG_CURATED.has(s)) return s; }
    return "";
};
export const segConflict = (a, b) => !!a && !!b && a !== b && a !== "unisex" && b !== "unisex";
export const stripSeg = (name, seg) => {
    if (!seg || !name) return name;
    const toks = String(name).trim().split(/\s+/);
    return toks.length > 1 && segNorm(toks[0]) === seg ? toks.slice(1).join(" ") : name;
};

// Two tokens "match" if equal, or one contains the other (≥3 chars) — handles
// compound words: "eyeliner" ~ "eye liner", "eyebrow" ~ "brow".
const tokMatch = (a, b) => {
    if (a === b) return true;
    const short = a.length <= b.length ? a : b;
    const long = a.length <= b.length ? b : a;
    return short.length >= 3 && long.includes(short);
};

// 0–100 similarity between an owner and competitor category, using BOTH the title
// (tokenized + stemmed) and the slug. Normalizing away plurals/separators/word
// order means "Toners" ~ "Toner" and "Eye Liner" ~ "eyeliner" read as near-perfect.
export const matchScore = (o, c) => {
    if (segConflict(audienceSeg(o), audienceSeg(c))) return 0;
    const os = slugOf(o.url);
    const cs = slugOf(c.url);
    const ot = tokenize(o.name || o.handle || os);
    const ct = tokenize(c.name || c.handle || cs);
    const shared = ct.filter((w) => ot.some((x) => tokMatch(x, w))).length;
    const oStem = ot.slice().sort().join(" ");
    const cStem = ct.slice().sort().join(" ");
    const stemEqual = !!oStem && oStem === cStem;
    const oc = os.replace(/[^a-z0-9]/g, "");
    const cc = cs.replace(/[^a-z0-9]/g, "");
    const compactEqual = !!oc && oc === cc;
    if (!shared && !stemEqual && !compactEqual) return 0;
    const union = new Set([...ot, ...ct]).size || 1;
    let sim = shared / union;
    if (stemEqual || compactEqual || os === cs) sim = Math.max(sim, 0.95);
    else if (os && cs && (os.startsWith(cs) || cs.startsWith(os))) sim = Math.max(sim, 0.75);
    else if (os && cs && (os.includes(cs) || cs.includes(os))) sim = Math.max(sim, 0.6);
    if ((o.depth || 1) !== (c.depth || 1)) sim *= 0.9;
    return Math.round(Math.min(99, sim * 100));
};
