import { Check, Layers, Info } from "lucide-react";
import StoreProfileCard from "../../shared/StoreProfileCard";

/* ────────────────────────────────────────────────────────────────
   IntelShift — Onboarding: Focus categories

   The user picks the categories they care most about (1–5, in PRIORITY
   order — selection order = rank) from what we detected on their store.
   This sharpens competitor suggestions, page pairing, Pro auto-select,
   fit scoring and small-plan page budgets.

   "All categories" (or picking nothing) = no focus lens; the system
   behaves exactly as it does today. If we detected nothing (custom / JS /
   blocked store) we don't show a picker — we default to "all" and say so.
──────────────────────────────────────────────────────────────── */

const MAX_FOCUS = 5;

/* Derive lightweight, display-only ATTRIBUTE tags from a collection's name +
   handle, so an otherwise bare "Leggings" or "Black Tops" carries context:
     • audience  — Women / Men / Kids / Unisex  (from womens-/mens-/kids- tokens)
     • facet     — a hint that it's a FILTERED VIEW, not a top category:
                     Color (Black Tops), Set (Green Gym Sets), Size (5 Inch Shorts)
   Word-boundary matched so "Blackout"/"Menswear" don't false-trigger. Best-effort:
   what the store didn't encode stays untagged (honest, not guessed). */
const _COLOR_RE = /\b(black|white|red|blue|green|pink|grey|gray|navy|beige|brown|purple|yellow|orange|gold|silver|teal|maroon|olive|khaki|cream|tan)\b/;
const _cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
function deriveAttrs(name, handle) {
  const s = `${name || ""} ${handle || ""}`.toLowerCase();
  const tags = [];
  // Audience (one, most specific first).
  if (/\b(wom[ae]n|women'?s|womens|ladies|female)\b/.test(s)) tags.push({ label: "Women", kind: "aud" });
  else if (/\b(m[ae]n|men'?s|mens|male|gents)\b/.test(s)) tags.push({ label: "Men", kind: "aud" });
  else if (/\b(kids?|children|child|boys?|girls?|youth|junior|toddler|baby)\b/.test(s)) tags.push({ label: "Kids", kind: "aud" });
  else if (/\bunisex\b/.test(s)) tags.push({ label: "Unisex", kind: "aud" });
  // Facet hints — signal a filtered/derived view rather than a core category.
  const color = (s.match(_COLOR_RE) || [])[1];
  if (color) tags.push({ label: _cap(color), kind: "color" });
  if (/\b(sets?|bundles?|tracksuits?|outfits?|kits?)\b/.test(s)) tags.push({ label: "Set", kind: "facet" });
  // Bare single letters (s/m/l) are too false-positive-prone — require a real
  // measurement or a multi-char size token.
  if (/\b\d+\s?(?:inch|in|")\b/.test(s) || /\b(xs|xl|xxl|xxxl|small|medium|large|petite|plus[- ]?size)\b/.test(s)) tags.push({ label: "Size", kind: "facet" });
  return tags.slice(0, 3);
}

const _tagStyle = (kind, onDark) => {
  if (kind === "aud") {
    return { background: onDark ? "rgba(255,255,255,0.28)" : "var(--glow-teal, rgba(78,205,196,0.16))", color: onDark ? "#fff" : "var(--secondary-dark, var(--secondary))" };
  }
  // color/facet — muted "this is a filtered view" hint.
  return { background: onDark ? "rgba(255,255,255,0.18)" : "var(--bg, #f1f5f9)", color: onDark ? "rgba(255,255,255,0.85)" : "var(--text-light)" };
};

const labelStyle = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  marginBottom: 8,
  color: "var(--text)",
};

export default function FocusCategories({
  categories = [],       // [{ name, handle, productCount }]
  selected = [],         // ordered array of category names (priority)
  setSelected,
  allSelected = false,   // "All categories" toggle
  setAllSelected,
  storeProfile = null,   // onboarding store profile (business type, market, category)
}) {
  const hasCategories = Array.isArray(categories) && categories.length > 0;

  const toggle = (name) => {
    if (allSelected) return; // All is exclusive
    const idx = selected.indexOf(name);
    if (idx >= 0) {
      setSelected(selected.filter((n) => n !== name));
    } else {
      if (selected.length >= MAX_FOCUS) return; // cap at 5
      setSelected([...selected, name]); // append → order = priority
    }
  };

  const pickAll = () => {
    setAllSelected(true);
    setSelected([]);
  };
  const clearAll = () => setAllSelected(false);

  return (
    <div style={{ fontFamily: "var(--font-sans)" }}>
      <h2 style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.025em", marginBottom: 6, color: "var(--primary)" }}>
        What do you want to focus on?
      </h2>
      <StoreProfileCard profile={storeProfile} />
      <p style={{ fontSize: 14.5, color: "var(--text-light)", marginBottom: "1.5rem", lineHeight: 1.6 }}>
        Here's what we found your store sells. Pick the categories that matter most —
        we'll use them to find the right competitors and focus your comparisons.
      </p>

      {!hasCategories ? (
        // Zero-detection path — no picker, default to "analyze all".
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "14px 16px", background: "var(--glow-teal, rgba(78,205,196,0.08))", border: "1px solid color-mix(in srgb, var(--secondary) 30%, transparent)", borderRadius: "var(--radius-sm, 10px)" }}>
          <Info size={16} style={{ color: "var(--secondary)", marginTop: 1, flexShrink: 0 }} />
          <span style={{ fontSize: 13.5, color: "var(--text)", lineHeight: 1.55 }}>
            We couldn't pull specific categories from your store, so we'll analyze
            <strong> everything</strong>. You can refine focus later from your workspace.
          </span>
        </div>
      ) : (
        <>
          <label style={labelStyle}>
            Your focus categories <span style={{ fontWeight: 400, color: "var(--text-light)" }}>· pick up to {MAX_FOCUS}, most important first</span>
          </label>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16, opacity: allSelected ? 0.4 : 1, pointerEvents: allSelected ? "none" : "auto" }}>
            {categories.map((c) => {
              const rank = selected.indexOf(c.name);
              const active = rank >= 0;
              const atCap = !active && selected.length >= MAX_FOCUS;
              return (
                <button
                  key={c.handle || c.name}
                  type="button"
                  onClick={() => toggle(c.name)}
                  disabled={atCap}
                  title={atCap ? `You can pick up to ${MAX_FOCUS}` : c.name}
                  style={{
                    display: "inline-flex", alignItems: "center", gap: 7,
                    padding: "8px 12px", borderRadius: 999, fontSize: 13, fontWeight: 600,
                    cursor: atCap ? "not-allowed" : "pointer",
                    transition: "all 0.15s ease",
                    border: active ? "1px solid var(--secondary)" : "1px solid var(--border)",
                    background: active ? "var(--secondary)" : "#fff",
                    color: active ? "#fff" : (atCap ? "var(--text-light)" : "var(--text)"),
                  }}
                >
                  {active && (
                    <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 17, height: 17, borderRadius: "50%", background: "rgba(255,255,255,0.25)", fontSize: 11, fontWeight: 800 }}>
                      {rank + 1}
                    </span>
                  )}
                  {c.name}
                  {deriveAttrs(c.name, c.handle).map((t, i) => (
                    <span key={i} style={{ ...(_tagStyle(t.kind, active)), fontWeight: 700, fontSize: 10, padding: "1px 6px", borderRadius: 999, letterSpacing: "0.02em" }}>
                      {t.label}
                    </span>
                  ))}
                  {typeof c.productCount === "number" && c.productCount > 0 && (
                    <span style={{ fontWeight: 400, opacity: 0.7, fontSize: 12 }}>· {c.productCount}</span>
                  )}
                </button>
              );
            })}
          </div>

          {/* All categories — mutually exclusive with the picks above. */}
          <button
            type="button"
            onClick={() => (allSelected ? clearAll() : pickAll())}
            style={{
              display: "inline-flex", alignItems: "center", gap: 9, padding: "10px 14px",
              borderRadius: "var(--radius-sm, 10px)", fontSize: 13.5, fontWeight: 600, cursor: "pointer",
              transition: "all 0.15s ease",
              border: allSelected ? "1px solid var(--primary)" : "1px solid var(--border)",
              background: allSelected ? "var(--primary)" : "#fff",
              color: allSelected ? "#fff" : "var(--text)",
            }}
          >
            <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 18, height: 18, borderRadius: 5, border: allSelected ? "none" : "1.5px solid var(--border)", background: allSelected ? "rgba(255,255,255,0.25)" : "transparent" }}>
              {allSelected ? <Check size={13} /> : <Layers size={12} style={{ color: "var(--text-light)" }} />}
            </span>
            Focus on all categories (analyze my whole store)
          </button>

          <p style={{ fontSize: 12, color: "var(--text-light)", margin: "14px 0 0", lineHeight: 1.55 }}>
            {allSelected
              ? "We'll treat every category equally — same as no specific focus."
              : selected.length > 0
                ? `${selected.length} selected. The order sets priority — #1 gets the most weight.`
                : "Pick at least one, or choose “all categories”."}
          </p>
        </>
      )}
    </div>
  );
}
