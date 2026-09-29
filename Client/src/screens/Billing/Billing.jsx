import { Rocket, ArrowLeft } from "lucide-react";
import { useLoaderData } from "react-router-dom";
import { useNavigate } from "react-router";

import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import useAuthStore from "../../store/auth.store";
import useWorkspaceStore from "../../store/workspace.store";
import OnboardingHeader from "../../components/features/OnBoarding/OnboardingHeader";

import { createFreeTrialSubscription } from "../../api/subscription.api";
import { getPaddleCheckout } from "../../services/paddle";
import { logout } from "../../api/user.api";

function Billing() {
  const planId = useAuthStore((state) => state.user?.plan);
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const workspace = useWorkspaceStore((state) => state.workspace);

  // They reached /billing from onboarding (already have a trial subscription but
  // haven't finished the workspace) — offer a way back so they aren't stuck here.
  const cameFromOnboarding = Boolean(user?.subscription) && !workspace;

  const plans = useLoaderData();
  // Enterprise is a "contact us" plan (price 0 + contactSales) — keep it out of the
  // free-trial and paid buckets so it renders its own card with a contact CTA.
  const enterprisePlan = plans.find((plan) => plan.contactSales || plan.name === "enterprise");
  const paidPlans = plans.filter((plan) => plan.price > 0);
  const freePlan = plans.find((plan) => plan.price === 0 && !plan.contactSales && plan.name !== "enterprise");

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error("Logout failed:", error);
    }
  };

  const handleCheckout = async (priceId, planId) => {
    try {
      await getPaddleCheckout(priceId, planId, user, "billing-success");
    } catch (error) {
      console.error("Error creating checkout session:", error);
    }
  };

  const handleFreeTrial = async (priceId, planId) => {
    try {
      await createFreeTrialSubscription(priceId, planId);
      navigate("/onboarding", { replace: true });
    } catch (error) {
      console.error("Error creating free trial subscription:", error);
    }
  };

  return (
    <div className="min-h-screen bg-(--bg)">
      <OnboardingHeader onLogout={handleLogout}>
        {cameFromOnboarding && (
          <button
            type="button"
            className="is-logout"
            onClick={() => navigate("/onboarding")}
          >
            <ArrowLeft size={14} />
            Back to setup
          </button>
        )}
      </OnboardingHeader>

      <div className="relative overflow-hidden px-4 py-10 sm:px-6">
        {/* soft brand glows, matching the marketing site */}
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-[var(--glow-teal)] blur-3xl" />
        <div className="pointer-events-none absolute -left-24 top-40 h-72 w-72 rounded-full bg-[var(--glow-coral)] blur-3xl" />

        <div className="relative mx-auto w-full max-w-6xl">
          {/* ── Heading ── */}
          <div className="text-center">
            <span
              className="inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-bold uppercase tracking-[0.08em] text-(--secondary)"
              style={{
                background: "color-mix(in srgb, var(--secondary) 10%, transparent)",
                border: "1px solid color-mix(in srgb, var(--secondary) 25%, transparent)",
              }}
            >
              <span className="h-2 w-2 rounded-full bg-(--secondary)" />
              Pricing
            </span>

            <h1 className="mx-auto mt-4 max-w-3xl text-3xl font-extrabold tracking-tight text-(--primary) sm:text-4xl">
              Choose the coverage your{" "}
              <span className="serif text-(--secondary)">market</span> needs
            </h1>

            <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-(--text-light) sm:text-base">
              Every plan includes homepage monitoring, AI insights, and instant
              alerts. Upgrade when you need more competitors, more pages per
              competitor, faster monitoring, and historical tracking.
            </p>
          </div>

          {/* ── Free-trial banner ── */}
          <div className="mt-8 rounded-3xl border border-[rgba(78,205,196,0.28)] bg-white p-6 shadow-(--shadow-sm) md:p-7">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-start gap-4">
                <span
                  className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl"
                  style={{
                    background: "color-mix(in srgb, var(--secondary) 14%, transparent)",
                    color: "var(--secondary)",
                  }}
                >
                  <Rocket size={22} strokeWidth={1.9} />
                </span>

                <div>
                  <span className="inline-flex items-center gap-2 rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-[0.08em] text-(--secondary)"
                    style={{ background: "color-mix(in srgb, var(--secondary) 12%, transparent)" }}>
                    Free trial
                  </span>
                  <h3 className="mt-2 text-xl font-bold text-(--primary)">
                    Try IntelShift before choosing a plan
                  </h3>
                  <p className="mt-1.5 max-w-2xl text-sm leading-6 text-(--text-light)">
                    Track 1 competitor with no credit card required — test the
                    monitoring flow, AI insights, and alerts before you commit.
                  </p>
                </div>
              </div>

              <Button
                type="button"
                title="Start free trial"
                onClick={() => handleFreeTrial(freePlan?.priceId, freePlan?._id)}
                showLoading={true}
                className="shrink-0 px-7"
              />
            </div>
          </div>

          {/* ── Paid plans ── */}
          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3 lg:gap-5">
            {paidPlans?.map((plan) => (
              <Card
                key={plan._id}
                planType={plan.displayName}
                description={plan.description}
                planId={plan.planId}
                price={plan.price}
                limitations={plan.features}
                isCurrent={plan._id === planId}
                buttonText="Select"
                onButtonClick={() => handleCheckout(plan.priceId, plan._id)}
                priceId={plan.priceId}
              />
            ))}
          </div>

          {/* ── Enterprise (contact us) ── */}
          {enterprisePlan && (
            <div className="mt-4 flex flex-col items-start justify-between gap-4 rounded-2xl border border-(--border) bg-(--card) p-6 sm:flex-row sm:items-center">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-bold text-(--text)">{enterprisePlan.displayName}</h3>
                  <span className="rounded-full bg-(--glow-teal) px-2.5 py-0.5 text-xs font-semibold text-(--secondary)">
                    Custom pricing
                  </span>
                </div>
                <p className="mt-1 max-w-xl text-sm text-(--text-light)">
                  {enterprisePlan.description}
                </p>
              </div>
              <a
                href={`mailto:sales@intelshift.ai?subject=${encodeURIComponent("Enterprise enquiry")}`}
                className="shrink-0 rounded-xl bg-(--primary) px-6 py-3 text-sm font-semibold text-white"
              >
                Talk to us
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Billing;
