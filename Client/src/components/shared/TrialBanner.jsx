import React from "react";
import { useNavigate } from "react-router-dom";
import { Clock } from "lucide-react";
import useAuthStore from "../../store/auth.store";

/* Top bar for trial users: how many days remain, plus an upgrade CTA. Renders
   nothing for non-trial users. Reads the trial window from the user's subscription
   (status "trialing" + trialEnd), which the API already returns. */
export default function TrialBanner() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const sub = user?.subscription;

  if (!sub || sub.status !== "trialing" || !sub.trialEnd) return null;

  const end = new Date(sub.trialEnd);
  const msLeft = end.getTime() - Date.now();
  const daysLeft = Math.max(0, Math.ceil(msLeft / 86400000));
  const expired = msLeft <= 0;

  const message = expired
    ? "Your free trial has ended."
    : `${daysLeft} ${daysLeft === 1 ? "day" : "days"} left in your free trial.`;

  const upgradeLink = (
    <button
      type="button"
      onClick={() => navigate("/settings/billing")}
      className="font-semibold text-white underline underline-offset-2 transition hover:opacity-80"
    >
      Upgrade
    </button>
  );
  const sub2 = expired
    ? <>{upgradeLink} to resume monitoring and unlock all features.</>
    : <>{upgradeLink} any time to keep monitoring after it ends.</>;

  return (
    <div className="w-full" style={{ background: "linear-gradient(90deg, var(--primary), var(--secondary-dark, var(--primary)))" }}>
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-center gap-2 px-4 py-2.5 text-center">
        <Clock size={16} className="shrink-0 text-white opacity-90" />
        <p className="text-sm text-white">
          <span className="font-semibold">{message}</span>
          <span className="ml-2 opacity-90">{sub2}</span>
        </p>
      </div>
    </div>
  );
}
