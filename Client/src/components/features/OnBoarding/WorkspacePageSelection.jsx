import { useEffect, useMemo, useRef, useState } from "react";
import {
  Home,
  AlertTriangle,
  Lock,
  CheckCircle2,
  X,
  Sparkles,
  ListTree,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

import TreeNode from "../../ui/TreeNode";
import ManualPageUrlPicker from "../../shared/ManualPageUrlPicker";
import PageDiscoveryLoader from "../Loadings/PageDiscoveryLoader";

import { createTreeNode } from "../../../api/utils.api";
import useAuthStore from "../../../store/auth.store";
import { computeDefaultPages, assessCatalog, walkTreeStats, capProductPages, collectTitles, countProductPages } from "../../../utils/treeStats";

// How many products we keep browsable in the owner's own tree. Their own store is
// usually the smaller one and they care about it, so we're generous — but still
// capped so a huge catalog can't hang the picker. Anything past this is reachable
// by search or by pasting the URL, and we say so, so the list never reads as a
// failed/truncated fetch.
const OWNER_PRODUCT_CAP = 300;

/* ────────────────────────────────────────────────────────────────
   IntelShift — Onboarding: choose the pages on YOUR site to track.
   Analysis runs on these pages only. Homepage is always included.
──────────────────────────────────────────────────────────────── */

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

const prettyPath = (raw) => {
  try {
    const u = new URL(raw);
    return u.pathname === "/" ? "/" : u.pathname.replace(/\/$/, "");
  } catch {
    return raw;
  }
};

/* ── Crawl cache ───────────────────────────────────────────────
   Keyed by origin and scoped to this page load, so navigating back
   to this step re-uses the crawl instead of hitting the API again.
   Promises are cached (not just results) so two rapid mounts share
   one request. This lives in the browser tab, so nothing is ever
   shared between different users.
──────────────────────────────────────────────────────────────── */

const treeCache = new Map();

const fetchTree = (origin) => {
  if (treeCache.has(origin)) return treeCache.get(origin);

  const pending = createTreeNode(origin).catch((error) => {
    treeCache.delete(origin); // let a later attempt retry
    throw error;
  });

  treeCache.set(origin, pending);
  return pending;
};

function WorkspacePageSelection({
  onPageSelection,
  // Reports whether the site yielded readable pages, so the stepper can hard-block
  // "Next" on a blocked / unreadable site (no point tracking one we can't read).
  onReadableChange,
  // Emits a { [url]: name } map from the crawl tree so the competitor mapping
  // step can match on the owner's real page names, not just URL slugs.
  onOwnerTitles,
  url,
  workspaceName,
  // Supplied by ProcessStepper — every step stays mounted, so we defer
  // the crawl until this one is actually on screen.
  isActive = true,
}) {
  const [treeData, setTreeData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [productTotal, setProductTotal] = useState(0); // true # products found (pre-cap)
  const [fetchError, setFetchError] = useState(false); // crawl threw (unreachable / server error)
  const [phase, setPhase] = useState("discovering"); // discovering → structuring
  const [treeSelectedPages, setTreeSelectedPages] = useState([]);
  const [manualUrls, setManualUrls] = useState([]);
  // Nonce-carrying request that tells TreeNode to uncheck a page (from the
  // "Will be analysed" list). Manual URLs are removed directly instead.
  const [deselectRequest, setDeselectRequest] = useState(null);

  const urlOf = (u) => (typeof u === "string" ? u : u?.url || "");
  const handleDeselect = (href) => {
    if (!href) return;
    const isManual = manualUrls.some((u) => urlOf(u) === href);
    if (isManual) {
      setManualUrls((prev) => prev.filter((u) => urlOf(u) !== href));
    } else {
      setDeselectRequest({ url: href, nonce: Date.now() });
    }
  };

  const user = useAuthStore((state) => state.user);
  const limits = user?.subscription?.planId?.limits?.pagesPerCompetitor || 2;
  const planLabel = user?.subscription?.planId?.displayName || "your plan";

  // Keep the callback in a ref so parent re-renders do not retrigger the effect.
  const onPageSelectionRef = useRef(onPageSelection);
  onPageSelectionRef.current = onPageSelection;

  const onReadableRef = useRef(onReadableChange);
  onReadableRef.current = onReadableChange;

  // The origin we've already loaded the tree for. Re-entering this step (e.g. the
  // user navigates back from the competitor step) must NOT re-fetch and re-apply
  // the auto-selection — that would wipe the pages they picked. We only re-crawl
  // when the site actually changes.
  const loadedOriginRef = useRef(null);

  const onOwnerTitlesRef = useRef(onOwnerTitles);
  onOwnerTitlesRef.current = onOwnerTitles;

  // Once the crawl settles, tell the stepper whether the site is readable at all.
  useEffect(() => {
    if (loading) return;
    const pageCount = treeData ? walkTreeStats(treeData).totalPages : 0;
    onReadableRef.current?.(!(fetchError || pageCount === 0));
  }, [loading, treeData, fetchError]);

  // Publish the owner's url→name map once discovered, so the mapping step can
  // match on real page names in addition to slugs.
  useEffect(() => {
    if (!treeData) return;
    onOwnerTitlesRef.current?.(collectTitles(treeData));
  }, [treeData]);

  const origin = useMemo(() => safeOrigin(url), [url]);

  useEffect(() => {
    if (!isActive || !url) return undefined;

    const originKey = safeOrigin(url);
    // Already crawled this site — the user came back to this step. Keep their tree
    // and their selection intact instead of re-running discovery + auto-select.
    if (loadedOriginRef.current === originKey) return undefined;

    let cancelled = false;

    let structureTimer;
    const fetchTreeData = async () => {
      try {
        setLoading(true);
        setFetchError(false);
        setPhase("discovering");
        const data = await fetchTree(originKey);
        if (cancelled) return;
        loadedOriginRef.current = originKey; // mark loaded so re-entry won't reset
        // Record the TRUE product count before capping, so we can honestly label a
        // shown sample as a subset (never a "failed fetch").
        setProductTotal(countProductPages(data));
        // Keep a generous but capped sample of product pages — enough to browse,
        // but not the thousands that hang the picker. Others via search/paste.
        setTreeData(capProductPages(data, OWNER_PRODUCT_CAP));
        // Brief "structuring" beat so the last thing the user sees is us
        // organizing the pages, then reveal the tree.
        setPhase("structuring");
        structureTimer = setTimeout(() => {
          if (!cancelled) setLoading(false);
        }, 900);
      } catch (error) {
        console.error("Error fetching tree data:", error);
        if (!cancelled) {
          setFetchError(true);
          setLoading(false);
        }
      }
    };

    fetchTreeData();

    return () => {
      cancelled = true;
      if (structureTimer) clearTimeout(structureTimer);
    };
  }, [isActive, url]);

  const selected = useMemo(
    () => [...treeSelectedPages, ...manualUrls],
    [treeSelectedPages, manualUrls]
  );

  useEffect(() => {
    onPageSelectionRef.current?.(selected);
  }, [selected]);

  // Plan-aware catalog assessment: does this store's category spine fit the
  // plan's page budget? Returns one of three tiers — ok / upgrade / mega — so we
  // show the RIGHT notice (or none) instead of a one-size "unsupported" message.
  const assessment = useMemo(() => assessCatalog(treeData, limits), [treeData, limits]);

  // A sensible starting selection so the user isn't staring at a blank tree:
  // their top collections in nav order (or pricing/features for non-catalog
  // sites), capped at the plan's page limit. TreeNode applies these once and
  // never overrides a choice the user has already made.
  const defaultUrls = useMemo(
    () => computeDefaultPages(treeData, limits),
    [treeData, limits]
  );

  // The tree is the "browse & add" drawer. Once discovery finishes, collapse it
  // when we already have suggestions to review (import-filter feel) and open it
  // when we have nothing to suggest (e.g. a SaaS site) so the user isn't stuck.
  const [browseOpen, setBrowseOpen] = useState(false);
  const browseInitRef = useRef(false);
  useEffect(() => {
    if (browseInitRef.current || !treeData) return;
    browseInitRef.current = true;
    setBrowseOpen(defaultUrls.length === 0);
  }, [treeData, defaultUrls]);

  // Inline rather than a Swal popup: this step is mounted from the start,
  // so an alert here would fire before the user has even reached it.
  if (!url) {
    return (
      <div style={{ color: "var(--text-light)", fontSize: 14 }}>
        Add your website URL in the previous step to choose pages.
      </div>
    );
  }

  if (loading) {
    return <PageDiscoveryLoader variant={phase === "structuring" ? "structuring" : "workspace"} />;
  }

  // Blocked / unreadable site: the crawl either failed outright or came back with
  // zero pages. Our crawler already handles many bot-protected (Cloudflare) sites,
  // so reaching here means we genuinely couldn't read it — tell the user plainly
  // and point them at a fix rather than dropping them on an empty picker.
  const pageCount = treeData ? walkTreeStats(treeData).totalPages : 0;
  const crawlFailed = fetchError || pageCount === 0;
  if (crawlFailed) {
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
          We couldn&apos;t read this site
        </h2>
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            padding: "1.05rem 1.125rem",
            marginTop: "0.75rem",
            background: "color-mix(in srgb, var(--danger, #dc2626) 7%, var(--card))",
            border: "1px solid color-mix(in srgb, var(--danger, #dc2626) 32%, transparent)",
            borderRadius: "var(--radius)",
          }}
        >
          <AlertTriangle
            size={18}
            style={{ color: "var(--danger, #dc2626)", marginTop: 1, flexShrink: 0 }}
          />
          <div style={{ fontSize: 13, lineHeight: 1.65, color: "var(--text)" }}>
            <p style={{ margin: 0, fontWeight: 700 }}>
              We couldn&apos;t read the pages on{" "}
              {workspaceName || origin.replace(/^https?:\/\//, "")}.
            </p>
            <p style={{ margin: "6px 0 0" }}>
              The site may block automated access, or run on a platform we can&apos;t
              fully read yet. Go <strong>Back</strong> to try a different address.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const remaining = Math.max(limits - selected.length, 0);
  const atLimit = selected.length >= limits;

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
        Choose the pages to track
      </h2>

      <p
        style={{
          fontSize: 14.5,
          color: "var(--text-light)",
          marginBottom: "1.25rem",
          lineHeight: 1.6,
        }}
      >
        These are the pages on{" "}
        <strong style={{ color: "var(--text)" }}>
          {workspaceName || origin.replace(/^https?:\/\//, "")}
        </strong>{" "}
        that IntelShift AI will analyse.
      </p>

      {/* ── Tier 2: upgrade nudge (bigger than THIS plan, but a real brand) ── */}
      {assessment.tier === "upgrade" && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            padding: "1rem 1.125rem",
            background: "var(--glow-teal)",
            border: "1px solid color-mix(in srgb, var(--secondary) 32%, transparent)",
            borderRadius: "var(--radius)",
            marginBottom: "1.25rem",
          }}
        >
          <Sparkles
            size={17}
            style={{ color: "var(--secondary-dark)", marginTop: 1, flexShrink: 0 }}
          />
          <div style={{ fontSize: 12.5, lineHeight: 1.65, color: "var(--text)" }}>
            <p style={{ margin: 0, fontWeight: 700 }}>
              This store is bigger than {planLabel}&apos;s {limits} pages can fully cover.
            </p>
            <p style={{ margin: "4px 0 0" }}>
              We&apos;ll focus your pages on the most important categories — plenty to
              start.{" "}
              {assessment.recommendedPlan && (
                <>
                  <strong>
                    {assessment.recommendedPlan.name} ({assessment.recommendedPlan.pages} pages)
                  </strong>{" "}
                  covers more of it whenever you&apos;re ready.
                </>
              )}
            </p>
          </div>
        </div>
      )}

      {/* ── Tier 3: marketplace / mega-retailer (too large even for Pro) ── */}
      {assessment.tier === "mega" && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            padding: "1rem 1.125rem",
            background: "color-mix(in srgb, var(--danger, #dc2626) 7%, var(--card))",
            border: "1px solid color-mix(in srgb, var(--danger, #dc2626) 32%, transparent)",
            borderRadius: "var(--radius)",
            marginBottom: "1.25rem",
          }}
        >
          <AlertTriangle
            size={17}
            style={{ color: "var(--danger, #dc2626)", marginTop: 1, flexShrink: 0 }}
          />
          <div style={{ fontSize: 12.5, lineHeight: 1.65, color: "var(--text)" }}>
            <p style={{ margin: 0, fontWeight: 700 }}>
              This looks like a marketplace or mega-retailer.
            </p>
            <p style={{ margin: "4px 0 0" }}>
              IntelShift works best for focused brands — comparisons get weaker at this
              scale. You can still track your{" "}
              <strong>most important</strong> pages (flagship collections, key product
              lines).
            </p>
          </div>
        </div>
      )}

      {/* ── PRIMARY: what we'll track (review zone) ───────────── */}
      <div
        style={{
          background: "var(--card)",
          border: `1px solid ${atLimit ? "color-mix(in srgb, var(--accent) 40%, transparent)" : "var(--border)"}`,
          borderRadius: "var(--radius)",
          boxShadow: "var(--shadow-sm)",
          marginBottom: "0.9rem",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            flexWrap: "wrap",
            padding: "0.8rem 1.05rem",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: "var(--text-light)",
            }}
          >
            Tracking
          </span>
          <span
            style={{
              fontSize: 12,
              fontWeight: 700,
              padding: "3px 10px",
              borderRadius: 999,
              background: atLimit ? "var(--glow-coral)" : "var(--bg)",
              color: atLimit ? "var(--accent-dark)" : "var(--text-light)",
              border: atLimit
                ? "1px solid color-mix(in srgb, var(--accent) 32%, transparent)"
                : "1px solid var(--border)",
            }}
          >
            {selected.length} of {limits}
            {!atLimit && remaining > 0 ? ` · ${remaining} left` : ""}
          </span>
        </div>

        <ul style={{ margin: 0, padding: "0.5rem 1.05rem 0.75rem", listStyle: "none" }}>
          <li style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0", fontSize: 13 }}>
            <Home size={14} style={{ color: "var(--secondary-dark)", flexShrink: 0 }} />
            <span style={{ fontWeight: 600, color: "var(--text)" }}>Homepage</span>
            <span
              style={{
                marginLeft: "auto",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontSize: 10.5,
                fontWeight: 700,
                color: "var(--secondary-dark)",
                whiteSpace: "nowrap",
              }}
            >
              <Lock size={10} /> Always
            </span>
          </li>

          {selected.length === 0 ? (
            <li style={{ padding: "6px 0 2px", fontSize: 12.5, color: "var(--text-light)", lineHeight: 1.5 }}>
              Nothing else picked yet — open <strong>Browse &amp; add pages</strong> below to choose what to track.
            </li>
          ) : (
            selected.map((page) => {
              const href = typeof page === "string" ? page : page?.url || "";
              return (
                <li
                  key={href}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "4px 0",
                    fontSize: 13,
                    minWidth: 0,
                  }}
                >
                  <CheckCircle2 size={14} style={{ color: "var(--secondary-dark)", flexShrink: 0 }} />
                  <span
                    title={href}
                    style={{
                      flex: 1,
                      color: "var(--text-light)",
                      fontSize: 12,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {prettyPath(href)}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleDeselect(href)}
                    aria-label={`Remove ${prettyPath(href)}`}
                    title="Remove from analysis"
                    style={{
                      flexShrink: 0,
                      width: 22,
                      height: 22,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      borderRadius: 999,
                      border: "none",
                      background: "transparent",
                      color: "var(--text-light)",
                      cursor: "pointer",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "var(--glow-coral)";
                      e.currentTarget.style.color = "var(--accent-dark)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "transparent";
                      e.currentTarget.style.color = "var(--text-light)";
                    }}
                  >
                    <X size={13} />
                  </button>
                </li>
              );
            })
          )}
        </ul>
      </div>

      {/* ── Slim guidance ─────────────────────────────────────── */}
      <p
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 8,
          margin: "0 0 0.9rem",
          fontSize: 12.5,
          lineHeight: 1.6,
          color: "var(--text-light)",
        }}
      >
        <Sparkles size={14} style={{ color: "var(--accent-dark)", marginTop: 2, flexShrink: 0 }} />
        <span>
          We&apos;ve pre-selected your top pages. Open{" "}
          <strong style={{ color: "var(--text)" }}>Browse</strong> to add or remove — the{" "}
          <span style={{ color: "var(--accent-dark)", fontWeight: 700 }}>Suggested</span> tags mark
          our picks.
        </span>
      </p>

      {/* ── Collapsible: browse & add pages ───────────────────── */}
      <div
        style={{
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          overflow: "hidden",
        }}
      >
        <button
          type="button"
          onClick={() => setBrowseOpen((v) => !v)}
          aria-expanded={browseOpen}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            padding: "0.8rem 1.05rem",
            background: "var(--bg)",
            border: "none",
            cursor: "pointer",
            fontFamily: "var(--font-sans)",
          }}
        >
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 13.5,
              fontWeight: 700,
              color: "var(--text)",
            }}
          >
            <ListTree size={15} style={{ color: "var(--secondary-dark)" }} />
            Browse &amp; add pages
          </span>
          {browseOpen ? (
            <ChevronUp size={17} style={{ color: "var(--text-light)" }} />
          ) : (
            <ChevronDown size={17} style={{ color: "var(--text-light)" }} />
          )}
        </button>

        {browseOpen && (
          <div style={{ padding: "0.85rem 1.05rem 1rem", borderTop: "1px solid var(--border)" }}>
      {productTotal > OWNER_PRODUCT_CAP && (
        <p
          style={{
            margin: "0 0 10px",
            fontSize: 12,
            lineHeight: 1.5,
            color: "var(--text-light)",
            background: "var(--bg)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            padding: "8px 10px",
          }}
        >
          Categories are what we track. We&rsquo;ve listed{" "}
          <strong style={{ color: "var(--text)" }}>{OWNER_PRODUCT_CAP}</strong> of your{" "}
          <strong style={{ color: "var(--text)" }}>{productTotal.toLocaleString()}</strong>{" "}
          products for quick picking — to track a specific one that isn&rsquo;t here,
          search the tree or paste its URL below.
        </p>
      )}

      <TreeNode
        data={treeData}
        selectionLimit={limits}
        homepage={false}
        onSelectionChange={setTreeSelectedPages}
        deselectRequest={deselectRequest}
        defaultSelectedUrls={defaultUrls}
      />

      <ManualPageUrlPicker
        urls={manualUrls}
        onUrlsChange={setManualUrls}
        existingUrls={treeSelectedPages}
        selectedCount={treeSelectedPages.length}
        selectionLimit={limits}
      />

          </div>
        )}
      </div>
    </div>
  );
}

export default WorkspacePageSelection;
