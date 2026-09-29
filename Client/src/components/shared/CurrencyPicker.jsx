import { useEffect, useRef, useState } from "react";
import { Globe, Loader2, AlertTriangle } from "lucide-react";
import { detectStores } from "../../api/utils.api";

/* ────────────────────────────────────────────────────────────────
   Shared currency picker for onboarding (used for BOTH the user's own
   site and each competitor, so they behave identically).

   Rule: probe the entered URL for an on-page currency switcher. If the
   store genuinely offers MORE THAN ONE currency, show the choice. If it
   offers one (or we detect none), show nothing and let the store's
   default stand. We never change the URL — the URL the user typed is the
   store, and the analysis crawls exactly that.
──────────────────────────────────────────────────────────────────── */

// Display names for detected currency codes.
const CURRENCY_NAMES = {
  USD: "US Dollar", EUR: "Euro", GBP: "British Pound", PKR: "Pakistani Rupee",
  INR: "Indian Rupee", AED: "UAE Dirham", SAR: "Saudi Riyal", CAD: "Canadian Dollar",
  AUD: "Australian Dollar", NZD: "NZ Dollar", JPY: "Japanese Yen", CNY: "Chinese Yuan",
  HKD: "Hong Kong Dollar", SGD: "Singapore Dollar", MYR: "Malaysian Ringgit",
  IDR: "Indonesian Rupiah", PHP: "Philippine Peso", THB: "Thai Baht", VND: "Vietnamese Dong",
  BDT: "Bangladeshi Taka", LKR: "Sri Lankan Rupee", TRY: "Turkish Lira", RUB: "Russian Ruble",
  PLN: "Polish Zloty", CZK: "Czech Koruna", HUF: "Hungarian Forint", RON: "Romanian Leu",
  SEK: "Swedish Krona", NOK: "Norwegian Krone", DKK: "Danish Krone", CHF: "Swiss Franc",
  ZAR: "South African Rand", NGN: "Nigerian Naira", EGP: "Egyptian Pound", KES: "Kenyan Shilling",
  MAD: "Moroccan Dirham", BRL: "Brazilian Real", MXN: "Mexican Peso", ARS: "Argentine Peso",
  CLP: "Chilean Peso", COP: "Colombian Peso", PEN: "Peruvian Sol", KRW: "South Korean Won",
  TWD: "Taiwan Dollar", ILS: "Israeli Shekel", QAR: "Qatari Riyal", KWD: "Kuwaiti Dinar",
  BHD: "Bahraini Dinar", OMR: "Omani Rial",
};

/* Markets offered in the manual fallback, shown when we couldn't auto-detect a
   currency. Ordered roughly by how often we see them; anchors the user's region
   for competitor matching + pricing. */
const MARKETS = [
  { country: "Pakistan", currency: "PKR" },
  { country: "United Arab Emirates", currency: "AED" },
  { country: "Saudi Arabia", currency: "SAR" },
  { country: "Qatar", currency: "QAR" },
  { country: "Kuwait", currency: "KWD" },
  { country: "Bahrain", currency: "BHD" },
  { country: "Oman", currency: "OMR" },
  { country: "India", currency: "INR" },
  { country: "Bangladesh", currency: "BDT" },
  { country: "Sri Lanka", currency: "LKR" },
  { country: "United States", currency: "USD" },
  { country: "United Kingdom", currency: "GBP" },
  { country: "Canada", currency: "CAD" },
  { country: "Australia", currency: "AUD" },
  { country: "New Zealand", currency: "NZD" },
  { country: "Eurozone (EU)", currency: "EUR" },
  { country: "Singapore", currency: "SGD" },
  { country: "Malaysia", currency: "MYR" },
  { country: "Indonesia", currency: "IDR" },
  { country: "Philippines", currency: "PHP" },
  { country: "Thailand", currency: "THB" },
  { country: "Turkey", currency: "TRY" },
  { country: "South Africa", currency: "ZAR" },
  { country: "Nigeria", currency: "NGN" },
  { country: "Egypt", currency: "EGP" },
  { country: "Japan", currency: "JPY" },
  { country: "China", currency: "CNY" },
];

/* Country-code TLD → currency, so we can pre-select the most likely market. */
const TLD_CURRENCY = {
  pk: "PKR", ae: "AED", sa: "SAR", qa: "QAR", kw: "KWD", bh: "BHD", om: "OMR",
  in: "INR", bd: "BDT", lk: "LKR", us: "USD", uk: "GBP", gb: "GBP", ca: "CAD",
  au: "AUD", nz: "NZD", sg: "SGD", my: "MYR", id: "IDR", ph: "PHP", th: "THB",
  tr: "TRY", za: "ZAR", ng: "NGN", eg: "EGP", jp: "JPY", cn: "CNY",
  de: "EUR", fr: "EUR", es: "EUR", it: "EUR", nl: "EUR", ie: "EUR", pt: "EUR",
};

/* Best-guess currency from a URL's country-code TLD (e.g. sivanna.com.pk → PKR).
   Returns "" when the TLD gives no signal (.com, .io, …). */
const tldCurrency = (u) => {
  try {
    const host = new URL(/^https?:\/\//i.test(u) ? u : "https://" + u).hostname;
    const tld = host.split(".").pop().toLowerCase();
    return TLD_CURRENCY[tld] || "";
  } catch {
    return "";
  }
};

const selectStyle = {
  width: "100%",
  padding: "10px 12px",
  fontSize: 14,
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border)",
  background: "var(--card)",
  color: "var(--text)",
  fontFamily: "var(--font-sans)",
  cursor: "pointer",
};

const fieldLabelStyle = {
  display: "block",
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  color: "var(--text-light)",
  marginBottom: 6,
};

/**
 * @param {string}   probeUrl              Normalized URL to probe (parent sets it on blur).
 * @param {string}   currency              Currently selected currency.
 * @param {string[]} availableCurrencies   Restored list (survives remount).
 * @param {Function} onChange              ({ currency, storeUrl, availableCurrencies }) => void
 */
export default function CurrencyPicker({
  probeUrl,
  currency = "",
  availableCurrencies = [],
  onChange,
  // Fired whenever the store probe starts/stops, so the parent can disable
  // "Next" while we're checking for a currency switcher.
  onDetectingChange,
  // Fired with false when the entered website doesn't exist / can't be reached,
  // true once a reachable site is confirmed — so the parent can block "Next".
  onValidityChange,
  // The user's country (ISO-2, e.g. "US") — used to auto-pick a geo-gated site's
  // regional store. When onStoreUrlChange is provided AND the site has multiple
  // regional storefronts, a "Store region" picker is shown and the URL is
  // switched to the chosen store.
  userCountry = "",
  onStoreUrlChange,
  // When true (used for the user's OWN store), show a "Which market are you in?"
  // selector if we can't auto-detect a currency, so region is always set.
  allowManualMarket = false,
}) {
  const [detecting, setDetecting] = useState(false);
  const [currencies, setCurrencies] = useState(availableCurrencies);
  const [notReachable, setNotReachable] = useState(false);
  // Why "Next" is blocked: "missing" (domain doesn't exist) vs "unfetched" (site
  // responded but we couldn't load the real page — e.g. bot protection).
  const [blockReason, setBlockReason] = useState("");
  const [locales, setLocales] = useState([]);
  const [selectedCountry, setSelectedCountry] = useState("");
  // Manual market fallback: set when a probe finishes with no currency detected.
  const [needManual, setNeedManual] = useState(false);
  const [manualCurrency, setManualCurrency] = useState("");
  const lastRef = useRef("");

  const multiCurrency = currencies.length > 1;
  const multiRegion = locales.length > 1 && !!onStoreUrlChange;
  const showManual = allowManualMarket && needManual && !multiCurrency;

  const normUrl = (u) => {
    try {
      return new URL(u).href.replace(/\/+$/, "").toLowerCase();
    } catch {
      return String(u || "").toLowerCase();
    }
  };

  useEffect(() => {
    const u = (probeUrl || "").trim();
    if (!u || !u.includes(".")) return undefined;
    if (u === lastRef.current) return undefined; // already probed this URL
    lastRef.current = u;

    let cancelled = false;
    setDetecting(true);
    setNotReachable(false);
    setBlockReason("");
    setNeedManual(false);
    onDetectingChange?.(true);
    (async () => {
      try {
        const res = await detectStores(u);
        if (cancelled) return;
        // Block "Next" when the site either does not exist OR could not actually be
        // loaded. `fetched === false` means every method (requests → cloudscraper →
        // real browser) failed to retrieve the real page — a bot-challenge/empty
        // shell doesn't count as loaded. A site we can't read can't be analyzed, so
        // onboarding must not advance. (`fetched` undefined = older API → fall back
        // to the existence signal so we don't wrongly block.)
        const missing = res?.exists === false;
        const unfetched = res?.fetched === false;
        const blocked = missing || unfetched;
        setNotReachable(blocked);
        setBlockReason(missing ? "missing" : unfetched ? "unfetched" : "");
        onValidityChange?.(!blocked);

        // Regional storefronts → offer a picker, and auto-switch to the store
        // matching the user's country if we're not already on it.
        const locs = Array.isArray(res?.locales) ? res.locales : [];
        setLocales(locs);
        if (locs.length > 1) {
          const currentMatch = locs.find((l) => normUrl(l.url) === normUrl(u));
          const ucMatch = userCountry ? locs.find((l) => l.country === userCountry) : null;
          // Default the picker to the user's region, else the store we're on,
          // else leave it for the user to choose.
          setSelectedCountry((ucMatch || currentMatch)?.country || "");
          // Auto-switch ONLY to the user's own country store (never an arbitrary
          // region) and only if we're not already there.
          if (onStoreUrlChange && ucMatch && normUrl(ucMatch.url) !== normUrl(u)) {
            onStoreUrlChange(ucMatch.url); // re-probes the regional store
          }
        }

        const curs = Array.isArray(res?.currencies) ? res.currencies : [];
        setCurrencies(curs);
        const detected = res?.currentCurrency || curs[0] || "";
        if (detected) {
          // Persist the detected currency even for single-currency stores
          // (useful metadata for currency-aware analysis) — we just don't prompt.
          onChange?.({
            currency: currency || detected,
            storeUrl: u,
            availableCurrencies: curs,
          });
        } else if (allowManualMarket && !blocked) {
          // Nothing detected on a reachable site → ask the user which market
          // they're in, pre-selected from the URL's TLD. Emit the guess now so
          // region is set even if they don't touch the picker.
          const guess = currency || tldCurrency(u);
          setManualCurrency(guess);
          setNeedManual(true);
          if (guess) {
            onChange?.({ currency: guess, storeUrl: u, availableCurrencies: [guess] });
          }
        }
      } catch (err) {
        // A hard failure to even reach the probe likely means the site isn't
        // reachable — flag it so the user can fix the URL.
        console.error("detect-stores failed:", err?.response?.status, err?.response?.data || err?.message);
        if (!cancelled) {
          setNotReachable(true);
          setBlockReason("unfetched");
          onValidityChange?.(false);
        }
      } finally {
        if (!cancelled) {
          setDetecting(false);
          onDetectingChange?.(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [probeUrl]);

  const select = (value) =>
    onChange?.({ currency: value, storeUrl: probeUrl, availableCurrencies: currencies });

  const selectManual = (value) => {
    setManualCurrency(value);
    onChange?.({ currency: value, storeUrl: probeUrl, availableCurrencies: value ? [value] : [] });
  };

  if (detecting) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginTop: 10,
          fontSize: 12.5,
          color: "var(--text-light)",
        }}
      >
        <Loader2 size={14} className="animate-spin" />
        Checking the store…
      </div>
    );
  }

  // Website doesn't exist / couldn't be reached → tell the user to fix the URL.
  if (notReachable) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 8,
          marginTop: 10,
          padding: "10px 12px",
          background: "var(--glow-coral)",
          border: "1px solid color-mix(in srgb, var(--accent) 32%, transparent)",
          borderRadius: "var(--radius-sm)",
        }}
      >
        <AlertTriangle size={15} style={{ color: "var(--accent-dark)", marginTop: 1, flexShrink: 0 }} />
        <span style={{ fontSize: 12.5, lineHeight: 1.5, color: "var(--text)" }}>
          {blockReason === "unfetched"
            ? "We couldn't load this website — it may be blocking automated access or is temporarily down. We can't analyze a site we can't read, so please enter a URL we can reach to continue."
            : "We couldn't reach this website. Double-check the URL is correct and live."}
        </span>
      </div>
    );
  }

  // Nothing to prompt for → no UI.
  if (!multiRegion && !multiCurrency && !showManual) return null;

  const pickStore = (countryCode) => {
    const loc = locales.find((l) => l.country === countryCode);
    if (!loc) return;
    setSelectedCountry(countryCode);
    onStoreUrlChange?.(loc.url);
  };
  const selectedLabel =
    locales.find((l) => l.country === selectedCountry)?.label || "";

  return (
    <div style={{ marginTop: 14, display: "grid", gap: 12 }}>
      {/* ── Regional store picker (geo-gated sites) ─────────────── */}
      {multiRegion && (
        <div
          style={{
            padding: "1rem 1.125rem",
            background: "var(--glow-teal)",
            border: "1px solid color-mix(in srgb, var(--secondary) 32%, transparent)",
            borderRadius: "var(--radius)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <Globe size={15} style={{ color: "var(--secondary-dark)" }} />
            <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: "var(--text)" }}>
              This site has regional stores
            </p>
          </div>
          <p style={{ margin: "0 0 12px", fontSize: 12, lineHeight: 1.55, color: "var(--text-light)" }}>
            {selectedLabel
              ? `Tracking the ${selectedLabel} store. Change it if you want a different region.`
              : "Pick the regional store you want to track."}
          </p>
          <label style={fieldLabelStyle}>Store region</label>
          <select
            style={selectStyle}
            value={selectedCountry}
            onChange={(e) => pickStore(e.target.value)}
          >
            {!selectedCountry && <option value="">Choose region…</option>}
            {locales.map((l) => (
              <option key={l.country} value={l.country}>
                {l.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* ── Currency picker ─────────────────────────────────────── */}
      {multiCurrency && (
        <div
          style={{
            padding: "1rem 1.125rem",
            background: "var(--glow-teal)",
            border: "1px solid color-mix(in srgb, var(--secondary) 32%, transparent)",
            borderRadius: "var(--radius)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <Globe size={15} style={{ color: "var(--secondary-dark)" }} />
            <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: "var(--text)" }}>
              This store offers multiple currencies
            </p>
          </div>

          <p style={{ margin: "0 0 12px", fontSize: 12, lineHeight: 1.55, color: "var(--text-light)" }}>
            Pick the currency for the market you&apos;re tracking.
          </p>

          <label style={fieldLabelStyle}>Currency</label>
          <select style={selectStyle} value={currency} onChange={(e) => select(e.target.value)}>
            {!currency && <option value="">Select currency…</option>}
            {currencies.map((c) => (
              <option key={c} value={c}>
                {c}
                {CURRENCY_NAMES[c] ? ` — ${CURRENCY_NAMES[c]}` : ""}
              </option>
            ))}
          </select>

          {currency ? (
            <p style={{ margin: "10px 0 0", fontSize: 12, color: "var(--text)" }}>
              Tracking currency: <strong>{currency}</strong>
            </p>
          ) : null}
        </div>
      )}

      {/* ── Manual market fallback (currency couldn't be detected) ── */}
      {showManual && (
        <div
          style={{
            padding: "1rem 1.125rem",
            background: "var(--glow-teal)",
            border: "1px solid color-mix(in srgb, var(--secondary) 32%, transparent)",
            borderRadius: "var(--radius)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <Globe size={15} style={{ color: "var(--secondary-dark)" }} />
            <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: "var(--text)" }}>
              Which market are you in?
            </p>
          </div>

          <p style={{ margin: "0 0 12px", fontSize: 12, lineHeight: 1.55, color: "var(--text-light)" }}>
            We couldn&apos;t detect your store&apos;s currency automatically. Pick your
            main market so we match competitors and pricing to the right region.
          </p>

          <label style={fieldLabelStyle}>Market</label>
          <select
            style={selectStyle}
            value={manualCurrency}
            onChange={(e) => selectManual(e.target.value)}
          >
            {!manualCurrency && <option value="">Select your market…</option>}
            {MARKETS.map((m) => (
              <option key={m.currency} value={m.currency}>
                {m.country} — {m.currency}
              </option>
            ))}
          </select>

          {manualCurrency ? (
            <p style={{ margin: "10px 0 0", fontSize: 12, color: "var(--text)" }}>
              Tracking market: <strong>{CURRENCY_NAMES[manualCurrency] || manualCurrency}</strong>
              {" "}({manualCurrency})
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
