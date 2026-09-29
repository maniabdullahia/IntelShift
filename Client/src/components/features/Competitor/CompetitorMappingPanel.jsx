import { useEffect, useMemo, useRef, useState } from "react";
import { Store, Target, Loader2, ExternalLink, ArrowRight, Plus, X, Link, LayoutGrid, ChevronDown } from "lucide-react";

import SearchSelect from "../../shared/SearchSelect";
import { matchScore, slugOf } from "../../../utils/collectionMatch";
import { getWorkspaceRecon, previewCollections } from "../../../api/workspace.api";

/* Same mapped "Choose what to track" experience as the onboarding selection modal,
   reusable for adding a competitor later. Fetches the competitor's collections
   (recon-shape) + the owner's, auto-pairs them, and lets the user tick mapped
   pairs / add pages by URL. Emits the picks via onPageSelection + onMappingChange
   so it drops into the existing CreateCompetitor wiring. */

let SEQ = 0;
const uid = (p) => `${p}${Date.now().toString(36)}${SEQ++}`;
const norm = (u) => String(u || "").trim().replace(/\/+$/, "");
const NONE = "";
const MATCH_MIN = 40;
const withProto = (u) => {
    const s = String(u || "").trim();
    if (!s) return "";
    if (/^https?:\/\//i.test(s)) return s;
    if (!s.includes(".")) return s;
    return `https://${s.replace(/^\/+/, "")}`;
};

function buildRows(ownerCols, compCols) {
    const scored = [];
    ownerCols.forEach((o, oi) =>
        compCols.forEach((c, ci) => {
            const s = matchScore(o, c);
            if (s >= MATCH_MIN) scored.push({ oi, ci, s });
        })
    );
    scored.sort((a, b) => b.s - a.s);
    const usedO = new Set();
    const usedC = new Set();
    const rows = [];
    const mk = (kind, o, c) => ({
        key: uid(kind), kind,
        ownerUrl: o ? norm(o.url) : NONE, ownerName: o ? o.name || o.handle : "",
        compUrl: c ? norm(c.url) : NONE, compName: c ? c.name || c.handle : "",
        tracked: false, customOwner: false, customComp: false,
    });
    for (const { oi, ci } of scored) {
        if (usedO.has(oi) || usedC.has(ci)) continue;
        usedO.add(oi); usedC.add(ci);
        rows.push(mk("matched", ownerCols[oi], compCols[ci]));
    }
    ownerCols.forEach((o, oi) => { if (!usedO.has(oi)) rows.push(mk("ownerOnly", o, null)); });
    compCols.forEach((c, ci) => { if (!usedC.has(ci)) rows.push(mk("compOnly", null, c)); });
    return rows;
}

const faviconUrl = (domain) => (domain ? `https://www.google.com/s2/favicons?sz=64&domain=${encodeURIComponent(domain)}` : "");
function SiteIcon({ domain, Fallback, size = 20 }) {
    const [err, setErr] = useState(false);
    const url = faviconUrl(domain);
    const inner = Math.max(10, size - 7);
    return (
        <span style={{ width: size, height: size, borderRadius: "50%", background: "#fff", border: "1px solid rgba(0,0,0,0.08)", display: "inline-flex", alignItems: "center", justifyContent: "center", overflow: "hidden", flexShrink: 0 }}>
            {url && !err ? <img src={url} alt="" width={inner} height={inner} onError={() => setErr(true)} /> : <Fallback size={inner} style={{ color: "var(--text-light)" }} />}
        </span>
    );
}

const GRID = "20px minmax(0,1fr) 18px minmax(0,1fr) 20px";

export default function CompetitorMappingPanel({
    url,
    competitorName,
    ownerName = "your store",
    pageLimit = 5,
    onPageSelection,
    onMappingChange,
    isActive = true,
}) {
    const [loading, setLoading] = useState(true);
    const [owner, setOwner] = useState(null);           // { domain, collections, productTotal }
    const [compCollections, setCompCollections] = useState([]);
    const [compProductTotal, setCompProductTotal] = useState(null);
    const [rows, setRows] = useState([]);
    const loadedRef = useRef("");

    const ownerCols = owner?.collections || [];
    const compDomain = useMemo(() => { try { return new URL(withProto(url)).hostname.replace(/^www\./, ""); } catch { return ""; } }, [url]);

    useEffect(() => {
        if (!isActive || !url) return;
        const key = norm(url);
        if (loadedRef.current === key) return;
        let alive = true;
        setLoading(true);
        Promise.all([getWorkspaceRecon().catch(() => null), previewCollections(url).catch(() => null)])
            .then(([recon, preview]) => {
                if (!alive) return;
                const notEmpty = (cols) => (cols || []).filter((c) => c?.url && (c.productCount == null || Number(c.productCount) > 0));
                const o = recon?.owner ? { ...recon.owner, collections: notEmpty(recon.owner.collections) } : null;
                const cc = notEmpty(preview?.collections);
                setOwner(o);
                setCompCollections(cc);
                setCompProductTotal(Number(preview?.productTotal) || null);
                setRows(buildRows(o?.collections || [], cc));
                loadedRef.current = key;
                setLoading(false);
            })
            .catch(() => { if (alive) setLoading(false); });
        return () => { alive = false; };
    }, [isActive, url]);

    // Emit selection + mapping to the parent whenever the rows change.
    useEffect(() => {
        const tracked = rows.filter((r) => r.tracked && norm(r.ownerUrl) && norm(r.compUrl));
        onPageSelection?.(tracked.map((r) => norm(r.compUrl)));
        onMappingChange?.(tracked.map((r) => ({ workspaceUrl: norm(r.ownerUrl), competitorUrl: norm(r.compUrl), status: "matched" })));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [rows]);

    const patchRow = (key, patch) => setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)));
    const removeRow = (key) => setRows((prev) => prev.filter((r) => r.key !== key));
    const addManualRow = () => setRows((prev) => [...prev, { key: uid("man"), kind: "manual", ownerUrl: NONE, ownerName: "", compUrl: NONE, compName: "", tracked: false, customOwner: true, customComp: true }]);

    const compCount = rows.filter((r) => r.tracked && norm(r.compUrl)).length;
    const [openGroups, setOpenGroups] = useState({});

    // Precompute the dropdown option lists ONCE (not per row per render) — building
    // ~200 option objects per row was the main source of lag.
    const ownerOptions = useMemo(() => ownerCols.map((col) => ({ value: norm(col.url), label: `${col.name || col.handle}${col.childCount ? ` (+${col.childCount})` : ""}`, col })), [ownerCols]);
    const compOptions = useMemo(() => compCollections.map((col) => ({ value: norm(col.url), label: `${col.name || col.handle}${col.childCount ? ` (+${col.childCount})` : ""}`, col })), [compCollections]);

    const canEnable = (r, nextOwner, nextComp) => {
        const oUrl = norm(nextOwner ?? r.ownerUrl);
        const cUrl = norm(nextComp ?? r.compUrl);
        if (!oUrl || !cUrl) return false;
        if (compCount >= pageLimit && !r.tracked) return false;
        for (const r2 of rows) {
            if (r2.key === r.key || !r2.tracked) continue;
            if (norm(r2.ownerUrl) === oUrl || norm(r2.compUrl) === cUrl) return false;
        }
        return true;
    };

    const toggleTracked = (r, checked) => { if (checked && !canEnable(r)) return; patchRow(r.key, { tracked: checked }); };
    const setOwnerChoice = (r, v) => { const patch = { customOwner: false, ownerUrl: v }; if (v && !r.tracked && canEnable(r, v, undefined)) patch.tracked = true; patchRow(r.key, patch); };
    const setCompChoice = (r, v) => { const patch = { customComp: false, compUrl: v }; if (v && !r.tracked && canEnable(r, undefined, v)) patch.tracked = true; patchRow(r.key, patch); };

    const fit = useMemo(() => {
        const matched = rows.filter((r) => r.kind === "matched").length;
        const cats = ownerCols.length;
        const ratio = cats ? matched / cats : 0;
        if (ratio >= 0.6) return { label: "Strong fit", tone: "var(--secondary)", matched, cats };
        if (ratio >= 0.3) return { label: "Partial fit", tone: "var(--accent)", matched, cats };
        return { label: "Weak fit", tone: "var(--danger, #dc2626)", matched, cats };
    }, [rows, ownerCols]);

    if (loading) {
        return (
            <div className="flex items-center justify-center gap-2 py-16" style={{ color: "var(--text-light)" }}>
                <Loader2 className="h-5 w-5 animate-spin" /> Reading {competitorName || "the competitor"}…
            </div>
        );
    }

    const labelForUrl = (cols, u) => { const c = (cols || []).find((x) => norm(x.url) === norm(u)); return c ? c.name || c.handle : slugOf(u).replace(/[-_]+/g, " ").trim() || u; };
    const openLink = (u) => (
        <a href={u || undefined} target="_blank" rel="noreferrer" title={u ? "Open page" : ""} onClick={(e) => e.stopPropagation()} className="grid h-6 w-6 shrink-0 place-items-center rounded-md" style={{ pointerEvents: u ? "auto" : "none" }}>
            <ExternalLink className="h-3.5 w-3.5" style={{ color: u ? "var(--accent)" : "var(--border)" }} />
        </a>
    );

    const renderRow = (r) => {
        const ownerEditable = r.kind === "compOnly" || r.kind === "manual";
        const compEditable = r.kind !== "compOnly";
        const isPair = !!(norm(r.ownerUrl) && norm(r.compUrl));
        const used = { o: new Set(), c: new Set() };
        for (const r2 of rows) { if (r2.key === r.key || !r2.tracked) continue; if (r2.ownerUrl) used.o.add(norm(r2.ownerUrl)); if (r2.compUrl) used.c.add(norm(r2.compUrl)); }
        const dup = isPair && (used.o.has(norm(r.ownerUrl)) || used.c.has(norm(r.compUrl)));
        const canTrack = canEnable(r);
        const dimmed = isPair && !r.tracked && !canTrack;
        const checkDisabled = !r.tracked && !canTrack;

        const oObj = ownerCols.find((x) => norm(x.url) === norm(r.ownerUrl)) || { url: r.ownerUrl };
        const cObj = compCollections.find((x) => norm(x.url) === norm(r.compUrl)) || { url: r.compUrl };
        const pct = isPair ? matchScore(oObj, cObj) : 0;
        const pctColor = pct >= 75 ? "#0f766e" : pct >= 45 ? "#a16207" : "#6b7280";

        const fieldBox = (label, u) => (
            <div className="flex h-9 min-w-0 items-center gap-1 rounded-lg border px-2.5" style={{ borderColor: "var(--border)", background: "var(--bg)" }}>
                <span className="min-w-0 flex-1 truncate text-sm font-semibold" style={{ color: "var(--text)" }}>{label || "—"}</span>
                {openLink(u)}
            </div>
        );
        const picker = (side) => {
            const isOwner = side === "owner";
            const urlOnly = r.kind === "manual";
            const isCustom = urlOnly || (isOwner ? r.customOwner : r.customComp);
            const val = isOwner ? r.ownerUrl : r.compUrl;
            const usedSet = isOwner ? used.o : used.c;
            const opts = (isOwner ? ownerOptions : compOptions).filter((o) => !usedSet.has(o.value) || o.value === norm(val));
            const refUrl = norm(isOwner ? r.compUrl : r.ownerUrl);
            const refObj = refUrl ? (isOwner ? compCollections : ownerCols).find((x) => norm(x.url) === refUrl) : null;
            const suggested = refObj ? opts.map((o) => ({ v: o.value, s: isOwner ? matchScore(o.col, refObj) : matchScore(refObj, o.col) })).filter((x) => x.s > 0).sort((a, b) => b.s - a.s).slice(0, 5).map((x) => x.v) : [];
            const toggle = () => patchRow(r.key, isOwner ? { customOwner: !r.customOwner, ownerUrl: NONE, tracked: false } : { customComp: !r.customComp, compUrl: NONE, tracked: false });
            const setUrl = (v) => patchRow(r.key, isOwner ? { ownerUrl: withProto(v) } : { compUrl: withProto(v) });
            return (
                <div className="flex min-w-0 items-center gap-1">
                    {isCustom ? (
                        <input value={val} onChange={(e) => setUrl(e.target.value)} placeholder={`${isOwner ? ownerName : competitorName} page URL`} className="h-9 min-w-0 flex-1 rounded-lg border px-2.5 text-sm" style={{ borderColor: "var(--border)", background: "var(--bg)", color: "var(--text)" }} />
                    ) : (
                        <SearchSelect value={val || NONE} placeholder={`+ Add ${isOwner ? ownerName : competitorName} page`} options={opts} suggested={suggested} onChange={(v) => (isOwner ? setOwnerChoice(r, v) : setCompChoice(r, v))} />
                    )}
                    {!urlOnly && (
                        <button type="button" onClick={toggle} title={isCustom ? "Choose from catalog" : "Paste a URL"} className="grid h-6 w-6 shrink-0 place-items-center rounded-md">
                            {isCustom ? <LayoutGrid className="h-3.5 w-3.5" style={{ color: "var(--text-light)" }} /> : <Link className="h-3.5 w-3.5" style={{ color: "var(--text-light)" }} />}
                        </button>
                    )}
                    {openLink(val)}
                </div>
            );
        };

        return (
            <div key={r.key} className="rounded-xl border p-2 transition-colors" style={{ borderColor: r.tracked ? "var(--accent)" : "var(--border)", background: r.tracked ? "color-mix(in srgb, var(--accent) 5%, var(--card))" : "var(--card)", opacity: dimmed ? 0.55 : 1 }}>
                <div className="grid items-center gap-2" style={{ gridTemplateColumns: GRID }}>
                    <input type="checkbox" checked={!!r.tracked} disabled={checkDisabled} onChange={(e) => toggleTracked(r, e.target.checked)} className="h-4 w-4 accent-[var(--accent)]" />
                    <div className="min-w-0">{ownerEditable ? picker("owner") : fieldBox(r.ownerName, r.ownerUrl)}</div>
                    <ArrowRight className="h-4 w-4 justify-self-center" style={{ color: "var(--text-light)" }} />
                    <div className="min-w-0">{compEditable ? picker("comp") : fieldBox(r.compName, r.compUrl)}</div>
                    {r.kind === "manual" ? <button type="button" onClick={() => removeRow(r.key)} title="Remove" className="justify-self-center"><X className="h-4 w-4" style={{ color: "var(--text-light)" }} /></button> : <span />}
                </div>
                {(pct > 0 || dup) && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-2" style={{ paddingLeft: 28 }}>
                        {pct > 0 && <span className="rounded-full px-1.5 py-0.5 text-[10px] font-bold" style={{ background: `color-mix(in srgb, ${pctColor} 14%, var(--card))`, color: pctColor }}>{pct}% match</span>}
                        {dup && <span className="text-[11px]" style={{ color: "var(--danger, #dc2626)" }}>Already mapped in another row</span>}
                    </div>
                )}
            </div>
        );
    };

    const renderGroup = (kind, title) => {
        const groupRows = rows.filter((r) => r.kind === kind);
        if (!groupRows.length) return null;
        const matched = kind === "matched";
        const onlyGroup = kind === "ownerOnly" || kind === "compOnly";
        const tone = matched ? "#4ecdc4" : onlyGroup ? "#eab308" : null;
        const panel = tone ? { background: `color-mix(in srgb, ${tone} 8%, var(--card))`, border: `1px solid color-mix(in srgb, ${tone} 40%, transparent)` } : { background: "var(--bg)", border: "1px solid var(--border)" };
        const headerColor = matched ? "var(--secondary-dark, #0f6e56)" : onlyGroup ? "#a16207" : "var(--text-light)";
        // Big groups start COLLAPSED — rendering hundreds of dropdown rows at once
        // freezes the UI. Also keep a group open if it already has tracked rows.
        const big = groupRows.length > 12;
        const hasTracked = groupRows.some((r) => r.tracked);
        const open = kind in openGroups ? openGroups[kind] : (!big || hasTracked);
        return (
            <div className="rounded-2xl p-3" style={panel}>
                <button type="button" onClick={() => setOpenGroups((p) => ({ ...p, [kind]: !(kind in p ? p[kind] : (!big || hasTracked)) }))} className="flex w-full items-center justify-center gap-2 pb-1">
                    <span className="text-[13px] font-bold uppercase tracking-wider" style={{ color: headerColor }}>{title} · {groupRows.length}</span>
                    {big && <ChevronDown className="h-3.5 w-3.5 transition-transform" style={{ color: headerColor, transform: open ? "none" : "rotate(-90deg)" }} />}
                </button>
                {open
                    ? <div className="mt-1.5 space-y-1.5">{groupRows.map(renderRow)}</div>
                    : <p className="text-center text-xs" style={{ color: "var(--text-light)" }}>Tap to show {groupRows.length} — or map from the groups above</p>}
            </div>
        );
    };

    const compCats = compCollections.length;
    return (
        <div className="space-y-4">
            {/* Header band */}
            <div className="overflow-hidden rounded-2xl">
                <div className="p-5" style={{ background: "var(--primary)" }}>
                    <div className="flex flex-wrap items-center gap-2.5">
                        <span className="inline-flex items-center gap-2 text-lg" style={{ color: "#fff", fontWeight: 800 }}>
                            <SiteIcon domain={owner?.domain} Fallback={Store} size={26} /> {ownerName}
                            <span style={{ color: "rgba(255,255,255,0.55)", fontWeight: 400 }}>vs</span>
                            <SiteIcon domain={compDomain} Fallback={Target} size={26} /> {competitorName}
                        </span>
                        <span className="rounded-full px-2.5 py-1 text-xs font-bold" style={{ background: fit.tone, color: "#fff" }}>{fit.label}</span>
                        <span className="text-sm" style={{ color: "rgba(255,255,255,0.8)" }}>matches {fit.matched} of {ownerName}'s {fit.cats} categories</span>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-[13px]" style={{ color: "rgba(255,255,255,0.75)" }}>
                        <span>{ownerName}: {ownerCols.length} categories{owner?.productTotal ? ` · ${Number(owner.productTotal).toLocaleString()} products` : ""}</span>
                        <span>{competitorName}: {compCats} categories{compProductTotal ? ` · ${compProductTotal.toLocaleString()} products` : ""}</span>
                    </div>
                </div>

                <div className="p-4">
                    <div className="mb-3 mt-2 grid items-center gap-2 px-0.5 text-[13px] font-bold uppercase tracking-wider" style={{ gridTemplateColumns: GRID, color: "var(--text-light)" }}>
                        <span />
                        <span className="inline-flex items-center justify-center gap-1.5"><SiteIcon domain={owner?.domain} Fallback={Store} size={18} /> {ownerName} pages</span>
                        <span />
                        <span className="inline-flex items-center justify-center gap-1.5"><SiteIcon domain={compDomain} Fallback={Target} size={18} /> {competitorName} pages</span>
                        <span />
                    </div>

                    <div className="space-y-4">
                        {renderGroup("matched", "Matched — on both sites")}
                        {renderGroup("ownerOnly", `Only on ${ownerName}`)}
                        {renderGroup("compOnly", `Only on ${competitorName}`)}
                        {renderGroup("manual", "Added by URL")}
                    </div>

                    <button type="button" onClick={addManualRow} className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed px-3 py-2.5 text-sm font-semibold transition-colors" style={{ borderColor: "var(--accent)", color: "var(--accent)", background: "color-mix(in srgb, var(--accent) 7%, var(--card))" }}>
                        <Plus className="h-4 w-4" /> Add a page by URL
                    </button>

                    <p className="mt-3 text-xs" style={{ color: "var(--text-light)" }}>
                        Tracking <strong style={{ color: "var(--text)" }}>{compCount}</strong> of {pageLimit} {pageLimit === 1 ? "page" : "pages"} <span style={{ color: "var(--text-light)" }}>+ homepage</span> for {competitorName}{compCount >= pageLimit ? " · limit reached" : ""}.
                    </p>
                </div>
            </div>
        </div>
    );
}
