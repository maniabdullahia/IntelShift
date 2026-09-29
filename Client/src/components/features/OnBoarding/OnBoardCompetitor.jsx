import React, { useEffect, useRef, useState } from "react";
import { Target, Check, X, FileText, Sparkles, Plus, Loader2 } from "lucide-react";
import Input from "../../ui/Input";
import SiteReadinessBar from "../../shared/SiteReadinessBar";
import { suggestCompetitors } from "../../../api/utils.api";

/* ────────────────────────────────────────────────────────────────
   IntelShift — Onboarding: add the first competitor.
   This is the highest-leverage choice in the whole flow, so the
   copy leans hard on picking a genuinely comparable competitor.
──────────────────────────────────────────────────────────────── */

const prettyPath = (raw) => {
  try {
    const u = new URL(raw);
    return u.pathname === "/" ? "Homepage" : u.pathname.replace(/\/$/, "");
  } catch {
    return raw;
  }
};

/* Users type "sivanna.com.pk" far more often than they type the
   scheme. Normalise on blur rather than on every keystroke, so the
   protocol does not appear while they are still typing. */
const withProtocol = (value) => {
  const raw = (value || "").trim();
  if (!raw) return raw;

  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("//")) return "https:" + raw;

  // Leave it alone until it actually looks like a domain
  if (!raw.includes(".")) return raw;

  return "https://" + raw.replace(/^\/+/, "");
};

const labelStyle = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  marginBottom: 8,
  color: "var(--text)",
};

// Confirmed currency → user's country (ISO-2), for auto-picking a competitor's
// regional storefront on geo-gated sites.
const CURRENCY_COUNTRY = {
  USD: "US", GBP: "GB", CAD: "CA", AUD: "AU", NZD: "NZ", JPY: "JP", CNY: "CN",
  HKD: "HK", KRW: "KR", INR: "IN", PKR: "PK", BDT: "BD", LKR: "LK", AED: "AE",
  SAR: "SA", QAR: "QA", KWD: "KW", OMR: "OM", BHD: "BH", EGP: "EG", ZAR: "ZA",
  NGN: "NG", KES: "KE", MAD: "MA", MYR: "MY", SGD: "SG", IDR: "ID", PHP: "PH",
  THB: "TH", VND: "VN", TRY: "TR", PLN: "PL", SEK: "SE", NOK: "NO", DKK: "DK",
  CHF: "CH", ILS: "IL", MXN: "MX", BRL: "BR", RUB: "RU",
};

/* Suggestions are expensive (LLM + live verification), so cache the promise per
   workspace URL for this page load — revisiting the step reuses the result. */
const suggestionCache = new Map();

const fetchSuggestions = (url, industry, pages = [], currency = "", categories = []) => {
  const catKey = (categories || []).join(",");
  const key = `${url || ""}|${currency || ""}|${(pages || []).length}|${catKey}`;
  if (suggestionCache.has(key)) return suggestionCache.get(key);
  const pending = suggestCompetitors(url, industry, pages, currency, categories)
    .then((res) => (Array.isArray(res?.suggestions) ? res.suggestions : []))
    .catch((error) => {
      suggestionCache.delete(key); // let a later mount retry
      throw error;
    });
  suggestionCache.set(key, pending);
  return pending;
};

const cleanDomain = (u) =>
  String(u || "")
    .replace(/^https?:\/\//i, "")
    .replace(/\/.*$/, "")
    .replace(/^www\./i, "");

const CHECKLIST = [
  { ok: true, text: "Same category, same audience, comparable price tier" },
  { ok: false, text: "A marketplace or aggregator when you are a single brand" },
];

const OnBoardCompetitor = ({
  competitorName,
  setCompetitorName,
  competitorURL,
  setCompetitorURL,
  // Optional: the pages the user picked for their own site in the previous
  // step. Pass these in to show the "you will need equivalents for" reminder.
  workspacePages = [],
  workspaceName,
  // The user's own store URL + industry + confirmed currency — used to suggest
  // region-anchored, catalog-verified direct competitors.
  workspaceURL = "",
  industry = "",
  workspaceCurrency = "",
  // The user's chosen focus categories (ordered), from the Focus step. When set,
  // the auto-suggestions target these instead of full auto-detection.
  focusCategories = [],
  // Injected by ProcessStepper — every step stays mounted, so we only fetch
  // suggestions once this step is actually on screen (pages are picked by then).
  isActive = true,
  // Position in the competitor list, and the ones already captured.
  competitorIndex = 0,
  competitorTotal = 1,
  addedCompetitors = [],
  // Saved store/currency selection for this competitor (restored on remount),
  // and a setter to persist changes back to the onboarding state.
  competitorStore = {},
  onStoreChange,
  // Bubbles the currency-probe in-progress state up so the parent can disable Next.
  onCurrencyCheckingChange,
  // Bubbles up whether the entered site is reachable (blocks Next when not).
  onUrlReachableChange,
  // Site-readiness validation state (shown under the URL field).
  validating = false,
  validateStage = "",
  validateError = "",
}) => {
  const pages = (workspacePages || [])
    .map((p) => (typeof p === "string" ? p : p?.url || ""))
    .filter(Boolean)
    .filter((p) => prettyPath(p) !== "Homepage");

  // Currency detection is handled by the shared <CurrencyPicker>. We feed it the
  // URL to probe — set on blur so it doesn't fire mid-typing. For geo-gated
  // sites, the picker can switch the tracked URL to the right regional store.
  const [probeUrl, setProbeUrl] = useState("");

  // The user's country (for auto-picking a competitor's regional store) derived
  // from the workspace currency, e.g. USD → US.
  const userCountry = CURRENCY_COUNTRY[String(workspaceCurrency || "").toUpperCase()] || "";

  // The regional-store picker (or auto-switch) changes the tracked competitor URL
  // and re-probes it for the correct currency.
  const handleStoreUrlChange = (newUrl) => {
    if (!newUrl) return;
    setCompetitorURL(newUrl);
    setProbeUrl(newUrl);
  };

  // ── Suggested competitors (LLM + verified). Non-blocking: the panel fills in
  // when ready; the user can always type their own. ─────────────────────────
  const [suggestions, setSuggestions] = useState([]);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [suggestFailed, setSuggestFailed] = useState(false);
  // "Target specific categories" control: reveal an input, run a category-seeded
  // search, and REPLACE the auto suggestions with the results (with a way back).
  const [showCatInput, setShowCatInput] = useState(false);
  const [catInput, setCatInput] = useState("");
  const [catMode, setCatMode] = useState(false); // true once category results replace the list

  const runCategorySearch = () => {
    const cats = catInput.split(",").map((c) => c.trim()).filter(Boolean);
    if (!cats.length || !workspaceURL) return;
    setSuggestLoading(true);
    setSuggestFailed(false);
    setCatMode(true);
    setShowCatInput(false);
    fetchSuggestions(workspaceURL, industry, workspacePages, workspaceCurrency, cats)
      .then((list) => { setSuggestions(list); setSuggestLoading(false); })
      .catch(() => { setSuggestFailed(true); setSuggestLoading(false); });
  };

  const backToAuto = () => {
    setCatMode(false);
    setSuggestLoading(true);
    setSuggestFailed(false);
    fetchSuggestions(workspaceURL, industry, workspacePages, workspaceCurrency, focusCategories)
      .then((list) => { setSuggestions(list); setSuggestLoading(false); })
      .catch(() => { setSuggestFailed(true); setSuggestLoading(false); });
  };

  useEffect(() => {
    if (!isActive || !workspaceURL) return undefined;
    if (catMode) return undefined; // don't clobber category-targeted results
    let cancelled = false;
    setSuggestLoading(true);
    setSuggestFailed(false);
    fetchSuggestions(workspaceURL, industry, workspacePages, workspaceCurrency, focusCategories)
      .then((list) => {
        if (cancelled) return;
        setSuggestions(list);
        setSuggestLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setSuggestFailed(true);
        setSuggestLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActive, workspaceURL, industry, workspaceCurrency, (focusCategories || []).join(",")]);

  // Domains already chosen (this field or earlier competitors) → hide from picks.
  const usedDomains = new Set(
    [competitorURL, ...(addedCompetitors || []).map((c) => c?.url)]
      .map(cleanDomain)
      .filter(Boolean)
  );
  const visibleSuggestions = suggestions.filter(
    (s) => !usedDomains.has(cleanDomain(s.domain || s.url))
  );

  const pickSuggestion = (s) => {
    setCompetitorName(s.name || cleanDomain(s.domain || s.url));
    const u = withProtocol(s.url || s.domain);
    setCompetitorURL(u);
    setProbeUrl(u);
  };

  return (
    <div style={{ fontFamily: "var(--font-sans)" }}>
      <h2
        style={{
          fontSize: 20,
          fontWeight: 600,
          letterSpacing: "-0.025em",
          marginBottom: 6,
          color: "var(--primary)",
        }}
      >
        {competitorIndex === 0
          ? "Add your first competitor"
          : "Add another competitor"}
      </h2>

      {competitorTotal > 1 && (
        <p
          style={{
            margin: "0 0 8px",
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "var(--text-light)",
          }}
        >
          Competitor {competitorIndex + 1} of {competitorTotal}
        </p>
      )}

      {addedCompetitors.length > 0 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 6,
            marginBottom: "1rem",
          }}
        >
          <span style={{ fontSize: 12, color: "var(--text-light)" }}>
            Already added:
          </span>
          {addedCompetitors.map((c) => (
            <span
              key={c.id || c.url}
              title={c.url}
              style={{
                fontSize: 12,
                fontWeight: 600,
                padding: "3px 10px",
                borderRadius: 999,
                background: "var(--glow-teal)",
                color: "var(--secondary-dark)",
              }}
            >
              {c.name || c.url}
            </span>
          ))}
        </div>
      )}

      {/* ── Or pick your own — guidance ───────────────────────── */}
      <p
        style={{
          fontSize: 14.5,
          color: "var(--text-light)",
          marginBottom: "1.25rem",
          lineHeight: 1.6,
        }}
      >
        Every insight IntelShift AI produces is relative to this brand. Choose well.
      </p>

      <div
        style={{
          padding: "1.125rem",
          background: "var(--glow-coral)",
          border: "1px solid color-mix(in srgb, var(--accent) 32%, transparent)",
          borderRadius: "var(--radius)",
          marginBottom: "1.5rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <Target size={17} style={{ color: "var(--accent-dark)" }} />
          <p
            style={{
              margin: 0,
              fontSize: 13,
              fontWeight: 700,
              color: "var(--text)",
            }}
          >
            Pick a direct competitor worth watching
          </p>
        </div>

        <div style={{ display: "grid", gap: 6, marginTop: 10 }}>
          {CHECKLIST.map((row) => (
            <div
              key={row.text}
              style={{ display: "flex", alignItems: "flex-start", gap: 8 }}
            >
              {row.ok ? (
                <Check
                  size={13}
                  strokeWidth={3}
                  style={{
                    color: "var(--success-dark)",
                    marginTop: 3,
                    flexShrink: 0,
                  }}
                />
              ) : (
                <X
                  size={13}
                  strokeWidth={3}
                  style={{
                    color: "var(--danger)",
                    marginTop: 3,
                    flexShrink: 0,
                  }}
                />
              )}
              <span
                style={{
                  fontSize: 12.5,
                  lineHeight: 1.5,
                  color: row.ok ? "var(--text)" : "var(--text-light)",
                }}
              >
                {row.text}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Reminder: the pages they need equivalents for ──────── */}
      {pages.length > 0 && (
        <div
          style={{
            padding: "1rem 1.125rem",
            background: "var(--bg)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            marginBottom: "1.5rem",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 10,
            }}
          >
            <FileText size={14} style={{ color: "var(--secondary-dark)" }} />
            <p
              style={{
                margin: 0,
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "var(--text-light)",
              }}
            >
              You picked these for {workspaceName || "your store"}
            </p>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                padding: "4px 10px",
                borderRadius: 999,
                background: "var(--glow-teal)",
                color: "var(--secondary-dark)",
              }}
            >
              Homepage
            </span>

            {pages.map((p) => (
              <span
                key={p}
                title={p}
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  padding: "4px 10px",
                  borderRadius: 999,
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                  color: "var(--text)",
                  maxWidth: 240,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {prettyPath(p)}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Suggested competitors (featured — first thing on the step) ──── */}
      {workspaceURL && (
        <div
          style={{
            padding: "1.5rem 1.625rem",
            background: "var(--glow-teal)",
            border: "1.5px solid color-mix(in srgb, var(--secondary) 40%, transparent)",
            borderRadius: "var(--radius-lg, 18px)",
            marginBottom: "1.75rem",
            boxShadow: "var(--shadow-md, 0 10px 30px rgba(0,0,0,0.08))",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 34,
                height: 34,
                borderRadius: 10,
                background: "var(--secondary-dark)",
                flexShrink: 0,
              }}
            >
              <Sparkles size={18} style={{ color: "#fff" }} />
            </span>
            <p style={{ margin: 0, fontSize: 17, fontWeight: 800, letterSpacing: "-0.02em", color: "var(--text)" }}>
              Suggested competitors
            </p>
          </div>
          <p
            style={{
              margin: "0 0 16px",
              fontSize: 13.5,
              color: "var(--text-light)",
              lineHeight: 1.55,
            }}
          >
            {catMode ? (
              <>
                Competitors that sell the categories you entered.{" "}
                <button type="button" onClick={backToAuto} style={{ background: "none", border: "none", padding: 0, color: "var(--secondary-dark)", fontWeight: 700, cursor: "pointer", textDecoration: "underline" }}>
                  Back to auto suggestions
                </button>
              </>
            ) : (
              <>
                Direct matches we found for{" "}
                <strong style={{ color: "var(--text)" }}>{workspaceName || "your store"}</strong>. Tap one to use it, or type your own below.
              </>
            )}
          </p>

          {suggestLoading ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12.5,
                color: "var(--text-light)",
              }}
            >
              <Loader2
                size={14}
                className="animate-spin"
                style={{ color: "var(--secondary-dark)" }}
              />
              Finding brands like yours…
            </div>
          ) : (
            <div style={{ display: "grid", gap: 10 }}>
              {visibleSuggestions.map((s) => {
                const isPicked = cleanDomain(competitorURL) === cleanDomain(s.domain || s.url);
                return (
                  <button
                    key={s.url || s.domain}
                    type="button"
                    onClick={() => pickSuggestion(s)}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 12,
                      textAlign: "left",
                      width: "100%",
                      padding: "14px 16px",
                      borderRadius: "var(--radius)",
                      cursor: "pointer",
                      background: isPicked ? "var(--glow-teal)" : "var(--card)",
                      border: isPicked
                        ? "1.5px solid color-mix(in srgb, var(--secondary) 55%, transparent)"
                        : "1px solid var(--border)",
                      boxShadow: isPicked ? "none" : "var(--shadow-sm)",
                      transition: "border-color .15s, background .15s, box-shadow .15s",
                    }}
                  >
                    <span
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: 26,
                        height: 26,
                        flexShrink: 0,
                        borderRadius: 999,
                        marginTop: 1,
                        background: isPicked ? "var(--secondary-dark)" : "var(--bg)",
                        border: isPicked ? "none" : "1px solid var(--border)",
                      }}
                    >
                      {isPicked ? (
                        <Check size={15} strokeWidth={3} style={{ color: "#fff" }} />
                      ) : (
                        <Plus size={15} strokeWidth={2.5} style={{ color: "var(--text-light)" }} />
                      )}
                    </span>
                    <span style={{ minWidth: 0, flex: 1 }}>
                      <span
                        style={{
                          display: "flex",
                          alignItems: "baseline",
                          gap: 8,
                          flexWrap: "wrap",
                        }}
                      >
                        <span style={{ fontSize: 15.5, fontWeight: 700, color: "var(--text)" }}>
                          {s.name || cleanDomain(s.domain || s.url)}
                        </span>
                        <span style={{ fontSize: 12.5, color: "var(--text-light)" }}>
                          {cleanDomain(s.domain || s.url)}
                        </span>
                      </span>
                      {s.reason && (
                        <span
                          style={{
                            display: "block",
                            marginTop: 2,
                            fontSize: 12,
                            lineHeight: 1.45,
                            color: "var(--text-light)",
                          }}
                        >
                          {s.reason}
                        </span>
                      )}
                      {Array.isArray(s.matchedCategories) &&
                        s.matchedCategories.length > 0 && (
                          <span
                            style={{
                              display: "flex",
                              alignItems: "center",
                              flexWrap: "wrap",
                              gap: 4,
                              marginTop: 6,
                            }}
                          >
                            <span
                              style={{
                                fontSize: 10.5,
                                fontWeight: 700,
                                letterSpacing: "0.04em",
                                textTransform: "uppercase",
                                color: "var(--secondary-dark)",
                                marginRight: 2,
                              }}
                            >
                              Covers
                            </span>
                            {s.matchedCategories.slice(0, 4).map((cat) => (
                              <span
                                key={cat}
                                style={{
                                  fontSize: 11,
                                  fontWeight: 600,
                                  padding: "1px 7px",
                                  borderRadius: 999,
                                  background: "var(--glow-teal)",
                                  color: "var(--secondary-dark)",
                                  textTransform: "capitalize",
                                }}
                              >
                                {cat}
                              </span>
                            ))}
                            {s.matchedCategories.length > 4 && (
                              <span
                                style={{ fontSize: 11, color: "var(--text-light)" }}
                              >
                                +{s.matchedCategories.length - 4}
                              </span>
                            )}
                          </span>
                        )}
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Empty state (auto-detection found nothing — e.g. an unreadable catalog) */}
          {!suggestLoading && visibleSuggestions.length === 0 && (
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--text-light)", lineHeight: 1.5 }}>
              {catMode
                ? "No competitors matched those categories. Try different or broader terms below."
                : "We couldn't auto-detect competitors for this store. Tell us what it sells and we'll search directly:"}
            </p>
          )}

          {/* ── Target specific categories (highlighted CTA + input) ──── */}
          <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px dashed color-mix(in srgb, var(--secondary) 40%, transparent)" }}>
            {!showCatInput ? (
              <button
                type="button"
                onClick={() => {
                  if (!catInput) {
                    const seed = [...new Set(visibleSuggestions.flatMap((s) => s.matchedCategories || []))].slice(0, 6);
                    if (seed.length) setCatInput(seed.join(", "));
                  }
                  setShowCatInput(true);
                }}
                style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "var(--secondary-dark)", color: "#fff", border: "none", borderRadius: 999, padding: "9px 16px", fontSize: 13.5, fontWeight: 700, cursor: "pointer", boxShadow: "0 6px 18px color-mix(in srgb, var(--secondary) 45%, transparent)" }}
              >
                <Sparkles size={15} style={{ color: "#fff" }} />
                Want to target specific category competitors?
              </button>
            ) : (
              <div>
                <p style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
                  Enter the categories to target, separated by commas
                </p>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <input
                    autoFocus
                    value={catInput}
                    onChange={(e) => setCatInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); runCategorySearch(); } }}
                    placeholder="e.g. lipstick, foundation, mascara"
                    style={{ flex: 1, minWidth: 220, padding: "11px 13px", fontSize: 14, borderRadius: 10, border: "1px solid var(--border)", background: "var(--card)", color: "var(--text)", fontFamily: "var(--font-sans)" }}
                  />
                  <button
                    type="button"
                    onClick={runCategorySearch}
                    disabled={!catInput.trim() || suggestLoading}
                    style={{ padding: "11px 18px", fontSize: 13.5, fontWeight: 700, borderRadius: 10, border: "none", cursor: catInput.trim() ? "pointer" : "not-allowed", background: catInput.trim() ? "var(--accent)" : "var(--border)", color: catInput.trim() ? "#fff" : "var(--text-light)" }}
                  >
                    Find competitors
                  </button>
                </div>
                <p style={{ margin: "8px 0 0", fontSize: 11.5, color: "var(--text-light)" }}>
                  We'll search each category in {workspaceCurrency ? `your market` : "your region"} and rank direct matches. Replaces the list above.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Fields ────────────────────────────────────────────── */}
      <div style={{ marginBottom: "1rem" }}>
        <div style={{ marginBottom: "1.125rem" }}>
          <label htmlFor="competitorName" style={labelStyle}>
            Competitor Name <span style={{ color: "var(--accent)" }}>*</span>
          </label>
          <Input
            id="competitorName"
            placeholder="Enter competitor name i.e. IntelShift AI"
            value={competitorName}
            onChange={(e) => setCompetitorName(e.target.value)}
          />
        </div>

        <div>
          <label htmlFor="competitorURL" style={labelStyle}>
            Competitor Store URL{" "}
            <span style={{ color: "var(--accent)" }}>*</span>
          </label>
          <Input
            id="competitorURL"
            placeholder="competitorstore.com"
            value={competitorURL}
            onChange={(e) => setCompetitorURL(e.target.value)}
            onBlur={(e) => {
              const v = withProtocol(e.target.value);
              setCompetitorURL(v);
              setProbeUrl(v);
            }}
          />
          <p
            style={{
              fontSize: 12,
              color: "var(--text-light)",
              margin: "8px 0 0",
              lineHeight: 1.55,
            }}
          >
            We'll capture this store automatically — you choose what to track once your workspace opens.
          </p>

          {/* Readiness (homepage + collection + product + currency) is confirmed
              when the competitor is added; its currency read pre-fills the store. */}
          <SiteReadinessBar validating={validating} stage={validateStage} error={validateError} />
        </div>
      </div>
    </div>
  );
};

export default OnBoardCompetitor;
