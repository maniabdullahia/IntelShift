import { useEffect, useState } from "react";
import { useLoaderData } from "react-router-dom";
import { CreditCard, XCircle, Trash2, RotateCcw } from "lucide-react";
import Card from "../../../components/ui/Card";
import Swal from "../../../components/shared/Alert";

import useAuthStore from "../../../store/auth.store";
import useWorkspaceStore from "../../../store/workspace.store";
import { cancelDowngrade } from "../../../api/downgrade.api";
import { getBillingActions, cancelSubscription } from "../../../api/billing.api";
import { requestAccountDeletion, reactivateAccount } from "../../../api/account.api";

function BillingAndUsage() {
  const workspace = useWorkspaceStore((state) => state.workspace);
  const user = useAuthStore((state) => state.user);
  const syncUser = useAuthStore((state) => state.syncUser);
  const currentPlan = useAuthStore((state) => state.user?.subscription?.planId);
  const planId = currentPlan?._id || currentPlan;
  const [cancelling, setCancelling] = useState(false);
  const [cancellingSub, setCancellingSub] = useState(false);
  const [closing, setClosing] = useState(false);
  const [billing, setBilling] = useState(null);
  const deletion = user?.deletion || {};
  const closurePending = ["requested", "scheduled", "deactivated"].includes(deletion.status);
  const competitors = workspace?.competitors || [];
  const filteredCompetitors = competitors?.filter(
    (competitor) => competitor.role == "Competitor",
  );

  const competitorCount = Number(filteredCompetitors?.length) || 0;
  const totalCompetitorsAllowed = useAuthStore(
    (state) => state.user?.subscription?.planId?.limits?.competitors,
  );

  const pagesLimit =
    user?.subscription?.planId?.limits?.pagesPerCompetitor || 0;
  const competitorLimits = user?.subscription?.planId?.limits?.competitors || 0;

  // Homepage is tracked automatically and isn't counted against the plan limit.
  const isHomepageUrl = (raw) => {
    try {
      const s = String(raw || "").trim();
      if (!s) return false;
      const u = new URL(/^https?:\/\//i.test(s) ? s : `https://${s}`);
      return u.pathname === "" || u.pathname === "/";
    } catch {
      return false;
    }
  };

  const pagesCount =
    filteredCompetitors?.reduce((total, competitor) => {
      // Exclude the homepage and pages staged to ADD (not monitored until the next
      // run). Staged removals still count until applied.
      const pages = (competitor.pages || []).filter((p) => !isHomepageUrl(p.url) && p.pendingChange !== "add");
      return total + pages.length;
    }, 0) || 0;
  const plans = useLoaderData();
  const paidPlans = plans.filter((plan) => plan.price > 0);

  // ── Current subscription details ──────────────────────────────────────────
  const subscription = user?.subscription || {};

  // Scheduled downgrade (if any) — so the user can see it and cancel it.
  const pendingDowngrade = subscription?.pendingDowngrade?.planId ? subscription.pendingDowngrade : null;
  const downgradeTargetPlan = pendingDowngrade
    ? plans.find((p) => String(p._id) === String(pendingDowngrade.planId))
    : null;

  const handleCancelDowngrade = async () => {
    setCancelling(true);
    try {
      await cancelDowngrade();
      await syncUser?.();
      Swal.fire({ icon: "success", title: "Downgrade cancelled", text: "You'll stay on your current plan.", timer: 2400, showConfirmButton: false });
    } catch (e) {
      Swal.fire({ icon: "error", title: "Couldn't cancel", text: e?.response?.data?.message || e?.message || "Please try again.", confirmButtonColor: "#ff6b6b" });
    } finally {
      setCancelling(false);
    }
  };

  // Load billing actions (payment-method URL + cancellation state) on mount and
  // whenever subscription status changes.
  useEffect(() => {
    let alive = true;
    getBillingActions()
      .then((d) => { if (alive) setBilling(d); })
      .catch(() => {});
    return () => { alive = false; };
  }, [user?.subscription?.status]);

  const handleUpdatePayment = () => {
    if (billing?.updatePaymentMethodUrl) {
      window.open(billing.updatePaymentMethodUrl, "_blank", "noopener,noreferrer");
    } else {
      Swal.fire({ icon: "info", title: "Not available yet", text: "Payment management appears once you're on a paid plan." });
    }
  };

  const handleCancelSubscription = async () => {
    const confirm = await Swal.fire({
      icon: "warning",
      title: "Cancel your subscription?",
      html: "Your plan stays active until the end of your current billing period, then stops. You keep everything you've paid for until then, and can re-subscribe anytime.",
      showCancelButton: true,
      confirmButtonText: "Cancel at period end",
      confirmButtonColor: "#fc5c65",
      cancelButtonText: "Keep my plan",
    });
    if (!confirm.isConfirmed) return;

    setCancellingSub(true);
    try {
      const res = await cancelSubscription();
      await syncUser?.();
      const refreshed = await getBillingActions().catch(() => null);
      if (refreshed) setBilling(refreshed);
      Swal.fire({
        icon: "success",
        title: "Cancellation scheduled",
        text: res.message,
      });
    } catch (e) {
      Swal.fire({ icon: "error", title: "Couldn't cancel", text: e?.response?.data?.message || e?.message || "Please try again.", confirmButtonColor: "#ff6b6b" });
    } finally {
      setCancellingSub(false);
    }
  };

  const handleRequestClosure = async () => {
    const confirm = await Swal.fire({
      icon: "warning",
      title: "Close your account?",
      html: "We'll email you a confirmation link. Your account isn't touched until you confirm — and even then you keep access until the end of your paid period and can reactivate anytime before deletion.",
      showCancelButton: true,
      confirmButtonText: "Email me the confirmation",
      confirmButtonColor: "#fc5c65",
      cancelButtonText: "Cancel",
    });
    if (!confirm.isConfirmed) return;

    setClosing(true);
    try {
      await requestAccountDeletion();
      await syncUser?.();
      Swal.fire({ icon: "success", title: "Check your email", text: "We've sent a confirmation link to close your account." });
    } catch (e) {
      Swal.fire({ icon: "error", title: "Couldn't start closure", text: e?.response?.data?.message || e?.message || "Please try again.", confirmButtonColor: "#ff6b6b" });
    } finally {
      setClosing(false);
    }
  };

  const handleReactivate = async () => {
    setClosing(true);
    try {
      await reactivateAccount();
      await syncUser?.();
      Swal.fire({ icon: "success", title: "Welcome back", text: "Your account closure has been cancelled." });
    } catch (e) {
      Swal.fire({ icon: "error", title: "Couldn't reactivate", text: e?.response?.data?.message || e?.message || "Please try again.", confirmButtonColor: "#ff6b6b" });
    } finally {
      setClosing(false);
    }
  };

  const cadence = currentPlan?.planReportingFrequency || "once";
  const CADENCE_DAYS = { daily: 1, "2d": 2, "3d": 3, weekly: 7, monthly: 30 };
  const cadenceDays = CADENCE_DAYS[String(cadence).toLowerCase()] || null;
  const CADENCE_LABEL = {
    daily: "Every day",
    "2d": "Every 2 days",
    "3d": "Every 3 days",
    weekly: "Weekly",
    monthly: "Monthly",
    once: "One-time",
  };
  const cadenceLabel = CADENCE_LABEL[String(cadence).toLowerCase()] || "—";
  const renewalDate = subscription?.nextBilledAt || subscription?.currentPeriodEnd || null;
  const fmtDate = (d) =>
    d ? new Date(d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "—";

  // Monitoring runs remaining before the next renewal (derived from cadence).
  let monitoringLeft = null;
  let monitoringTotal = null;
  if (cadenceDays && renewalDate) {
    const msDay = 86400000;
    monitoringLeft = Math.max(0, Math.floor((new Date(renewalDate) - new Date()) / (cadenceDays * msDay)));
    monitoringTotal = Math.max(monitoringLeft, Math.floor(30 / cadenceDays));
  }

  const usageData = [
    {
      usageTitle: "Competitors",
      progressScore: competitorCount,
      totalScore: totalCompetitorsAllowed,
    },
    {
      usageTitle: "Pages Monitored",
      progressScore: pagesCount,
      totalScore: pagesLimit * competitorLimits,
    },
    ...(monitoringTotal
      ? [
          {
            usageTitle: "Monitoring runs left",
            progressScore: monitoringTotal - monitoringLeft,
            totalScore: monitoringTotal,
          },
        ]
      : []),
  ];

  const getUsageTone = (percentage) => {
    if (percentage >= 85) return "bg-(--danger)";
    if (percentage >= 60) return "bg-(--warning)";
    return "bg-(--secondary)";
  };

  const getButtonText = (plan) => {
    const currentPlanPrice = currentPlan?.price;
    if (plan.price === currentPlanPrice) {
      return "Current Plan";
    } else if (plan.price > currentPlanPrice && currentPlanPrice === 0) {
      return "Subscribe";
    } else if (plan.price > currentPlanPrice) {
      return "Upgrade";
    } else {
      return "Downgrade";
    }
  };

  return (
    <div className="bg-(--background) px-4 py-6 sm:px-6 sm:py-8">
      <div className="mx-auto w-full max-w-6xl">
        <div className="relative mb-8 overflow-hidden rounded-3xl border border-(--border) bg-linear-to-r from-(--primary) to-[rgba(26,26,46,0.9)] p-5 shadow-md sm:p-7">
          <div className="pointer-events-none absolute -right-20 -top-16 h-44 w-44 rounded-full bg-[rgba(78,205,196,0.16)] blur-2xl" />
          <div className="pointer-events-none absolute -bottom-20 left-8 h-40 w-40 rounded-full bg-[rgba(255,107,107,0.16)] blur-2xl" />

          <h1 className="relative font-[Inter] tracking-tight text-3xl font-bold text-white sm:text-4xl">
            Billing & Usage
          </h1>
          <p className="relative mt-2 text-white/80">
            Manage your plan and monitor usage
          </p>

          <div className="relative mt-4 inline-flex items-center rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white/90">
            Subscription Overview
          </div>
        </div>

        {/* Scheduled downgrade banner */}
        {pendingDowngrade && (
          <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-amber-300 bg-amber-50 p-5">
            <div>
              <p className="text-sm font-semibold text-amber-800">
                Downgrade scheduled{downgradeTargetPlan ? ` to ${downgradeTargetPlan.displayName}` : ""}
              </p>
              <p className="mt-1 text-sm text-amber-700">
                Takes effect on{" "}
                <strong>{pendingDowngrade.effectiveAt ? new Date(pendingDowngrade.effectiveAt).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" }) : "your next renewal"}</strong>.
                You keep your current plan and everything until then.
              </p>
            </div>
            <button
              type="button"
              onClick={handleCancelDowngrade}
              disabled={cancelling}
              className="inline-flex items-center gap-1.5 rounded-lg bg-white px-4 py-2 text-sm font-bold text-amber-800 border border-amber-300 transition hover:bg-amber-100 disabled:opacity-60"
            >
              {cancelling ? "Cancelling…" : "Cancel downgrade"}
            </button>
          </div>
        )}

        {/* Current plan details */}
        <div className="mb-6 rounded-3xl border border-(--border) bg-white p-5 shadow-sm sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-(--text-light)">Current plan</p>
              <div className="mt-1 flex items-baseline gap-2">
                <h2 className="text-2xl font-bold text-(--primary)">
                  {currentPlan?.displayName || currentPlan?.name || "Free trial"}
                </h2>
                {currentPlan?.price != null && (
                  <span className="text-sm font-medium text-(--text-light)">
                    ${currentPlan.price}/mo
                  </span>
                )}
              </div>
              <span
                className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
                  String(subscription?.status).toLowerCase() === "active"
                    ? "bg-[rgba(38,222,129,0.1)] text-(--success)"
                    : "bg-[rgba(26,26,46,0.06)] text-(--primary)"
                }`}
              >
                {subscription?.status || "trialing"}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm sm:grid-cols-3">
              <div>
                <p className="text-(--text-light)">Monitoring</p>
                <p className="font-semibold text-(--text)">{cadenceLabel}</p>
              </div>
              <div>
                <p className="text-(--text-light)">Renews</p>
                <p className="font-semibold text-(--text)">{fmtDate(renewalDate)}</p>
              </div>
              <div>
                <p className="text-(--text-light)">Competitors</p>
                <p className="font-semibold text-(--text)">{competitorLimits || "—"}</p>
              </div>
              <div>
                <p className="text-(--text-light)">Pages / competitor</p>
                <p className="font-semibold text-(--text)">{pagesLimit || "—"}</p>
              </div>
              <div>
                <p className="text-(--text-light)">History timeline</p>
                <p className="font-semibold text-(--text)">
                  {["growth", "pro"].includes(String(currentPlan?.name).toLowerCase()) ? "Included" : "—"}
                </p>
              </div>
              <div>
                <p className="text-(--text-light)">Change alerts</p>
                <p className="font-semibold text-(--text)">
                  {String(currentPlan?.name).toLowerCase() === "trial" || !currentPlan ? "—" : "Included"}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Current Plan Section */}
        <div className="rounded-3xl border border-(--border) bg-white p-4 shadow-sm sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h1 className="text-xl font-bold text-(--primary) sm:text-2xl">
              Plans
            </h1>
            {planId == "trial" && (
              <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-(--border) bg-[rgba(38,222,129,0.08)] px-3 py-1">
                <span className="relative flex size-3">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-(--success) opacity-75"></span>
                  <span className="relative inline-flex size-3 rounded-full bg-(--success)"></span>
                </span>
                <span className="text-sm font-medium text-(--success)">
                  Free Trial
                </span>
              </div>
            )}
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:gap-5 lg:grid-cols-3">
            {paidPlans?.map((plan) => {
              return (
                <Card
                  key={plan._id}
                  planType={plan.displayName}
                  description={plan.description}
                  planId={plan._id}
                  price={plan.price}
                  limitations={plan.features}
                  isCurrent={plan._id === planId}
                  buttonText={getButtonText(plan)}
                  priceId={plan.priceId}
                />
              );
            })}
          </div>
        </div>
        {/* Usage Section */}
        <div className="mt-10">
          <h1 className="my-3 text-xl font-bold text-(--primary)">
            Usage This Month
          </h1>
          <div className="grid grid-cols-1 gap-4 sm:gap-5 md:grid-cols-2 lg:grid-cols-3">
            {usageData?.map((usage, index) => {
              const progressPercentage =
                (usage.progressScore / usage.totalScore) * 100;
              const usageTone = getUsageTone(progressPercentage);
              return (
                <div
                  key={index}
                  className="rounded-2xl border border-(--border) bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md sm:p-5"
                >
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <h2 className="text-md font-semibold text-(--primary)">
                      {usage.usageTitle}
                    </h2>
                    <span className="rounded-full bg-[rgba(26,26,46,0.06)] px-2.5 py-1 text-xs font-semibold text-(--primary)">
                      {Math.round(progressPercentage)}%
                    </span>
                  </div>

                  <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-(--border)">
                    <div
                      className={`${usageTone} h-2 rounded-full transition-all duration-300`}
                      style={{ width: `${Math.min(progressPercentage, 100)}%` }}
                    />
                  </div>

                  <div className="mt-2 flex items-center justify-between text-sm text-(--text-light)">
                    <p>{`${usage.progressScore} of ${usage.totalScore} used`}</p>
                    <p className="font-medium text-(--primary)">{`${Math.max(usage.totalScore - usage.progressScore, 0)} left`}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Manage subscription — payment method + cancel/unsubscribe */}
        <div className="mt-10 rounded-3xl border border-(--border) bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-xl font-bold text-(--primary)">Manage subscription</h2>
          <p className="mt-1 text-sm text-(--text-light)">
            Update your card or cancel your plan. Payments are handled on Paddle's secure hosted pages — we never store card details.
          </p>

          {billing?.cancelAtPeriodEnd && (
            <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
              Your subscription is set to cancel at the end of the current period
              {billing?.periodEnd ? ` (${fmtDate(billing.periodEnd)})` : ""}. You keep full access until then.
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleUpdatePayment}
              disabled={!billing?.hasSubscription}
              className="inline-flex items-center gap-2 rounded-lg border border-(--border) bg-white px-4 py-2 text-sm font-semibold text-(--primary) transition hover:bg-[rgba(0,0,0,0.03)] disabled:opacity-50"
            >
              <CreditCard size={16} /> Update payment method
            </button>

            {billing?.hasSubscription && !billing?.cancelAtPeriodEnd && String(billing?.status).toLowerCase() !== "canceled" && (
              <button
                type="button"
                onClick={handleCancelSubscription}
                disabled={cancellingSub}
                className="inline-flex items-center gap-2 rounded-lg border border-(--danger) px-4 py-2 text-sm font-semibold text-(--danger) transition hover:bg-(--danger) hover:text-white disabled:opacity-60"
              >
                <XCircle size={16} /> {cancellingSub ? "Please wait…" : "Cancel subscription"}
              </button>
            )}
          </div>

          {!billing?.hasSubscription && (
            <p className="mt-3 text-xs text-(--text-light)">
              You're on a free trial — payment management and cancellation appear once you subscribe to a paid plan.
            </p>
          )}
        </div>

        {/* Danger Zone — staged, reversible account closure */}
        <div className="mt-6 mb-2 rounded-3xl border border-(--danger)/30 bg-white p-5 shadow-sm sm:p-6">
          <h3 className="mb-2 flex items-center gap-2 text-lg font-bold text-(--danger)">
            <Trash2 size={20} /> Danger Zone
          </h3>
          <p className="mb-4 text-sm text-(--text-light)">
            Closing your account stops future billing and removes your workspace, competitors and history. It happens in stages so you can change your mind:
          </p>
          <ol className="mb-5 space-y-2 text-sm text-(--text)">
            <li className="flex gap-2"><span className="font-bold text-(--secondary-dark)">1.</span> We email you a confirmation link — nothing changes until you click it.</li>
            <li className="flex gap-2"><span className="font-bold text-(--secondary-dark)">2.</span> Your subscription is cancelled, but you keep full access until the end of your paid period.</li>
            <li className="flex gap-2"><span className="font-bold text-(--secondary-dark)">3.</span> After a 14-day grace window your data is permanently deleted. Reactivate anytime before then.</li>
          </ol>
          {closurePending ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-(--danger)/20 bg-(--danger)/5 p-4">
              <p className="text-sm text-(--text)">A closure is already in progress. You can cancel it and keep your account.</p>
              <button
                type="button"
                onClick={handleReactivate}
                disabled={closing}
                className="inline-flex items-center gap-1.5 rounded-lg border border-(--secondary-dark) px-4 py-2 text-sm font-bold text-(--secondary-dark) transition hover:bg-(--secondary-dark) hover:text-white disabled:opacity-60"
              >
                <RotateCcw size={14} className={closing ? "animate-spin" : ""} /> Reactivate account
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={handleRequestClosure}
              disabled={closing}
              className="inline-flex items-center gap-1.5 rounded-lg border border-(--danger) px-4 py-2 text-sm font-bold text-(--danger) transition hover:bg-(--danger) hover:text-white disabled:opacity-60"
            >
              <Trash2 size={14} /> {closing ? "Please wait…" : "Close my account"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default BillingAndUsage;
