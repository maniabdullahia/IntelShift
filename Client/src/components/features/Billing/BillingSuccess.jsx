import { CheckCircle2, LoaderCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useState, useEffect } from "react";

import Button from "../../ui/Button";
import useAuthStore from "../../../store/auth.store";
import OnboardingHeader from "../OnBoarding/OnboardingHeader";
import { logout } from "../../../api/user.api";

function BillingSuccess() {
  const navigate = useNavigate();

  const [ fetchingSubscription, setFetchingSubscription ] = useState(true);

  const user = useAuthStore((state) => state.user);
  const syncUser = useAuthStore((state) => state.syncUser);

  // Same logout the onboarding header fires — the route guard handles redirect.
  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error("❌ Logout failed:", error);
    }
  };

  // The plan is finalised by an async Paddle webhook, so re-sync the user a few
  // times until the paid plan lands (instead of trusting the stale store copy).
  useEffect(() => {
    let attempts = 0;
    let timer;
    let alive = true;

    const poll = async () => {
      attempts += 1;
      try {
        const fresh = await syncUser();
        const name = String(fresh?.subscription?.planId?.name || "").toLowerCase();
        if (!alive) return;
        if ((name && name !== "trial") || attempts >= 6) {
          setFetchingSubscription(false);
          return;
        }
      } catch {
        /* keep polling */
      }
      if (alive) timer = setTimeout(poll, 2000);
    };

    poll();
    return () => { alive = false; clearTimeout(timer); };
  }, [syncUser]);

  const planName = user?.subscription?.planId?.displayName || "your plan";

  if (fetchingSubscription) {
    return (
      <>
        <OnboardingHeader onLogout={handleLogout} />
        <div className="bg-(--background) flex min-h-[calc(100vh-72px)] items-center justify-center px-4">
          <div className="flex flex-col items-center gap-3 text-center">
            <LoaderCircle size={28} className="animate-spin text-(--secondary)" />
            <p className="text-lg font-semibold text-(--primary)">Confirming your payment…</p>
            <p className="text-sm text-(--text-light)">This only takes a moment.</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <OnboardingHeader onLogout={handleLogout} />

      <div className="bg-(--background) min-h-[calc(100vh-72px)] px-4 py-10 sm:px-6 sm:py-14">
        <div className="mx-auto w-full max-w-4xl">
          <div className="rounded-4xl border border-(--border) bg-white p-8 shadow-[0_24px_60px_rgba(15,23,42,0.08)] transition-all duration-300 sm:p-10">
            <div className="flex flex-col items-center justify-center gap-6 text-center">
              <div className="flex h-20 w-20 items-center justify-center rounded-full bg-[rgba(38,222,129,0.16)] text-(--success)">
                <CheckCircle2 size={36} />
              </div>

              <div className="space-y-3">
                <p className="inline-flex rounded-full border border-(--success) bg-[rgba(38,222,129,0.08)] px-4 py-1 text-sm font-semibold uppercase tracking-[0.22em] text-(--success)">
                  Payment confirmed
                </p>
                <h1 className="text-3xl font-bold text-(--primary) sm:text-4xl">
                  Your subscription is active
                </h1>
                <p className="mx-auto max-w-2xl text-base leading-7 text-(--text-light)">
                  You&apos;re all set. IntelShift is now monitoring your market, and your selected plan <span className="font-semibold text-(--primary)">{planName}</span> is active.
                </p>
              </div>

              <div className="">
                <Button
                  type="button"
                  title="Continue setup"
                  onClick={() => navigate("/")}
                  className="rounded-full bg-(--accent) px-6 py-3 text-sm font-semibold text-white"
                />
                
              </div>
            </div>

           
          </div>
        </div>
      </div>
    </>
  );
}

export default BillingSuccess;
