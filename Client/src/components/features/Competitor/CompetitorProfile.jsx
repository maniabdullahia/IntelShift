import { useEffect, useState } from "react";
import { Sparkles, ExternalLink, Loader2, Plus } from "lucide-react";

import Input from "../../ui/Input";
import { suggestCompetitors } from "../../../api/utils.api";

const nameFromDomain = (domain) => {
  const first = String(domain || "").split(".")[0] || "";
  return first ? first.charAt(0).toUpperCase() + first.slice(1) : "";
};

const CompetitorProfile = ({
  competitorName,
  setCompetitorName,
  competitorUrl,
  setCompetitorUrl,
  ownerUrl,
  industry,
  excludeDomains = [],
}) => {

  const addHttpsPrefix = (url) => {
    if (!url.startsWith("http://") && !url.startsWith("https://")) {
      return `https://${url}`;
    }
    return url;
  }

  // Auto-suggested competitors for the user's own store (same engine onboarding uses).
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ownerUrl) return;
    let alive = true;
    setLoading(true);
    suggestCompetitors(ownerUrl, industry, [], "")
      .then((res) => {
        if (!alive) return;
        const list = Array.isArray(res?.suggestions) ? res.suggestions : Array.isArray(res) ? res : [];
        const have = new Set((excludeDomains || []).map((d) => String(d || "").toLowerCase()));
        setSuggestions(list.filter((s) => s?.domain && !have.has(String(s.domain).toLowerCase())));
      })
      .catch(() => { if (alive) setSuggestions([]); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ownerUrl, industry]);

  const pick = (s) => {
    setCompetitorUrl(s.url || (s.domain ? `https://${s.domain}` : ""));
    setCompetitorName(s.name || nameFromDomain(s.domain));
  };

  const pickedDomain = String(competitorUrl || "").replace(/^https?:\/\//i, "").replace(/^www\./i, "").replace(/\/.*$/, "").toLowerCase();

  return (
    <div>
      <h1 className="text-(--primary) mb-2 text-2xl font-[Inter] tracking-tight">
        Set up Competitor
      </h1>
      <p className="text-sm text-(--text-light) my-5 leading-0.5">
        Tell us a bit about your competitor to get started.
      </p>

      {/* Suggested competitors */}
      {(loading || suggestions.length > 0) && (
        <div className="mt-4 rounded-xl border p-3.5" style={{ borderColor: "var(--border)", background: "var(--bg)" }}>
          <p className="mb-2 inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--text-light)" }}>
            <Sparkles size={13} style={{ color: "var(--secondary)" }} /> Suggested for your store
          </p>
          {loading ? (
            <div className="flex items-center gap-2 py-2 text-sm" style={{ color: "var(--text-light)" }}>
              <Loader2 size={15} className="animate-spin" /> Finding close competitors…
            </div>
          ) : (
            <div className="flex flex-col gap-1.5">
              {suggestions.slice(0, 6).map((s) => {
                const active = pickedDomain && String(s.domain).toLowerCase() === pickedDomain;
                return (
                  <div
                    key={s.domain || s.url}
                    className="flex items-center gap-3 rounded-lg border px-3 py-2"
                    style={{ borderColor: active ? "var(--secondary)" : "var(--border)", background: active ? "color-mix(in srgb, var(--secondary) 8%, var(--card))" : "var(--card)" }}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold" style={{ color: "var(--text)" }}>{s.name || nameFromDomain(s.domain)}</p>
                      <p className="truncate text-xs" style={{ color: "var(--text-light)" }}>
                        {s.domain}{Array.isArray(s.matchedCategories) && s.matchedCategories.length ? ` · ${s.matchedCategories.slice(0, 3).join(", ")}` : ""}
                      </p>
                    </div>
                    {s.url && (
                      <a href={s.url} target="_blank" rel="noreferrer" className="shrink-0" title="Open site">
                        <ExternalLink size={15} style={{ color: "var(--text-light)" }} />
                      </a>
                    )}
                    <button
                      type="button"
                      onClick={() => pick(s)}
                      className="inline-flex shrink-0 items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-bold text-white"
                      style={{ background: active ? "var(--secondary)" : "var(--primary)" }}
                    >
                      {active ? "Selected" : <><Plus size={13} /> Use</>}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div className="mt-4 space-y-4">
        <label htmlFor="competitorName" className="text-sm mt-3">Competitor Name <span className="text-(--accent)">*</span></label>
        <Input
          label="Competitor Name"
          id="competitorName"
          placeholder="Enter Your Competitor's Name (e.g. Intelshift)"
          value={competitorName}
          onChange={(e) => setCompetitorName(e.target.value)}
        />
        <label htmlFor="competitorUrl" className="text-sm mt-3">Competitor URL <span className="text-(--accent)">*</span></label>
        <Input
          label="Competitor URL"
          id="competitorUrl"
          placeholder="Enter Your Competitor's Website URL"
          value={competitorUrl}
          onChange={(e) => setCompetitorUrl(e.target.value)}
          onBlur={(e) => setCompetitorUrl(addHttpsPrefix(e.target.value))}
        />
      </div>
    </div>
  );
};

export default CompetitorProfile;
