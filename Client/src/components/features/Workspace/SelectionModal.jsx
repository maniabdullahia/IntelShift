import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Store, Target, Loader2, ExternalLink, Home, ArrowRight, ArrowLeft, Plus, Minus, X, Check, RefreshCw, Sparkles, Link, LayoutGrid, ChevronDown, LogOut } from "lucide-react";

import useWorkspaceStore from "../../../store/workspace.store";
import useAuthStore from "../../../store/auth.store";
import { getWorkspaceRecon, saveSelectionDraft, commitSelection, replaceCompetitor, markIntroCompleted } from "../../../api/workspace.api";
import { suggestCompetitors } from "../../../api/utils.api";
import Swal from "../../shared/Alert";
import { matchScore, slugOf, segNorm, segDisplay, SEG_CURATED, SEG_ORDER, stripSeg } from "../../../utils/collectionMatch";
import SearchSelect from "../../shared/SearchSelect";

/* ────────────────────────────────────────────────────────────────
   Capture-first: in-workspace selection + mapping panel.
   A two-column reconciliation per competitor:
     • Matched (auto)     — pages on BOTH sides, paired + pre-selected
     • Only on your site  — your pages with no competitor match (+ Add on their side)
     • Only on their site — their pages with no match on yours (+ Add on your side)
     • Added by URL        — rows you add manually (product / any page), both sides
   Either side accepts a pasted URL. Page counters enforce the plan limit per
   site. Committing creates the tracked pages and starts the deep analysis.
──────────────────────────────────────────────────────────────── */

const CUSTOM = "__custom__";
const NONE = "";

const norm = (u) => String(u || "").trim().replace(/\/+$/, "");
const withProto = (u) => {
    const s = String(u || "").trim();
    if (!s) return "";
    if (/^https?:\/\//i.test(s)) return s;
    if (!s.includes(".")) return s;
    return `https://${s.replace(/^\/+/, "")}`;
};
// Matching stack (tokenize, synonyms, segments, matchScore) lives in
// ../../../utils/collectionMatch and is imported above — shared with the
// tracked-pages manager so the tuned logic stays in one place.

let ROW_SEQ = 0;
const uid = (p) => `${p}${Date.now().toString(36)}${ROW_SEQ++}`;

// Only pairs at/above this confidence are auto-suggested in "Matched". Weaker
// lexical overlaps land in the "Only on…" groups instead (still selectable there).
const MATCH_MIN = 40;
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
    const mk = (kind, o, c, tracked) => ({
        key: uid(kind), kind,
        ownerUrl: o ? norm(o.url) : NONE, ownerName: o ? o.name || o.handle : "",
        compUrl: c ? norm(c.url) : NONE, compName: c ? c.name || c.handle : "",
        tracked, customOwner: false, customComp: false,
    });
    for (const { oi, ci } of scored) {
        if (usedO.has(oi) || usedC.has(ci)) continue;
        usedO.add(oi); usedC.add(ci);
        // Matched pairs are SUGGESTED (highlighted), not auto-tracked — the user
        // opts in by ticking them.
        rows.push(mk("matched", ownerCols[oi], compCols[ci], false));
    }
    ownerCols.forEach((o, oi) => { if (!usedO.has(oi)) rows.push(mk("ownerOnly", o, null, false)); });
    compCols.forEach((c, ci) => { if (!usedC.has(ci)) rows.push(mk("compOnly", null, c, false)); });
    return rows;
}

const overlay = {
    position: "fixed", inset: 0, zIndex: 60, background: "rgba(15,15,30,0.55)",
    backdropFilter: "blur(3px)", display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
};
const modalBox = {
    width: "100%", maxWidth: 960, maxHeight: "90vh", display: "flex", flexDirection: "column",
    background: "var(--card)", borderRadius: 20, boxShadow: "var(--shadow-lg)", overflow: "hidden", position: "relative",
};
const selectStyle = { borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" };
const inputStyle = { borderColor: "var(--border)", background: "var(--bg)", color: "var(--text)" };
const GRID = "20px minmax(0,1fr) 18px minmax(0,1fr) 20px";

const faviconUrl = (domain) => (domain ? `https://www.google.com/s2/favicons?sz=64&domain=${encodeURIComponent(domain)}` : "");

// A site's favicon in a round white badge (like the app logo), falling back to a
// lucide icon if it can't load.
function SiteIcon({ domain, Fallback, size = 20 }) {
    const [err, setErr] = useState(false);
    const url = faviconUrl(domain);
    const inner = Math.max(10, size - 7);
    return (
        <span
            style={{ width: size, height: size, borderRadius: "50%", background: "#fff", border: "1px solid rgba(0,0,0,0.08)", display: "inline-flex", alignItems: "center", justifyContent: "center", overflow: "hidden", flexShrink: 0 }}
        >
            {!url || err
                ? <Fallback size={inner} style={{ color: "var(--text-light)" }} />
                : <img src={url} alt="" width={inner} height={inner} onError={() => setErr(true)} style={{ objectFit: "contain" }} />}
        </span>
    );
}

function Counter({ n, limit }) {
    const full = n >= limit;
    return (
        <span
            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-bold"
            style={{
                background: full ? "color-mix(in srgb, var(--danger, #dc2626) 12%, var(--card))" : "color-mix(in srgb, var(--secondary) 12%, var(--card))",
                color: full ? "var(--danger, #dc2626)" : "var(--secondary-dark, var(--secondary))",
            }}
            title={full ? "Plan limit reached" : "Pages selected"}
        >
            {n}/{limit}
        </span>
    );
}

// In-modal analysis progress — shown after commit (setupStage="analyzing") so the
// user stays right here instead of bouncing to a separate screen. Polls the
// workspace and auto-opens the first report the moment it's ready.
function AnalyzingView() {
    const workspace = useWorkspaceStore((s) => s?.workspace);
    const rivals = (workspace?.competitors || []).filter((c) => c?.role === "Competitor");
    const allPages = rivals.flatMap((c) => c?.pages || []);
    const done = (s) => String(s || "").toLowerCase() === "completed";
    const failed = (s) => ["failed", "error", "blocked"].includes(String(s || "").toLowerCase());
    const settled = (s) => done(s) || failed(s);
    const pagesTotal = allPages.length;
    const pagesSettled = allPages.filter((p) => settled(p?.scanStatus)).length;
    const compTotal = rivals.length;
    const compSettled = rivals.filter((c) => settled(c?.scanStatus)).length;
    const analysis = workspace?.analysis?.[0];

    const pagesFrac = pagesTotal ? pagesSettled / pagesTotal : 0;
    const compFrac = compTotal ? compSettled / compTotal : 0;
    let percent = Math.round(50 * pagesFrac + 25 * compFrac + (analysis ? 25 : 0));
    if (analysis) percent = 100;
    else if (percent >= 100) percent = 99;
    else if (percent < 5 && pagesTotal > 0) percent = 5;

    const step = analysis
        ? "Report ready"
        : pagesTotal === 0 || pagesSettled < pagesTotal
            ? "Analyzing pages…"
            : compSettled < compTotal
                ? "Comparing competitors…"
                : "Building your report…";

    // Keep the workspace fresh (socket usually pushes this, polling is a backstop).
    // The redirect to the finished report is handled in SelectionModal (which stays
    // mounted through the stage change), so it isn't missed when this view unmounts.
    useEffect(() => {
        const t = setInterval(() => { useWorkspaceStore.getState().syncWorkspace().catch(() => {}); }, 4000);
        return () => clearInterval(t);
    }, []);

    return (
        <div style={overlay}>
            <div style={{ ...modalBox, maxWidth: 560 }}>
                <div className="p-8 text-center">
                    <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full" style={{ background: "color-mix(in srgb, var(--secondary) 12%, var(--card))" }}>
                        <Loader2 className="h-7 w-7 animate-spin" style={{ color: "var(--secondary)" }} />
                    </div>
                    <h2 className="text-xl font-extrabold" style={{ color: "var(--primary)" }}>Building your first report</h2>
                    <p className="mx-auto mt-1.5 max-w-sm text-sm" style={{ color: "var(--text-light)" }}>
                        We're analyzing the pages you selected across each competitor. This can take a few minutes — you can leave this open and we'll take you to your report automatically.
                    </p>

                    <div className="mt-6">
                        <div className="mb-1.5 flex items-center justify-between text-xs font-semibold" style={{ color: "var(--text-light)" }}>
                            <span>{step}</span>
                            <span>{percent}%</span>
                        </div>
                        <div className="h-2 w-full overflow-hidden rounded-full" style={{ background: "var(--border)" }}>
                            <div className="h-full rounded-full transition-all" style={{ width: `${percent}%`, background: "var(--secondary)" }} />
                        </div>
                        {pagesTotal > 0 && (
                            <p className="mt-2 text-[11px]" style={{ color: "var(--text-light)" }}>
                                {pagesSettled} of {pagesTotal} pages · {compSettled} of {compTotal} competitors
                            </p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default function SelectionModal() {
    const workspace = useWorkspaceStore((s) => s?.workspace);
    const stage = workspace?.setupStage;
    const navigate = useNavigate();
    const user = useAuthStore((s) => s?.user);
    const logout = useAuthStore((s) => s?.logout);
    const pageLimit = Math.max(1, user?.subscription?.planId?.limits?.pagesPerCompetitor ?? 5);
    // Growth/Pro carry many pages — pre-select the matched pairs so the user isn't
    // ticking dozens by hand (they can still Remove all / adjust).
    const planName = String(user?.subscription?.planId?.name || user?.subscription?.planId?.displayName || "").toLowerCase();
    const autoSelectMatched = planName === "growth" || planName === "pro";

    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);
    const [rowsByComp, setRowsByComp] = useState({});
    // Row source filter: false = only categories linked in the site's nav/menu
    // (less noise), true = every category we found (incl. unlinked/hidden ones).
    const [showAllCats, setShowAllCats] = useState(false);
    // Accordion: the single open segment per group (keyed cid:kind → segment|null).
    const [openSeg, setOpenSeg] = useState({});
    const [submitting, setSubmitting] = useState(false);
    // Replace-competitor panel
    const [replacing, setReplacing] = useState(null);       // the competitor being replaced
    const [suggestions, setSuggestions] = useState([]);
    const [suggestLoading, setSuggestLoading] = useState(false);
    const [manualUrl, setManualUrl] = useState("");
    const [replaceBusy, setReplaceBusy] = useState(false);
    // Category-query search inside the Replace panel.
    const [showQueryInput, setShowQueryInput] = useState(false);
    const [catInput, setCatInput] = useState("");
    const [queryMode, setQueryMode] = useState(false);   // true once query results replace the stored list
    // Draft auto-save: gate saves until the initial load hydrates the rows.
    const hydratedRef = useRef(false);
    const [draftSavedAt, setDraftSavedAt] = useState(null);

    useEffect(() => {
        if (stage !== "selecting") return;
        let alive = true;
        setLoading(true);
        hydratedRef.current = false;
        getWorkspaceRecon()
            .then((d) => {
                if (!alive) return;
                // Drop empty (0-product) collections so dead/empty ones can't be
                // picked or mapped. Keep null/unknown counts (non-Shopify platforms).
                const notEmpty = (cols) => (cols || []).filter((c) => c.productCount == null || Number(c.productCount) > 0);
                if (d?.owner) d.owner.collections = notEmpty(d.owner.collections);
                if (Array.isArray(d?.competitors)) d.competitors = d.competitors.map((c) => ({ ...c, collections: notEmpty(c.collections) }));
                setData(d);
                const ownerCols = d?.owner?.collections || [];
                const draft = d?.draft && typeof d.draft === "object" ? d.draft : null;
                const next = {};
                for (const c of d?.competitors || []) {
                    // Restore the saved draft for this competitor if we have one.
                    if (draft && Array.isArray(draft[c.competitorId])) {
                        next[c.competitorId] = draft[c.competitorId];
                        continue;
                    }
                    let rows = buildRows(ownerCols, c.collections || []);
                    // Auto-select matched pairs on Growth/Pro (up to the per-competitor limit).
                    if (autoSelectMatched) {
                        let n = 0;
                        rows = rows.map((r) => (r.kind === "matched" && n < pageLimit ? (n++, { ...r, tracked: true }) : r));
                    }
                    next[c.competitorId] = rows;
                }
                setRowsByComp(next);
                setLoading(false);
                // Allow auto-save only after this initial hydration settles.
                requestAnimationFrame(() => { hydratedRef.current = true; });
            })
            .catch(() => { if (alive) setLoading(false); });
        return () => { alive = false; };
    }, [stage]);

    // Auto-save the draft (debounced) whenever selections change post-hydration.
    useEffect(() => {
        if (!hydratedRef.current || stage !== "selecting") return;
        const t = setTimeout(() => {
            saveSelectionDraft(rowsByComp).then(() => setDraftSavedAt(Date.now())).catch(() => {});
        }, 800);
        return () => clearTimeout(t);
    }, [rowsByComp, stage]);

    // Open the report the moment analysis completes. This MUST live here (not in
    // AnalyzingView): when the run finishes, setupStage flips to "ready" and the
    // analysis lands in the SAME store update, so AnalyzingView unmounts (stage no
    // longer "analyzing") before it can navigate — leaving the user on a stale page.
    // SelectionModal is always mounted, so this effect always fires. We gate it on
    // "was analyzing" so it only redirects on the analyzing→done transition, never on
    // a normal later visit to a page while an old analysis exists.
    const wasAnalyzingRef = useRef(false);
    useEffect(() => {
        if (stage === "analyzing") wasAnalyzingRef.current = true;
    }, [stage]);
    useEffect(() => {
        const a = workspace?.analysis?.[0];
        if (a?.analysisId && wasAnalyzingRef.current) {
            wasAnalyzingRef.current = false;
            markIntroCompleted().catch(() => {});
            navigate(`/analysis/${a.analysisId}`, { replace: true });
        }
    }, [workspace?.analysis, navigate]);

    const owner = data?.owner;
    const competitors = useMemo(() => data?.competitors || [], [data]);

    // Focus categories (from onboarding): a priority LENS, never a filter. Used to
    // rank matched pairs first and to score competitor fit by focus coverage.
    const focusList = (workspace?.focusMode === "selected" && Array.isArray(workspace?.focusCategories))
        ? workspace.focusCategories : [];
    const focusKey = focusList.join("|").toLowerCase();
    const focusRank = useMemo(() => {
        const m = new Map();
        focusList.forEach((c, i) => m.set(String(c || "").toLowerCase().trim(), i));
        return m;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [focusKey]);
    const hasFocus = focusRank.size > 0;
    // A collection is a "focus" one if its name/handle matches a focus category.
    const focusRankOfCol = (col) => {
        if (!col) return Infinity;
        const cands = [col.name, col.handle].map((x) => String(x || "").toLowerCase().trim());
        let best = Infinity;
        for (const c of cands) {
            if (focusRank.has(c)) best = Math.min(best, focusRank.get(c));
        }
        return best;
    };
    // Wizard: review one competitor at a time (Next/Back).
    const [step, setStep] = useState(0);
    const total = competitors.length;
    const idx = Math.min(step, Math.max(0, total - 1));
    const activeComp = competitors[idx] || null;
    const activeCount = activeComp ? (rowsByComp[activeComp.competitorId] || []).filter((r) => r.tracked && r.ownerUrl && r.compUrl).length : 0;

    const ownerTrackedSet = useMemo(() => {
        const s = new Set();
        Object.values(rowsByComp).forEach((rows) => rows.forEach((r) => { if (r.tracked && r.ownerUrl) s.add(norm(r.ownerUrl)); }));
        return s;
    }, [rowsByComp]);
    const ownerCount = ownerTrackedSet.size;
    const compCount = (cid) => (rowsByComp[cid] || []).filter((r) => r.tracked && r.compUrl).length;

    // Nav-hierarchy lookups: sub-category counts + parent, so the picker can say
    // "covers N sub-categories" and flag a page already covered by a tracked parent.
    const ownerCols0 = owner?.collections || [];
    const ownerMeta = useMemo(() => {
        const m = {};
        ownerCols0.forEach((c) => { m[norm(c.url)] = { childCount: c.childCount || 0, parentName: c.parentName || null }; });
        return m;
    }, [ownerCols0]);
    const ownerNameToUrl = useMemo(() => {
        const m = {};
        ownerCols0.forEach((c) => { if (c.name) m[String(c.name).toLowerCase()] = norm(c.url); });
        return m;
    }, [ownerCols0]);
    const compMetaByCid = useMemo(() => {
        const m = {};
        competitors.forEach((c) => {
            const mm = {};
            (c.collections || []).forEach((x) => { mm[norm(x.url)] = { childCount: x.childCount || 0 }; });
            m[c.competitorId] = mm;
        });
        return m;
    }, [competitors]);

    if (stage === "analyzing") return <AnalyzingView />;
    if (stage !== "selecting") return null;

    // A page is trackable only as a COMPLETE owner↔competitor pair (mapped-only),
    // and only while it stays within the per-site plan limit.
    const canEnable = (cid, r, nextOwner, nextComp) => {
        const oUrl = norm(nextOwner ?? r.ownerUrl);
        const cUrl = norm(nextComp ?? r.compUrl);
        if (!oUrl || !cUrl) return false; // both sides required
        // Plan limit is per COMPETITOR (pagesPerCompetitor) — each competitor can
        // track up to pageLimit pairs, independently of the others.
        if (compCount(cid) >= pageLimit) return false;
        // A page can only be used in ONE mapping — reusing a page that's already
        // MAPPED (tracked) elsewhere would be silently dropped by the backend's
        // per-(competitor,url) dedup. Unmapped rows don't reserve a page.
        for (const r2 of rowsByComp[cid] || []) {
            if (r2.key === r.key || !r2.tracked) continue;
            if (norm(r2.ownerUrl) === oUrl || norm(r2.compUrl) === cUrl) return false;
        }
        return true;
    };

    const patchRow = (cid, key, patch) =>
        setRowsByComp((prev) => ({ ...prev, [cid]: (prev[cid] || []).map((r) => (r.key === key ? { ...r, ...patch } : r)) }));
    const removeRow = (cid, key) =>
        setRowsByComp((prev) => ({ ...prev, [cid]: (prev[cid] || []).filter((r) => r.key !== key) }));
    // Untrack every selected pair for one competitor.
    const clearComp = (cid) =>
        setRowsByComp((prev) => ({ ...prev, [cid]: (prev[cid] || []).map((r) => (r.tracked ? { ...r, tracked: false } : r)) }));
    const addManualRow = (cid) =>
        setRowsByComp((prev) => ({ ...prev, [cid]: [...(prev[cid] || []), { key: uid("man"), kind: "manual", ownerUrl: NONE, ownerName: "", compUrl: NONE, compName: "", tracked: false, customOwner: true, customComp: true }] }));

    const toggleTracked = (cid, r, checked) => {
        if (checked && !canEnable(cid, r)) return;
        patchRow(cid, r.key, { tracked: checked });
    };
    const setCompChoice = (cid, r, value) => {
        if (value === CUSTOM) { patchRow(cid, r.key, { customComp: true, compUrl: NONE }); return; }
        const patch = { customComp: false, compUrl: value };
        if (value && !r.tracked && canEnable(cid, r, undefined, value)) patch.tracked = true;
        patchRow(cid, r.key, patch);
    };
    const setOwnerChoice = (cid, r, value) => {
        if (value === CUSTOM) { patchRow(cid, r.key, { customOwner: true, ownerUrl: NONE }); return; }
        const patch = { customOwner: false, ownerUrl: value };
        if (value && !r.tracked && canEnable(cid, r, value, undefined)) patch.tracked = true;
        patchRow(cid, r.key, patch);
    };

    const handleSubmit = async () => {
        if (submitting) return;
        // The last competitor must have at least one page chosen.
        if (activeCount === 0) {
            Swal.fire({ icon: "info", title: "Pick at least one page", text: `Choose at least one page for ${activeComp?.name || "this competitor"} before starting.` });
            return;
        }
        // If any competitor is below its page limit, confirm before starting.
        const incomplete = competitors.filter((c) => compCount(c.competitorId) < pageLimit);
        if (incomplete.length > 0) {
            const res = await Swal.fire({
                icon: "question",
                title: "Start analysis now?",
                text: `${incomplete.length} of ${competitors.length} competitor${competitors.length === 1 ? "" : "s"} ${incomplete.length === 1 ? "doesn't" : "don't"} have all ${pageLimit} pages selected yet. You can start now, or go back and complete them first.`,
                showCancelButton: true,
                confirmButtonText: "Start analysis",
                cancelButtonText: "Complete pages first",
            });
            if (!res.isConfirmed) return;
        }
        setSubmitting(true);
        try {
            const payload = {
                ownerPages: [...ownerTrackedSet],
                competitors: competitors.map((c) => ({
                    competitorId: c.competitorId,
                    pages: (rowsByComp[c.competitorId] || [])
                        .filter((r) => r.tracked && r.compUrl && norm(r.compUrl))
                        .map((r) => ({ url: norm(r.compUrl), mappedOwnerUrl: norm(r.ownerUrl) })),
                })),
            };
            await commitSelection(payload);
            // Flip to "analyzing" — the modal swaps to the in-place progress view
            // (AnalyzingView) instead of routing away to /intro.
            await useWorkspaceStore.getState().syncWorkspace();
        } catch (e) {
            // Some mapped pages 404'd — list them so the user can replace them.
            const dead = e?.response?.status === 422 ? e?.response?.data?.deadPages : null;
            if (Array.isArray(dead) && dead.length) {
                const rows = dead
                    .map((d) => `• ${d.label} <span style="color:var(--text-light)">(${d.side === "owner" ? ownerName : d.storeName})</span>`)
                    .join("<br/>");
                Swal.fire({
                    icon: "warning",
                    title: "Some pages are no longer reachable",
                    html: `These pages returned 404 and can't be analyzed. Remove or replace them, then start again:<br/><br/>${rows}`,
                    confirmButtonText: "OK, I'll fix them",
                });
            } else {
                Swal.fire({ icon: "error", title: "Couldn't start analysis", text: e?.response?.data?.message || e?.message || "Please try again." });
            }
        } finally {
            setSubmitting(false);
        }
    };

    const ownerName = owner?.name || "your store";

    const handleLogout = async () => {
        const res = await Swal.fire({
            icon: "question",
            title: "Log out?",
            text: "Your selections are saved — you'll pick up right here next time you log in.",
            showCancelButton: true,
            confirmButtonText: "Log out",
            cancelButtonText: "Stay",
        });
        if (!res.isConfirmed) return;
        try { await saveSelectionDraft(rowsByComp); } catch { /* best-effort */ }
        logout?.();
        navigate("/", { replace: true });
    };

    // Domains already in the workspace — never suggest these.
    const usedDomains = () =>
        new Set([owner, ...competitors].map((s) => String(s?.domain || "").toLowerCase()).filter(Boolean));

    const openReplace = (comp) => {
        setReplacing(comp);
        setManualUrl("");
        setQueryMode(false);
        setShowQueryInput(false);
        setCatInput("");
        // Show the STORED suggestions (generated in the background after onboarding) —
        // no live search, instant. Hide any already in the workspace this session.
        const have = usedDomains();
        setSuggestions((data?.suggestedCompetitors || []).filter((s) => !have.has(String(s.domain || "").toLowerCase())));
        setSuggestLoading(false);
    };

    // Category-query search inside Replace — mirrors onboarding's "target specific
    // categories". Results REPLACE the stored list (with a way back).
    const runReplaceQuery = async () => {
        const cats = catInput.split(",").map((c) => c.trim()).filter(Boolean);
        if (!cats.length || suggestLoading) return;
        setSuggestLoading(true);
        setQueryMode(true);
        setShowQueryInput(false);
        try {
            const res = await suggestCompetitors(owner?.url, workspace?.industry, [], owner?.currency || "", cats);
            const list = Array.isArray(res?.suggestions) ? res.suggestions : Array.isArray(res) ? res : [];
            const have = usedDomains();
            setSuggestions(list.filter((s) => !have.has(String(s.domain || "").toLowerCase())));
        } catch {
            setSuggestions([]);
        } finally {
            setSuggestLoading(false);
        }
    };
    const backToStored = () => {
        setQueryMode(false);
        const have = usedDomains();
        setSuggestions((data?.suggestedCompetitors || []).filter((s) => !have.has(String(s.domain || "").toLowerCase())));
    };
    const doReplace = async (url) => {
        if (!replacing || !url || replaceBusy) return;
        setReplaceBusy(true);
        try {
            // The server runs the SAME readiness + scale gate as onboarding
            // (homepage + collection + product reachable, not enterprise-scale)
            // before it accepts the swap, so an unreadable/bot-protected site is
            // rejected here instead of becoming a 0-category competitor.
            await replaceCompetitor(replacing.competitorId, url);
            await useWorkspaceStore.getState().syncWorkspace();
            navigate("/intro", { replace: true });
        } catch (e) {
            const code = e?.response?.data?.code;
            const reason = e?.response?.data?.message || e?.message || "Please try again.";
            const title =
                code === "ENTERPRISE" ? "This store needs a custom setup"
                : code === "UNREADABLE" ? "We couldn't read this store"
                : "Couldn't replace competitor";
            Swal.fire({ icon: code === "ENTERPRISE" ? "info" : "error", title, text: reason });
            setReplaceBusy(false);
        }
    };

    // Fit read: how many of the user's categories this competitor also carries.
    // When the user set focus categories, score fit by FOCUS coverage instead of
    // overall overlap — a competitor that matches what they actually care about is
    // a better fit than one matching many categories they don't.
    const fitOf = (cid) => {
        const rows = rowsByComp[cid] || [];
        const matchedRows = rows.filter((r) => r.kind === "matched");

        if (hasFocus) {
            const coveredFocus = new Set();
            for (const r of matchedRows) {
                const oc = (owner?.collections || []).find((x) => norm(x.url) === norm(r.ownerUrl));
                const rk = focusRankOfCol(oc);
                if (rk !== Infinity) coveredFocus.add(rk);
            }
            const covered = coveredFocus.size;
            const focusTotal = focusRank.size;
            const ratio = focusTotal ? covered / focusTotal : 0;
            const base = { matched: covered, ownerCats: focusTotal, focus: true };
            if (ratio >= 0.6) return { label: "Strong fit", tone: "var(--secondary)", ...base };
            if (ratio > 0) return { label: "Partial fit", tone: "var(--accent)", ...base };
            return { label: "Weak fit", tone: "var(--danger, #dc2626)", ...base };
        }

        const matched = matchedRows.length;
        const ownerCats = (owner?.collections || []).length;
        const ratio = ownerCats ? matched / ownerCats : 0;
        if (ratio >= 0.6) return { label: "Strong fit", tone: "var(--secondary)", matched, ownerCats };
        if (ratio >= 0.3) return { label: "Partial fit", tone: "var(--accent)", matched, ownerCats };
        return { label: "Weak fit", tone: "var(--danger, #dc2626)", matched, ownerCats };
    };

    // Display name for a page URL (from its collection, else the slug).
    const labelForUrl = (cols, url) => {
        const u = norm(url);
        const c = (cols || []).find((x) => norm(x.url) === u);
        return c ? (c.name || c.handle) : slugOf(url).replace(/[-_]+/g, " ").trim() || url;
    };

    const renderRow = (cid, comp, r, seg = "") => {
        const ownerCols = owner?.collections || [];
        const compCols = comp.collections || [];
        const ownerEditable = r.kind === "compOnly" || r.kind === "manual";
        const compEditable = r.kind !== "compOnly";
        const isPair = !!(norm(r.ownerUrl) && norm(r.compUrl));
        // Pages already MAPPED (in a tracked row) — excluded from this row's
        // dropdowns and used to flag a pasted duplicate. Unmapped pages still show.
        const used = { o: new Set(), c: new Set() };
        for (const r2 of rowsByComp[cid] || []) {
            if (r2.key === r.key || !r2.tracked) continue;
            if (r2.ownerUrl) used.o.add(norm(r2.ownerUrl));
            if (r2.compUrl) used.c.add(norm(r2.compUrl));
        }
        const dup = isPair && (used.o.has(norm(r.ownerUrl)) || used.c.has(norm(r.compUrl)));
        const canTrack = canEnable(cid, r);
        const dimmed = isPair && !r.tracked && !canTrack;
        const checkDisabled = !r.tracked && !canTrack;
        const checkTitle = !isPair
            ? "Map a page on both sides to track this"
            : dup
                ? "This page is already mapped in another row"
                : !canTrack
                    ? `Plan limit is ${pageLimit} pages per site`
                    : "";

        const oMeta = ownerMeta[norm(r.ownerUrl)] || {};
        const parentUrl = oMeta.parentName ? ownerNameToUrl[String(oMeta.parentName).toLowerCase()] : null;
        const covered = parentUrl && parentUrl !== norm(r.ownerUrl) && ownerTrackedSet.has(parentUrl);
        const cMeta = (compMetaByCid[cid] || {})[norm(r.compUrl)] || {};
        const hint = oMeta.childCount > 0
            ? `Covers ${oMeta.childCount} sub-categor${oMeta.childCount > 1 ? "ies" : "y"} on ${ownerName}`
            : covered
                ? `Already covered by ${oMeta.parentName}`
                : cMeta.childCount > 0
                    ? `${comp.name}'s page covers ${cMeta.childCount} sub-categories`
                    : null;

        // Live match confidence for the pair (~15 = near-perfect), shown as a tag.
        const oObj = ownerCols.find((x) => norm(x.url) === norm(r.ownerUrl)) || { url: r.ownerUrl };
        const cObj = compCols.find((x) => norm(x.url) === norm(r.compUrl)) || { url: r.compUrl };
        const matchPct = isPair ? matchScore(oObj, cObj) : 0;
        const pctColor = matchPct >= 75 ? "#0f766e" : matchPct >= 45 ? "#a16207" : "#6b7280";

        const linkIcon = (url) => (
            <a
                href={url || undefined}
                target="_blank"
                rel="noreferrer"
                title={url ? "Open page" : ""}
                onClick={(e) => e.stopPropagation()}
                className="grid h-6 w-6 shrink-0 place-items-center rounded-md"
                style={{ pointerEvents: url ? "auto" : "none", opacity: url ? 1 : 0.25 }}
            >
                <ExternalLink className="h-3.5 w-3.5" style={{ color: "var(--text-light)" }} />
            </a>
        );
        const fieldBox = (label, url, sub) => (
            <div className="flex h-9 min-w-0 items-center gap-1 rounded-lg border px-2.5" style={{ borderColor: "var(--border)", background: "var(--bg)" }}>
                {sub && <span className="shrink-0 text-sm" style={{ color: "var(--text-light)" }} title="Sub-category">↳</span>}
                <span className="min-w-0 flex-1 truncate text-sm font-semibold" style={{ color: "var(--text)" }}>{label || "—"}</span>
                {linkIcon(url)}
            </div>
        );
        const picker = (side) => {
            const isOwner = side === "owner";
            const urlOnly = r.kind === "manual"; // "Add by URL" rows are URL-only — no dropdown/toggle
            const isCustom = urlOnly || (isOwner ? r.customOwner : r.customComp);
            const val = isOwner ? r.ownerUrl : r.compUrl;
            const usedSet = isOwner ? used.o : used.c;
            // Hide pages already mapped elsewhere, but always keep this row's own value.
            const cols = (isOwner ? ownerCols : compCols).filter((o) => !usedSet.has(norm(o.url)) || norm(o.url) === norm(val));
            // Ranked suggestions vs the OTHER (fixed) side of this row — surfaces
            // close-but-unsure candidates at the top of the dropdown.
            const refUrl = norm(isOwner ? r.compUrl : r.ownerUrl);
            const refObj = refUrl ? (isOwner ? compCols : ownerCols).find((x) => norm(x.url) === refUrl) : null;
            const suggested = refObj
                ? cols
                    .map((o) => ({ v: norm(o.url), s: isOwner ? matchScore(o, refObj) : matchScore(refObj, o) }))
                    .filter((x) => x.s > 0)
                    .sort((a, b) => b.s - a.s)
                    .slice(0, 5)
                    .map((x) => x.v)
                : [];
            // Mode toggle: pick from the catalog dropdown or paste a URL. The icon
            // shows the OTHER mode — paste-url while the dropdown is up, catalog
            // while pasting.
            const toggle = () => patchRow(cid, r.key, isOwner
                ? { customOwner: !r.customOwner, ownerUrl: NONE, tracked: false }
                : { customComp: !r.customComp, compUrl: NONE, tracked: false });
            const setUrl = (v) => patchRow(cid, r.key, isOwner ? { ownerUrl: withProto(v) } : { compUrl: withProto(v) });
            return (
                <div className="flex min-w-0 items-center gap-1">
                    {isCustom ? (
                        <input value={val} onChange={(e) => setUrl(e.target.value)} placeholder={`${isOwner ? ownerName : comp.name} page URL`} className="h-9 min-w-0 flex-1 rounded-lg border px-2.5 text-sm" style={inputStyle} />
                    ) : (
                        <SearchSelect
                            value={val || NONE}
                            placeholder={`+ Add ${isOwner ? ownerName : comp.name} page`}
                            options={cols.map((o) => ({ value: norm(o.url), label: `${o.name || o.handle}${o.childCount ? ` (+${o.childCount})` : ""}` }))}
                            suggested={suggested}
                            onChange={(v) => (isOwner ? setOwnerChoice(cid, r, v) : setCompChoice(cid, r, v))}
                        />
                    )}
                    {!urlOnly && (
                        <button type="button" onClick={toggle} title={isCustom ? "Choose from catalog" : "Paste a URL"} className="grid h-6 w-6 shrink-0 place-items-center rounded-md">
                            {isCustom ? <LayoutGrid className="h-3.5 w-3.5" style={{ color: "var(--text-light)" }} /> : <Link className="h-3.5 w-3.5" style={{ color: "var(--text-light)" }} />}
                        </button>
                    )}
                    {linkIcon(val)}
                </div>
            );
        };

        return (
            <div
                key={r.key}
                className="rounded-xl border p-2 transition-colors"
                style={{
                    borderColor: r.tracked ? "var(--accent)" : "var(--border)",
                    background: r.tracked ? "color-mix(in srgb, var(--accent) 5%, var(--card))" : "var(--card)",
                    opacity: dimmed ? 0.55 : 1,
                }}
            >
                <div className="grid items-center gap-2" style={{ gridTemplateColumns: GRID }}>
                    <input
                        type="checkbox"
                        checked={!!r.tracked}
                        disabled={checkDisabled}
                        onChange={(e) => toggleTracked(cid, r, e.target.checked)}
                        className="h-4 w-4 accent-[var(--accent)]"
                        title={checkTitle}
                    />
                    <div className="min-w-0">{ownerEditable ? picker("owner") : fieldBox(stripSeg(r.ownerName, seg), r.ownerUrl, (oObj?.depth || 1) === 2)}</div>
                    <ArrowRight className="h-4 w-4 justify-self-center" style={{ color: "var(--text-light)" }} />
                    <div className="min-w-0">{compEditable ? picker("comp") : fieldBox(stripSeg(r.compName, seg), r.compUrl, (cObj?.depth || 1) === 2)}</div>
                    {r.kind === "manual"
                        ? <button type="button" onClick={() => removeRow(cid, r.key)} title="Remove" className="justify-self-center"><X className="h-4 w-4" style={{ color: "var(--text-light)" }} /></button>
                        : <span />}
                </div>
                {(matchPct > 0 || hint) && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-2" style={{ paddingLeft: 28 }}>
                        {matchPct > 0 && (
                            <span className="rounded-full px-1.5 py-0.5 text-[10px] font-bold" style={{ background: `color-mix(in srgb, ${pctColor} 14%, var(--card))`, color: pctColor }}>{matchPct}% match</span>
                        )}
                        {hint && <span className="text-[11px]" style={{ color: "var(--text-light)" }}>{hint}</span>}
                    </div>
                )}
            </div>
        );
    };

    const renderGroup = (cid, comp, kind, title) => {
        // "Live on site" filter — a row counts as live if either side's collection
        // is flagged inNav (linked anywhere in the store's live nav chrome; set by
        // the catalog liveness pass). Always keep manual + already-tracked rows.
        const ownerCols = owner?.collections || [];
        const compCols = comp.collections || [];
        const inMenu = (r) => {
            const oc = ownerCols.find((x) => norm(x.url) === norm(r.ownerUrl));
            const cc = compCols.find((x) => norm(x.url) === norm(r.compUrl));
            return !!(oc?.inNav || cc?.inNav);
        };
        // Sort/segment key off the row's FIXED primary side (owner for owner/matched
        // rows, competitor for "only on competitor" rows) — so mapping the OTHER side
        // yourself never changes the key and the row keeps its position.
        const primaryUrl = (r) => (r.kind === "compOnly" ? r.compUrl : r.ownerUrl);
        const primaryCols = (r) => (r.kind === "compOnly" ? compCols : ownerCols);
        const primaryCol = (r) => primaryCols(r).find((x) => norm(x.url) === norm(primaryUrl(r))) || {};
        // Tier order — cluster each top-level category with its sub-categories
        // beneath it (L1 before its L2 children), alphabetical by top category.
        const tierKey = (r) => {
            const src = primaryCol(r);
            const name = String(src.name || src.handle || labelForUrl(primaryCols(r), primaryUrl(r)) || "").toLowerCase();
            const depth = src.depth || 1;
            const parent = String(src.parentName || "").toLowerCase();
            return { top: depth === 2 && parent ? parent : name, depth, name };
        };
        const rows = (rowsByComp[cid] || [])
            .filter((r) => r.kind === kind)
            .filter((r) => showAllCats || r.kind === "manual" || r.tracked || inMenu(r))
            .sort((a, b) => {
                if (kind === "manual") return 0; // keep user's add order
                // Focus categories lead (in priority order) — so the pairs the user
                // cares about are picked first (matters most on tight page budgets).
                if (hasFocus) {
                    const fa = focusRankOfCol(primaryCol(a));
                    const fb = focusRankOfCol(primaryCol(b));
                    if (fa !== fb) return fa - fb;
                }
                const A = tierKey(a), B = tierKey(b);
                return A.top.localeCompare(B.top) || (A.depth - B.depth) || A.name.localeCompare(B.name);
            });
        if (!rows.length) return null;
        const matched = kind === "matched";
        const onlyGroup = kind === "ownerOnly" || kind === "compOnly";
        const tone = matched ? "#4ecdc4" : onlyGroup ? "#eab308" : null;
        const panel = tone
            ? { background: `color-mix(in srgb, ${tone} 8%, var(--card))`, border: `1px solid color-mix(in srgb, ${tone} 40%, transparent)` }
            : { background: "var(--bg)", border: "1px solid var(--border)" };
        const headerColor = matched ? "var(--secondary-dark, #0f6e56)" : onlyGroup ? "#a16207" : "var(--text-light)";

        // Audience-segment sub-grouping — on large flat catalogs, cluster rows under
        // a leading segment word (Men/Women/Boys… or any prefix shared by 3+ rows).
        const leadSeg = (r) => {
            const src = primaryCol(r);
            const name = String(src.name || src.handle || "");
            const slug = slugOf(primaryUrl(r)) || "";
            const words = [...name.split(/[\s\-_/]+/), ...slug.split(/[\s\-_/]+/)].filter(Boolean);
            // A curated segment word anywhere in the name/slug wins (Men, Women, Boys…).
            for (const w of words) { const s = segNorm(w); if (SEG_CURATED.has(s)) return s; }
            // Otherwise fall back to the LEADING word — for recurring generic prefixes
            // only (positional, so common mid-name words don't create noise).
            const first = name.split(/[\s\-_/]+/).filter(Boolean)[0] || slug.split(/[\s\-_/]+/).filter(Boolean)[0] || "";
            return segNorm(first);
        };
        const segCount = {};
        for (const r of rows) { const s = leadSeg(r); if (s) segCount[s] = (segCount[s] || 0) + 1; }
        const qualifies = (s) => (SEG_CURATED.has(s) ? segCount[s] >= 2 : segCount[s] >= 3);
        const segList = Object.keys(segCount).filter(qualifies);
        const covered = segList.reduce((a, s) => a + segCount[s], 0);
        const useSegments = kind !== "manual" && rows.length >= 6 && segList.length >= 1 && covered >= 4;

        let body;
        if (useSegments) {
            const segRows = {}; const ungrouped = [];
            for (const r of rows) {
                const s = leadSeg(r);
                if (s && segList.includes(s)) (segRows[s] = segRows[s] || []).push(r);
                else ungrouped.push(r);
            }
            const orderedSegs = [
                ...SEG_ORDER.filter((s) => segList.includes(s)),
                ...segList.filter((s) => !SEG_CURATED.has(s)).sort((a, b) => segCount[b] - segCount[a] || a.localeCompare(b)),
            ];
            // Accordion — only ONE segment open per group at a time. Default open
            // the first section that's in use (has a tracked row), else all closed.
            const groupKey = `${cid}:${kind}`;
            const defaultOpen = orderedSegs.find((s) => segRows[s].some((r) => r.tracked)) || null;
            const openS = groupKey in openSeg ? openSeg[groupKey] : defaultOpen;
            body = (
                <div className="space-y-2.5">
                    {ungrouped.length > 0 && <div className="space-y-1.5">{ungrouped.map((r) => renderRow(cid, comp, r))}</div>}
                    {orderedSegs.map((s) => {
                        const open = openS === s;
                        const hasTracked = segRows[s].some((r) => r.tracked);
                        return (
                            <div key={s}>
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        const el = e.currentTarget;
                                        const willOpen = openS !== s;
                                        setOpenSeg((p) => ({ ...p, [groupKey]: (groupKey in p ? p[groupKey] : defaultOpen) === s ? null : s }));
                                        // After the collapse/expand settles, bring the opened header to the top.
                                        if (willOpen) requestAnimationFrame(() => requestAnimationFrame(() => el.scrollIntoView({ block: "start", behavior: "smooth" })));
                                    }}
                                    className="flex w-full items-center gap-2 py-0.5"
                                    style={{ scrollMarginTop: 8 }}
                                >
                                    {open
                                        ? <Minus className="h-3.5 w-3.5 shrink-0" style={{ color: headerColor }} />
                                        : <Plus className="h-3.5 w-3.5 shrink-0" style={{ color: headerColor }} />}
                                    <span className="text-[11px] font-bold uppercase tracking-wide" style={{ color: headerColor }}>{segDisplay(s)}</span>
                                    <span className="text-[10px]" style={{ color: "var(--text-light)" }}>· {segRows[s].length}{hasTracked ? " · in use" : ""}</span>
                                    <div className="h-px flex-1" style={{ background: "var(--border)" }} />
                                </button>
                                {open && <div className="mt-1.5 space-y-1.5">{segRows[s].map((r) => renderRow(cid, comp, r, s))}</div>}
                            </div>
                        );
                    })}
                </div>
            );
        } else {
            body = <div className="space-y-1.5">{rows.map((r) => renderRow(cid, comp, r))}</div>;
        }
        return (
            <div className="rounded-2xl p-3" style={panel}>
                <p className="pb-2.5 text-center text-[13px] font-bold uppercase tracking-wider" style={{ color: headerColor }}>{title} · {rows.length}</p>
                {body}
            </div>
        );
    };

    return (
        <div style={overlay}>
            {/* Log out — on the backdrop, outside the modal card. Progress is auto-saved. */}
            <button
                type="button"
                onClick={handleLogout}
                title="Log out — your progress is saved"
                style={{ position: "absolute", top: 16, right: 16, zIndex: 61, border: "1px solid rgba(255,255,255,0.28)", background: "rgba(255,255,255,0.12)" }}
                className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-white/20"
            >
                <LogOut className="h-3.5 w-3.5" /> Log out
            </button>
            <div style={modalBox}>
                {/* Header */}
                <div className="border-b p-5" style={{ borderColor: "var(--border)" }}>
                    <div className="flex items-start justify-between gap-4">
                        <h2 className="text-xl font-extrabold" style={{ color: "var(--primary)" }}>Choose what to track</h2>
                        <div className="hidden shrink-0 items-center gap-2 sm:flex">
                            <span className="text-xs font-semibold" style={{ color: "var(--text-light)" }}>Pages for {activeComp?.name || "this competitor"}</span>
                            <Counter n={activeCount} limit={pageLimit} />
                        </div>
                    </div>
                    <div className="mt-3 flex items-start gap-2.5 rounded-xl px-3.5 py-2.5 text-sm" style={{ background: "color-mix(in srgb, var(--secondary) 10%, var(--card))", border: "1px solid color-mix(in srgb, var(--secondary) 35%, transparent)", color: "var(--text)" }}>
                        <Sparkles className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--secondary)" }} />
                        <p className="leading-relaxed">
                            We paired the pages that <strong style={{ color: "var(--secondary-dark, #0f6e56)" }}>match on both sides</strong>. Review them, add matches for the rest, or add any page <span style={{ color: "var(--text-light)" }}>(a product, a landing page…)</span> by URL.
                        </p>
                    </div>
                </div>

                {/* Body */}
                <div className="min-h-0 flex-1 overflow-y-auto p-5 space-y-6">
                    {loading ? (
                        <div className="flex items-center justify-center gap-2 py-16" style={{ color: "var(--text-light)" }}>
                            <Loader2 className="h-5 w-5 animate-spin" /> Loading what we found…
                        </div>
                    ) : (
                        <>
                            {/* Selected pages recap */}
                            {(() => {
                                const selected = [];
                                if (activeComp) {
                                    for (const r of rowsByComp[activeComp.competitorId] || []) {
                                        if (r.tracked && r.ownerUrl && r.compUrl) selected.push({ c: activeComp, r });
                                    }
                                }
                                return (
                                    <div className="rounded-xl border p-3" style={{ borderColor: "var(--border)", background: "var(--bg)" }}>
                                        <div className="mb-2 flex items-center justify-between gap-2">
                                            <p className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--text-light)" }}>Selected · {selected.length}</p>
                                            {selected.length > 0 && (
                                                <button
                                                    type="button"
                                                    onClick={async () => {
                                                        const res = await Swal.fire({
                                                            icon: "warning",
                                                            title: "Remove all selected pages?",
                                                            text: `This will untrack all ${selected.length} selected ${selected.length === 1 ? "page" : "pages"} for ${activeComp?.name || "this competitor"}.`,
                                                            showCancelButton: true,
                                                            confirmButtonText: "Remove all",
                                                            cancelButtonText: "Keep them",
                                                            confirmButtonColor: "var(--danger, #dc2626)",
                                                        });
                                                        if (res.isConfirmed) clearComp(activeComp.competitorId);
                                                    }}
                                                    className="inline-flex items-center gap-1 text-[11px] font-semibold"
                                                    style={{ color: "var(--danger, #dc2626)" }}
                                                    title="Untrack all selected pages for this competitor"
                                                >
                                                    <X className="h-3.5 w-3.5" /> Remove all
                                                </button>
                                            )}
                                        </div>
                                        <div className="flex flex-wrap gap-1.5">
                                            <span className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold" style={{ borderColor: "color-mix(in srgb, var(--secondary) 40%, transparent)", background: "color-mix(in srgb, var(--secondary) 10%, var(--card))", color: "var(--text)" }}>
                                                <Home className="h-3 w-3" style={{ color: "var(--secondary)" }} /> Homepage
                                            </span>
                                            {selected.length === 0 ? (
                                                <span className="inline-flex items-center text-xs" style={{ color: "var(--text-light)" }}>Tick a mapped pair below to start selecting.</span>
                                            ) : selected.map(({ c, r }) => (
                                                <span key={r.key} className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold" style={{ borderColor: "var(--accent)", background: "color-mix(in srgb, var(--accent) 8%, var(--card))", color: "var(--text)" }}>
                                                    <span className="max-w-[190px] truncate">{labelForUrl(owner?.collections, r.ownerUrl)} ↔ {labelForUrl(c.collections, r.compUrl)}</span>
                                                    <button type="button" onClick={() => patchRow(c.competitorId, r.key, { tracked: false })} title="Remove"><X className="h-3.5 w-3.5" style={{ color: "var(--text-light)" }} /></button>
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                );
                            })()}

                            {/* Wizard progress — one competitor at a time */}
                            {total > 1 && (
                                <div className="flex items-center justify-center gap-2">
                                    <span className="text-xs font-semibold" style={{ color: "var(--text-light)" }}>Competitor {idx + 1} of {total}</span>
                                    <div className="flex items-center gap-1.5">
                                        {competitors.map((c, i) => (
                                            <button
                                                key={c.competitorId}
                                                type="button"
                                                onClick={() => setStep(i)}
                                                title={c.name}
                                                className="h-2 rounded-full transition-all"
                                                style={{ width: i === idx ? 20 : 8, background: i === idx ? "var(--accent)" : "var(--border)" }}
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {(activeComp ? [activeComp] : []).map((comp) => {
                              const fit = fitOf(comp.competitorId);
                              // Exact store-wide total from recon (sitemap / WP header / live count).
                              // We deliberately DON'T fall back to summing per-collection counts —
                              // that double-counts multi-collection products and inflates the total.
                              const ownerProducts = Number(owner?.productTotal) || 0;
                              const compProducts = Number(comp.productTotal) || 0;
                              // Category counts follow the toggle: in-menu shows only nav-linked
                              // categories (matching the rows shown), "all" shows everything found.
                              const ownerCols = owner?.collections || [];
                              const compCols = comp.collections || [];
                              const ownerCats = showAllCats ? ownerCols.length : ownerCols.filter((c) => c.inNav).length;
                              const compCats = showAllCats ? compCols.length : compCols.filter((c) => c.inNav).length;
                              return (
                                <section key={comp.competitorId} className="overflow-hidden rounded-2xl border" style={{ borderColor: "var(--border)" }}>
                                    {/* Header band — dark blue, distinct from the white page rows */}
                                    <div className="p-5" style={{ background: "var(--primary)" }}>
                                        <div className="flex flex-wrap items-center gap-2.5">
                                            <span className="inline-flex items-center gap-2 text-lg" style={{ color: "#fff", fontWeight: 800 }}>
                                                <SiteIcon domain={owner?.domain} Fallback={Store} size={26} /> {ownerName}
                                                <span style={{ color: "rgba(255,255,255,0.55)", fontWeight: 400 }}>vs</span>
                                                <SiteIcon domain={comp.domain} Fallback={Target} size={26} /> {comp.name}
                                            </span>
                                            <span className="rounded-full px-2.5 py-1 text-xs font-bold" style={{ background: fit.tone, color: "#fff" }}>{fit.label}</span>
                                            <span className="text-sm" style={{ color: "rgba(255,255,255,0.8)" }}>{fit.focus ? `covers ${fit.matched} of your ${fit.ownerCats} focus categories` : `matches ${fit.matched} of ${ownerName}'s ${fit.ownerCats} categories`}</span>
                                            <button type="button" onClick={() => openReplace(comp)} className="ml-auto inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-semibold" style={{ border: "1px solid rgba(255,255,255,0.3)", color: "#fff", background: "rgba(255,255,255,0.1)" }} title="Swap this competitor for a better-fit site">
                                                <RefreshCw className="h-4 w-4" /> Replace
                                            </button>
                                        </div>
                                        <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-[13px]" style={{ color: "rgba(255,255,255,0.75)" }}>
                                            <span>{ownerName}: {ownerCats} categories{ownerProducts ? ` · ${ownerProducts.toLocaleString()} products` : ""}</span>
                                            <span>{comp.name}: {compCats} categories{compProducts ? ` · ${compProducts.toLocaleString()} products` : ""}</span>
                                        </div>
                                        {/* Row source toggle — live-site nav vs everything we found */}
                                        <div className="mt-2.5 flex items-center gap-2">
                                            <span className="text-xs font-medium" style={{ color: "rgba(255,255,255,0.6)" }}>Show</span>
                                            <div className="inline-flex rounded-lg p-0.5" style={{ border: "1px solid rgba(255,255,255,0.2)", background: "rgba(255,255,255,0.08)" }}>
                                                {[
                                                    { v: false, label: "Live on site", hint: "Only categories actually surfaced in the store's live navigation." },
                                                    { v: true, label: "All categories", hint: "Every category we found, including hidden/discontinued ones." },
                                                ].map((opt) => {
                                                    const active = showAllCats === opt.v;
                                                    return (
                                                        <button
                                                            key={String(opt.v)}
                                                            type="button"
                                                            title={opt.hint}
                                                            onClick={() => setShowAllCats(opt.v)}
                                                            className="rounded-md px-2.5 py-1 text-xs font-semibold transition-colors"
                                                            style={{ background: active ? "rgba(255,255,255,0.92)" : "transparent", color: active ? "var(--primary)" : "rgba(255,255,255,0.65)" }}
                                                        >
                                                            {opt.label}
                                                        </button>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    </div>

                                    <div className="p-4">
                                    {/* Column headers */}
                                    <div className="mb-3 mt-5 grid items-center gap-2 px-0.5 text-[13px] font-bold uppercase tracking-wider" style={{ gridTemplateColumns: GRID, color: "var(--text-light)" }}>
                                        <span />
                                        <span className="inline-flex items-center justify-center gap-1.5"><SiteIcon domain={owner?.domain} Fallback={Store} size={18} /> {ownerName} pages</span>
                                        <span />
                                        <span className="inline-flex items-center justify-center gap-1.5"><SiteIcon domain={comp.domain} Fallback={Target} size={18} /> {comp.name} pages</span>
                                        <span />
                                    </div>

                                    <div className="space-y-4">
                                        {renderGroup(comp.competitorId, comp, "matched", "Matched — on both sites")}
                                        {renderGroup(comp.competitorId, comp, "ownerOnly", `Only on ${ownerName}`)}
                                        {renderGroup(comp.competitorId, comp, "compOnly", `Only on ${comp.name}`)}
                                        {renderGroup(comp.competitorId, comp, "manual", "Added by URL")}
                                    </div>

                                    <button
                                        type="button"
                                        onClick={() => addManualRow(comp.competitorId)}
                                        className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed px-3 py-2.5 text-sm font-semibold transition-colors"
                                        style={{ borderColor: "var(--accent)", color: "var(--accent)", background: "color-mix(in srgb, var(--accent) 7%, var(--card))" }}
                                    >
                                        <Plus className="h-4 w-4" /> Add a page by URL
                                    </button>
                                    </div>
                                </section>
                              );
                            })}
                        </>
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between gap-4 border-t p-5" style={{ borderColor: "var(--border)" }}>
                    <p className="text-xs" style={{ color: "var(--text-light)" }}>
                        Tracking <strong style={{ color: "var(--text)" }}>{activeCount}</strong> of {pageLimit} {pageLimit === 1 ? "page" : "pages"} <span style={{ color: "var(--text-light)" }}>+ homepage</span> for {activeComp?.name || "this competitor"}{activeCount >= pageLimit ? " · limit reached" : ""}.{draftSavedAt ? <span style={{ color: "var(--secondary-dark, #0f6e56)" }}> Progress saved.</span> : " You can change these anytime later."}
                    </p>
                    <div className="flex items-center gap-2">
                        {idx > 0 && (
                            <button
                                type="button"
                                onClick={() => setStep(idx - 1)}
                                disabled={submitting}
                                className="inline-flex items-center gap-1.5 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-60"
                                style={{ borderColor: "var(--border)", color: "var(--text)", background: "var(--card)" }}
                            >
                                <ArrowLeft className="h-4 w-4" /> Back
                            </button>
                        )}
                        {idx < total - 1 ? (
                            <button
                                type="button"
                                onClick={async () => {
                                    if (activeCount < pageLimit) {
                                        const res = await Swal.fire({
                                            icon: "question",
                                            title: "Move on without finishing?",
                                            text: `You've selected ${activeCount} of ${pageLimit} pages for ${activeComp?.name || "this competitor"}. You can come back anytime.`,
                                            showCancelButton: true,
                                            confirmButtonText: "Next competitor",
                                            cancelButtonText: "Stay here",
                                        });
                                        if (!res.isConfirmed) return;
                                    }
                                    setStep(idx + 1);
                                }}
                                disabled={loading}
                                className="inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-bold text-white transition-transform hover:-translate-y-0.5 disabled:translate-y-0 disabled:opacity-60"
                                style={{ background: "var(--primary)" }}
                            >
                                Next competitor <ArrowRight className="h-4 w-4" />
                            </button>
                        ) : (
                            <button
                                type="button"
                                onClick={handleSubmit}
                                disabled={submitting || loading || activeCount === 0}
                                className="inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-bold text-white transition-transform hover:-translate-y-0.5 disabled:translate-y-0 disabled:opacity-60"
                                style={{ background: "var(--accent)", boxShadow: "0 8px 24px rgba(255,107,107,0.3)" }}
                            >
                                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                                {submitting ? "Starting…" : "Start analysis"}
                            </button>
                        )}
                    </div>
                </div>

                {/* Replace-competitor panel — suggested competitors + manual URL */}
                {replacing && (
                    <div style={{ position: "absolute", inset: 0, zIndex: 70, background: "rgba(15,15,30,0.5)", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
                        <div style={{ width: "100%", maxWidth: 540, maxHeight: "84%", display: "flex", flexDirection: "column", background: "var(--card)", borderRadius: 16, boxShadow: "var(--shadow-lg)", overflow: "hidden" }}>
                            <div className="flex items-center justify-between gap-2 border-b p-4" style={{ borderColor: "var(--border)" }}>
                                <div>
                                    <h3 className="text-base font-extrabold" style={{ color: "var(--primary)" }}>Replace {replacing.name}</h3>
                                    <p className="text-xs" style={{ color: "var(--text-light)" }}>Pick a suggested competitor, or add one by URL. We'll re-capture it, then bring you back here.</p>
                                </div>
                                <button type="button" onClick={() => setReplacing(null)} aria-label="Close"><X className="h-5 w-5" style={{ color: "var(--text-light)" }} /></button>
                            </div>

                            <div className="min-h-0 flex-1 overflow-y-auto p-4 space-y-2">
                                <div className="flex items-center justify-between gap-2">
                                    <p className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--text-light)" }}>
                                        <Sparkles className="h-3.5 w-3.5" style={{ color: "var(--secondary)" }} /> {queryMode ? "For your categories" : `Suggested for ${ownerName}`}
                                    </p>
                                    {queryMode && (
                                        <button type="button" onClick={backToStored} className="text-[11px] font-bold underline" style={{ color: "var(--secondary-dark)" }}>Back to suggestions</button>
                                    )}
                                </div>
                                {suggestLoading ? (
                                    <div className="flex items-center gap-2 py-6 text-sm" style={{ color: "var(--text-light)" }}><Loader2 className="h-4 w-4 animate-spin" /> {queryMode ? "Searching your categories…" : "Loading suggestions…"}</div>
                                ) : suggestions.length === 0 ? (
                                    <p className="py-2 text-sm" style={{ color: "var(--text-light)" }}>{queryMode ? "No competitors matched those categories — try different terms, or add one by URL below." : "No stored suggestions — search by category or add one by URL below."}</p>
                                ) : (
                                    suggestions.map((s) => (
                                        <div key={s.domain || s.url} className="flex items-center gap-3 rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
                                            <div className="min-w-0 flex-1">
                                                <p className="truncate text-sm font-semibold" style={{ color: "var(--text)" }}>
                                                    {s.name || s.domain}
                                                    {typeof s.similarityScore === "number" && s.similarityScore > 0 && (
                                                        <span className="ml-2 rounded-full px-1.5 py-0.5 text-[10px] font-bold align-middle" style={{ background: "var(--glow-teal, rgba(78,205,196,0.14))", color: "var(--secondary-dark, var(--secondary))" }} title="How closely this store matches yours">
                                                            {Math.round(s.similarityScore * 100)}% match
                                                        </span>
                                                    )}
                                                </p>
                                                {/* Prefer the human "why it's a real competitor" reason; fall back to domain + matched categories. */}
                                                <p className="truncate text-xs" style={{ color: "var(--text-light)" }}>
                                                    {s.whyMatch
                                                        ? `${s.domain} · ${s.whyMatch}`
                                                        : `${s.domain}${Array.isArray(s.matchedCategories) && s.matchedCategories.length ? ` · ${s.matchedCategories.slice(0, 3).join(", ")}` : ""}`}
                                                </p>
                                            </div>
                                            <a href={s.url} target="_blank" rel="noreferrer" className="shrink-0" title="Open"><ExternalLink className="h-4 w-4" style={{ color: "var(--text-light)" }} /></a>
                                            <button type="button" onClick={() => doReplace(s.url)} disabled={replaceBusy} className="shrink-0 rounded-lg px-3 py-1.5 text-xs font-bold text-white disabled:opacity-60" style={{ background: "var(--primary)" }}>Use</button>
                                        </div>
                                    ))
                                )}
                            </div>

                            <div className="border-t p-4 space-y-3" style={{ borderColor: "var(--border)" }}>
                                {/* Target specific categories (search like onboarding) */}
                                {!showQueryInput ? (
                                    <button type="button" onClick={() => setShowQueryInput(true)} className="inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-bold text-white" style={{ background: "var(--secondary-dark)" }}>
                                        <Sparkles className="h-3.5 w-3.5" /> Search competitors by category
                                    </button>
                                ) : (
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <input autoFocus value={catInput} onChange={(e) => setCatInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") runReplaceQuery(); }} placeholder="Categories to target, comma-separated (e.g. lipstick, mascara)" className="flex-1 rounded-xl border px-3 py-2 text-sm" style={inputStyle} />
                                            <button type="button" onClick={runReplaceQuery} disabled={suggestLoading || !catInput.trim()} className="shrink-0 rounded-xl px-4 py-2 text-sm font-bold text-white disabled:opacity-60" style={{ background: "var(--secondary-dark)" }}>Search</button>
                                        </div>
                                        <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-light)" }}>Searches each category in your market and replaces the list above.</p>
                                    </div>
                                )}
                                <div className="flex items-center gap-2">
                                    <input value={manualUrl} onChange={(e) => setManualUrl(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") doReplace(withProto(manualUrl)); }} placeholder="Or add a competitor by URL (competitor.com)" className="flex-1 rounded-xl border px-3 py-2 text-sm" style={inputStyle} />
                                    <button type="button" onClick={() => doReplace(withProto(manualUrl))} disabled={replaceBusy || !manualUrl.includes(".")} className="inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-bold text-white disabled:opacity-60" style={{ background: "var(--accent)" }}>
                                        {replaceBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} {replaceBusy ? "Checking site…" : "Replace"}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
