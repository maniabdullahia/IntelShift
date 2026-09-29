import React, { useEffect, useMemo, useState } from 'react'
import useWorkspaceStore from '../../store/workspace.store'
import { useNavigate } from "react-router";
import OnboardingHeader from "../../components/features/OnBoarding/OnboardingHeader";

import { joinWorkspace } from '../../socket/socketManager';

import { markIntroCompleted, rescanWorkspace } from '../../api/workspace.api';
import { logout } from '../../api/user.api';


import {
    FileText,
    Users,
    BarChart2,
    LoaderCircle,
    CheckCircle2,
    AlertTriangle,
    Store,
    Target,
} from 'lucide-react'

/* If nothing changes for this long, the run is stuck rather than slow.
   Without this the screen spins forever on any backend failure. */
const STALL_TIMEOUT_MS = 5 * 60 * 1000

const STEPS = [
    {
        key: 'pages',
        title: 'Analyzing Pages',
        desc: 'Scanning pages to extract content, metadata and signals.',
        Icon: FileText,
    },
    {
        key: 'competitors',
        title: 'Analyzing Competitors',
        desc: 'Crawling competitor stores and comparing signals.',
        Icon: Users,
    },
    {
        key: 'report',
        title: 'Generating Report',
        desc: 'Compiling insights and preparing your first report.',
        Icon: BarChart2,
    },
]

/* ──────────────────────────────────────────────────────────────────
   Capture-first recon progress. Shown while setupStage === "recon":
   we're reading each site's homepage / menu / catalog (breadth only)
   before the user picks what to track. Simple per-site progress — no
   deep analysis is running yet.
─────────────────────────────────────────────────────────────────── */
function ReconProgress({ workspace, onLogout }) {
    const sites = workspace?.competitors || [];
    const statusOf = (s) => String(s || 'Pending').toLowerCase();
    const settled = (s) => statusOf(s) === 'completed' || statusOf(s) === 'failed';

    const total = sites.length;
    const done = sites.filter((c) => settled(c?.reconStatus)).length;
    let percent = total ? Math.round((done / total) * 100) : 0;
    if (percent >= 100 && done < total) percent = 99;
    else if (percent < 6 && total > 0) percent = 6;

    const rowState = (s) => {
        const v = statusOf(s);
        if (v === 'completed') return { label: 'Ready', Icon: CheckCircle2, color: 'var(--success)' };
        if (v === 'failed') return { label: "Couldn't read", Icon: AlertTriangle, color: 'var(--danger, #dc2626)' };
        if (v === 'processing') return { label: 'Analyzing…', Icon: LoaderCircle, color: 'var(--accent)', spin: true };
        return { label: 'Queued', Icon: LoaderCircle, color: 'var(--text-light)' };
    };

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
            <OnboardingHeader onLogout={onLogout} />
            <div className="relative w-full overflow-hidden px-4 py-10 sm:py-12 flex items-start justify-center">
                <div className="pointer-events-none absolute -right-24 -top-16 h-72 w-72 rounded-full bg-[var(--glow-teal)] blur-3xl" />
                <div className="pointer-events-none absolute -left-24 top-40 h-72 w-72 rounded-full bg-[var(--glow-coral)] blur-3xl" />

                <div className="relative w-full max-w-xl">
                    <div className="mb-8 text-center">
                        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-3" style={{ color: 'var(--primary)' }}>
                            Reviewing the{' '}
                            <span className="serif" style={{ color: 'var(--secondary)' }}>Sites</span>
                        </h1>
                        <p className="text-base max-w-md mx-auto leading-relaxed" style={{ color: 'var(--text-light)' }}>
                            We're taking a first look at each site so you can choose what to track.
                        </p>
                    </div>

                    {/* Progress bar */}
                    <div className="mb-6">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
                                {done} of {total} sites
                            </span>
                            <span className="text-sm font-bold" style={{ color: 'var(--secondary-dark)' }}>{percent}%</span>
                        </div>
                        <div className="relative w-full h-2.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                            <div
                                className="relative h-full transition-all duration-700 ease-out rounded-full overflow-hidden"
                                style={{ width: `${percent}%`, background: 'linear-gradient(90deg, var(--secondary), var(--accent))' }}
                            >
                                {done < total && (
                                    <div
                                        className="absolute inset-0"
                                        style={{ background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.45), transparent)', animation: 'is-shimmer 1.4s linear infinite' }}
                                    />
                                )}
                            </div>
                        </div>
                        <style>{`@keyframes is-shimmer { from { transform: translateX(-100%); } to { transform: translateX(100%); } }`}</style>
                    </div>

                    {/* Per-site rows */}
                    <div className="space-y-2.5">
                        {sites.map((site) => {
                            const st = rowState(site?.reconStatus);
                            const isOwner = site?.role === 'Owner';
                            const SiteIcon = isOwner ? Store : Target;
                            return (
                                <div
                                    key={site?.id || site?._id || site?.name}
                                    className="rounded-2xl border-2 p-4 flex items-center gap-4"
                                    style={{ borderColor: 'var(--border)', background: 'var(--card)' }}
                                >
                                    <div className="shrink-0 rounded-xl p-2.5" style={{ background: 'var(--background)' }}>
                                        <SiteIcon className="h-5 w-5" style={{ color: isOwner ? 'var(--secondary)' : 'var(--primary)' }} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-bold truncate" style={{ color: 'var(--text)' }}>{site?.name || 'Site'}</p>
                                        <p className="text-xs" style={{ color: 'var(--text-light)' }}>{isOwner ? 'Your store' : 'Competitor'}</p>
                                    </div>
                                    <div className="shrink-0 inline-flex items-center gap-2">
                                        <st.Icon className={`h-4 w-4${st.spin ? ' animate-spin' : ''}`} style={{ color: st.color }} />
                                        <span className="text-xs font-semibold whitespace-nowrap" style={{ color: st.color }}>{st.label}</span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    <div className="text-center pt-6 mt-6 border-t" style={{ borderColor: 'var(--border)' }}>
                        <p className="text-sm" style={{ color: 'var(--text-light)' }}>
                            {done >= total && total > 0
                                ? '✨ All set — taking you to pick what to track…'
                                : 'Hang tight, this won\'t take long.'}
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

function Intro() {

    const navigate = useNavigate();
    const workspace = useWorkspaceStore((state) => state?.workspace)
    const introCompleted = workspace?.introCompleted;
    const setupStage = workspace?.setupStage;

    // Capture-first recon phase: poll for recon progress + the flip to
    // "selecting", then hand off to the workspace (where selection happens).
    useEffect(() => {
        if (setupStage !== 'recon') return;
        const t = setInterval(() => {
            useWorkspaceStore.getState().syncWorkspace().catch(() => {});
        }, 4000);
        return () => clearInterval(t);
    }, [setupStage]);

    useEffect(() => {
        if (setupStage === 'selecting') {
            navigate('/dashboard', { replace: true });
        }
    }, [setupStage, navigate]);

    // Redirect when intro is already completed.
    // This must live in an effect, not the render body -- calling navigate()
    // during render triggers a setState on RouterProvider while Intro is
    // still rendering, which React disallows ("Cannot update a component
    // while rendering a different component").
    useEffect(() => {
        if (introCompleted) {
            navigate("/dashboard", { replace: true });
        }
    }, [introCompleted, navigate]);

    useEffect(() => {
        if (!workspace?.id) return;

        joinWorkspace(workspace.id);
        console.log('Joined workspace room:', workspace.id);

        // Don't leave on unmount
    }, [workspace?.id]);


    /* Guarded index. `workspace?.analysis[0]` only guards `workspace` -- it
       still throws when a workspace exists without an analysis array, which
       is exactly the state this screen renders in. */
    const workspaceAnalysis = workspace?.analysis?.[0];

    /* ALL competitors, not just the first. The previous .find() returned
       competitor #1 and ignored the rest, so with a multi-competitor
       workspace the steps completed while other competitors were still
       crawling and the screen then waited forever. */
    const competitors = useMemo(
        () => (workspace?.competitors || []).filter((comp) => comp?.role === 'Competitor'),
        [workspace?.competitors]
    )

    const isCompleted = (status) => status?.toLowerCase() === 'completed'
    const isFailed = (status) => {
        const value = status?.toLowerCase()
        return value === 'failed' || value === 'error' || value === 'blocked'
    }

    const progress = useMemo(() => {
        const allPages = competitors.flatMap((comp) => comp?.pages || [])

        const pagesTotal = allPages.length
        const pagesDone = allPages.filter((page) => isCompleted(page?.scanStatus)).length
        const pagesFailed = allPages.filter((page) => isFailed(page?.scanStatus)).length

        /* Settled, not completed. A failed page will never reach 'completed',
           so gating on completion alone stalls step 1 permanently. */
        const pagesSettled = pagesDone + pagesFailed

        const competitorsTotal = competitors.length
        const competitorsDone = competitors.filter((comp) => isCompleted(comp?.scanStatus)).length
        const competitorsFailed = competitors.filter((comp) => isFailed(comp?.scanStatus)).length
        const competitorsSettled = competitorsDone + competitorsFailed

        return {
            pagesTotal,
            pagesDone,
            pagesFailed,
            allPagesSettled: pagesTotal > 0 && pagesSettled === pagesTotal,
            competitorsTotal,
            competitorsDone,
            competitorsFailed,
            allCompetitorsSettled: competitorsTotal > 0 && competitorsSettled === competitorsTotal,
            /* Every competitor failed -- there is nothing left to report on. */
            everythingFailed: competitorsTotal > 0 && competitorsFailed === competitorsTotal,
        }
    }, [competitors])

    const statuses = ['pending', 'pending', 'pending']
    let current = 0

    // Step 1: Page Analysis -- across every competitor
    if (progress.pagesTotal > 0) {
        statuses[0] = progress.allPagesSettled ? 'done' : 'active'
        current = progress.allPagesSettled ? 1 : 0
    }

    // Step 2: Competitor Analysis -- waits for ALL competitors to settle
    if (progress.allPagesSettled) {
        statuses[1] = progress.allCompetitorsSettled ? 'done' : 'active'
        current = progress.allCompetitorsSettled ? 2 : 1
    }

    // Step 3: Report Generation
    if (progress.allCompetitorsSettled) {
        statuses[2] = 'active'
        current = 2
    }

    // Step 4: Analysis Ready
    if (workspaceAnalysis) {
        statuses[0] = 'done'
        statuses[1] = 'done'
        statuses[2] = 'done'
        current = 3
    }

    /* ── Stall detection ──────────────────────────────────────────
       Tracks whether anything advanced. If the fingerprint stops moving
       for STALL_TIMEOUT_MS the run is wedged -- surface it instead of
       spinning. Rate-limit rejections upstream land here. */
    const [stalled, setStalled] = useState(false)
    const [retrying, setRetrying] = useState(false)

    /* Report-generation failure: pages + competitors all finished, but the
       workspace-level report produced NOTHING (backend marks scanStatus Failed).
       Distinct from a crawl failure -- here retrying the report is what helps. */
    const scan = workspace?.scanStatus?.toLowerCase()
    const reportFailed = progress.allCompetitorsSettled && !workspaceAnalysis &&
        (scan === 'failed' || scan === 'partial')

    /* Which failure are we in? Drives the message + the right recovery action. */
    const failureMode = !workspaceAnalysis
        ? (reportFailed ? 'report' : progress.everythingFailed ? 'crawl' : stalled ? 'stall' : null)
        : null

    const handleRetry = async () => {
        if (retrying || !workspace?.id) return
        setRetrying(true)
        setStalled(false)
        try {
            await rescanWorkspace(workspace.id)
            await useWorkspaceStore.getState().syncWorkspace()
        } catch (e) {
            console.error('Retry failed:', e)
        } finally {
            setRetrying(false)
        }
    }

    const fingerprint = `${progress.pagesDone}/${progress.pagesFailed}/${progress.pagesTotal}` +
        `|${progress.competitorsDone}/${progress.competitorsFailed}/${progress.competitorsTotal}` +
        `|${workspaceAnalysis ? 'ready' : 'waiting'}`

    /* The fingerprint is the dependency: any real progress re-runs this
       effect, which clears the flag and restarts the clock. */
    useEffect(() => {
        if (workspaceAnalysis) return

        setStalled(false)

        const timer = setTimeout(() => setStalled(true), STALL_TIMEOUT_MS)
        return () => clearTimeout(timer)
    }, [fingerprint, workspaceAnalysis])

    useEffect(() => {
        if (!workspaceAnalysis) return;
        console.log('🔴 Analysis ready, navigating to analysis screen');

        const analysisId = workspaceAnalysis?.analysisId;
        console.log(`🔴 First Analysis ID:`, analysisId);
        // setIntroCompleted(true);
        markIntroCompleted()
        navigate(`/analysis/${analysisId}`, { replace: true });
    }, [workspaceAnalysis, navigate]);

    // Calculate progress
    const doneCount = statuses.filter(status => status === 'done').length;

    /* Continuous progress % — moves as each PAGE and COMPETITOR settles, instead
       of jumping in thirds. Pages are the long pole (weight 50%), competitors and
       the report split the rest. Feels like a real loading bar. */
    const pagesFrac = progress.pagesTotal
        ? (progress.pagesDone + progress.pagesFailed) / progress.pagesTotal
        : 0;
    const compFrac = progress.competitorsTotal
        ? (progress.competitorsDone + progress.competitorsFailed) / progress.competitorsTotal
        : 0;
    let percent = Math.round(50 * pagesFrac + 25 * compFrac + (workspaceAnalysis ? 25 : 0));
    if (workspaceAnalysis) percent = 100;
    else if (percent >= 100) percent = 99;       // never show 100 until truly ready
    else if (percent < 5 && progress.pagesTotal > 0) percent = 5; // feels alive at the start

    // eslint-disable-next-line no-unused-vars
    const renderIcon = (status, Icon) => {
        if (status === 'done') {
            return (
                <CheckCircle2 className="h-6 w-6" style={{ color: 'var(--success)' }} />
            )
        }

        if (status === 'active') {
            return (
                <LoaderCircle className="h-6 w-6 animate-spin" style={{ color: 'var(--accent)' }} />
            )
        }

        return (
            <Icon className="h-6 w-6" style={{ color: 'var(--text-light)' }} />
        )
    }

    const handleLogout = async () => {
        try { await logout(); } catch (e) { console.error('Logout failed:', e); }
    };

    // Capture-first: while recon is running, show the recon progress view instead
    // of the deep-analysis tracker (no analysis is running yet at this stage).
    if (setupStage === 'recon') {
        return <ReconProgress workspace={workspace} onLogout={handleLogout} />;
    }

    // Recon done → the effect above is redirecting to the workspace. Render nothing
    // so the old deep-analysis screen doesn't flash for a frame during the redirect.
    if (setupStage === 'selecting') {
        return null;
    }

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
        <OnboardingHeader onLogout={handleLogout} />
        <div className="relative w-full overflow-hidden px-4 py-10 sm:py-12 flex items-start justify-center">
            {/* soft brand glows for depth, matching the marketing site */}
            <div className="pointer-events-none absolute -right-24 -top-16 h-72 w-72 rounded-full bg-[var(--glow-teal)] blur-3xl" />
            <div className="pointer-events-none absolute -left-24 top-40 h-72 w-72 rounded-full bg-[var(--glow-coral)] blur-3xl" />

            <div className="relative w-full max-w-2xl">
                {/* Header Section */}
                <div className="mb-10 text-center">
                    <h1
                        className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-3"
                        style={{ color: 'var(--primary)' }}
                    >
                        Setting up your{' '}
                        <span className="serif" style={{ color: 'var(--secondary)' }}>workspace</span>
                    </h1>

                    <p
                        className="text-base sm:text-lg max-w-lg mx-auto leading-relaxed"
                        style={{ color: 'var(--text-light)' }}
                    >
                        We're analyzing your competitive landscape to build your first intelligence report.
                    </p>
                </div>

                {/* Stall / failure notice -- the screen must never just spin */}
                {failureMode && (
                    <div
                        className="mb-8 rounded-2xl border-2 p-5 flex items-start gap-4"
                        style={{
                            borderColor: 'color-mix(in srgb, var(--danger, #dc2626) 35%, transparent)',
                            background: 'color-mix(in srgb, var(--danger, #dc2626) 6%, var(--card))',
                        }}
                    >
                        <AlertTriangle
                            className="h-6 w-6 shrink-0 mt-0.5"
                            style={{ color: 'var(--danger, #dc2626)' }}
                        />
                        <div className="flex-1">
                            <h3 className="text-base font-bold mb-1" style={{ color: 'var(--text)' }}>
                                {failureMode === 'report'
                                    ? "We couldn't generate your report"
                                    : failureMode === 'crawl'
                                        ? 'We could not analyze your competitors'
                                        : 'This is taking longer than expected'}
                            </h3>
                            <p className="text-sm mb-3" style={{ color: 'var(--text-light)' }}>
                                {failureMode === 'report'
                                    ? 'Your pages were scanned, but the report step failed to complete. This can happen with very large stores. You can retry it now.'
                                    : failureMode === 'crawl'
                                        ? 'Every competitor store failed to scan. This usually means the stores blocked our crawler.'
                                        : 'The analysis has not progressed in a while. It may still finish, or it may have stalled.'}
                            </p>
                            {failureMode === 'report' || failureMode === 'crawl' ? (
                                <button
                                    onClick={handleRetry}
                                    disabled={retrying}
                                    className="text-sm font-semibold px-4 py-2 rounded-lg inline-flex items-center gap-2 disabled:opacity-60"
                                    style={{ background: 'var(--primary)', color: '#fff' }}
                                >
                                    {retrying && <LoaderCircle className="h-4 w-4 animate-spin" />}
                                    {retrying ? 'Retrying…' : 'Retry analysis'}
                                </button>
                            ) : (
                                <button
                                    onClick={() => window.location.reload()}
                                    className="text-sm font-semibold px-4 py-2 rounded-lg"
                                    style={{ background: 'var(--primary)', color: '#fff' }}
                                >
                                    Refresh status
                                </button>
                            )}
                        </div>
                    </div>
                )}

                {/* Progress Bar */}
                <div className="mb-8">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>Progress</span>
                        <span className="text-sm font-bold" style={{ color: 'var(--secondary-dark)' }}>
                            {percent}%
                        </span>
                    </div>
                    <div
                        className="relative w-full h-2.5 rounded-full overflow-hidden"
                        style={{ background: 'var(--border)' }}
                    >
                        <div
                            className="relative h-full transition-all duration-700 ease-out rounded-full overflow-hidden"
                            style={{
                                width: `${percent}%`,
                                background: 'linear-gradient(90deg, var(--secondary), var(--accent))',
                            }}
                        >
                            {/* Moving sheen so the bar reads as "working" even between settles. */}
                            {!workspaceAnalysis && (
                                <div
                                    className="absolute inset-0"
                                    style={{
                                        background:
                                            'linear-gradient(90deg, transparent, rgba(255,255,255,0.45), transparent)',
                                        animation: 'is-shimmer 1.4s linear infinite',
                                    }}
                                />
                            )}
                        </div>
                    </div>
                    <style>{`@keyframes is-shimmer { from { transform: translateX(-100%); } to { transform: translateX(100%); } }`}</style>
                </div>

                {/* Steps Container */}
                <div className="space-y-3 mb-8">
                    {STEPS.map((step, idx) => {
                        const status = statuses[idx];
                        const isActive = idx === current;
                        const isDone = status === 'done';

                        const cardStyle = isActive
                            ? {
                                borderColor: 'var(--accent)',
                                background: 'color-mix(in srgb, var(--accent) 6%, var(--card))',
                                boxShadow: 'var(--shadow-md)',
                            }
                            : isDone
                                ? {
                                    borderColor: 'color-mix(in srgb, var(--success) 35%, transparent)',
                                    background: 'color-mix(in srgb, var(--success) 6%, var(--card))',
                                }
                                : {
                                    borderColor: 'var(--border)',
                                    background: 'var(--card)',
                                };

                        const iconWrapStyle = isActive
                            ? { background: 'var(--primary)' }
                            : isDone
                                ? { background: 'color-mix(in srgb, var(--success) 16%, var(--card))' }
                                : { background: 'var(--background)' };

                        const titleStyle = isActive
                            ? { color: 'var(--primary)' }
                            : isDone
                                ? { color: 'var(--success)' }
                                : { color: 'var(--text)' };

                        const badgeStyle = isActive
                            ? { background: 'var(--primary)', color: '#fff' }
                            : isDone
                                ? { background: 'color-mix(in srgb, var(--success) 18%, var(--card))', color: 'var(--success)' }
                                : { background: 'var(--border)', color: 'var(--text-light)' };

                        return (
                            <div
                                key={step.key}
                                className="group relative rounded-2xl border-2 transition-all duration-300 p-5"
                                style={cardStyle}
                            >
                                <div className="flex items-start gap-4">
                                    {/* Icon Container */}
                                    <div
                                        className="shrink-0 rounded-xl p-3 transition-all duration-300"
                                        style={iconWrapStyle}
                                    >
                                        {renderIcon(status, step.Icon)}
                                    </div>

                                    {/* Content */}
                                    <div className="flex-1 min-w-0">
                                        <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                                            <h3
                                                className="text-base sm:text-lg font-bold transition-colors"
                                                style={titleStyle}
                                            >
                                                {step.title}
                                            </h3>
                                            <span
                                                className="text-xs font-bold uppercase tracking-wide px-2.5 py-1 rounded-lg whitespace-nowrap"
                                                style={badgeStyle}
                                            >
                                                {idx === current
                                                    ? 'In progress'
                                                    : isDone
                                                        ? 'Completed'
                                                        : 'Pending'}
                                            </span>
                                        </div>
                                        <p className="text-sm line-clamp-2" style={{ color: 'var(--text-light)' }}>
                                            {step.desc}
                                        </p>

                                        {/* Live counts, so multi-competitor runs
                                            show real progress instead of a
                                            spinner that reflects competitor #1 */}
                                        {step.key === 'pages' && progress.pagesTotal > 0 && (
                                            <p className="text-xs mt-1.5 font-medium" style={{ color: 'var(--text-light)' }}>
                                                {progress.pagesDone} of {progress.pagesTotal} pages analyzed
                                                {progress.pagesFailed > 0 && ` · ${progress.pagesFailed} could not be scanned`}
                                            </p>
                                        )}

                                        {step.key === 'competitors' && progress.competitorsTotal > 0 && (
                                            <p className="text-xs mt-1.5 font-medium" style={{ color: 'var(--text-light)' }}>
                                                {progress.competitorsDone} of {progress.competitorsTotal} competitors analyzed
                                                {progress.competitorsFailed > 0 && ` · ${progress.competitorsFailed} failed`}
                                            </p>
                                        )}
                                    </div>

                                    {/* Activity Indicator */}
                                    {isActive && (
                                        <div className="shrink-0 flex gap-1">
                                            {[0, 1, 2].map((dot) => (
                                                <div
                                                    key={dot}
                                                    className="h-2 w-2 rounded-full animate-pulse"
                                                    style={{
                                                        background: 'var(--accent)',
                                                        animationDelay: `${dot * 0.2}s`,
                                                    }}
                                                />
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* Connecting Line */}
                                {idx < STEPS.length - 1 && (
                                    <div
                                        className="absolute left-9 top-full h-3 w-0.5 transition-colors"
                                        style={{
                                            background: isDone
                                                ? 'color-mix(in srgb, var(--success) 40%, transparent)'
                                                : 'var(--border)',
                                        }}
                                    />
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* Footer Message */}
                <div className="text-center pt-6 border-t" style={{ borderColor: 'var(--border)' }}>
                    <p className="text-sm" style={{ color: 'var(--text-light)' }}>
                        {statuses[2] === 'done'
                            ? '✨ Your workspace is ready! Redirecting...'
                            : progress.competitorsTotal > 1
                                ? `Analyzing ${progress.competitorsTotal} competitors. This usually takes a few minutes.`
                                : 'This usually takes a few minutes.'}
                    </p>
                </div>
            </div>
        </div>
        </div>
    )
}

export default Intro