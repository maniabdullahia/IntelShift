import { useEffect, useMemo, useRef, useState } from "react";
import { useLoaderData } from "react-router-dom";
import { useNavigate } from "react-router";
import { Check, ArrowLeft, ShieldCheck, Lock } from "lucide-react";

import Brand from "../../components/shared/Brand";
import useAuthStore from "../../store/auth.store";
import { logout } from "../../api/user.api";
import {
  readCheckoutIntent,
  openInlineCheckout,
} from "../../services/paddle/paddle.service";

/* ────────────────────────────────────────────────────────────────
   Custom dark checkout — order summary + Paddle inline frame, in the
   spirit of the OpenAI/Claude/Stripe embedded checkout. The card form
   itself is Paddle's secure frame (themed dark); everything around it
   is ours.
──────────────────────────────────────────────────────────────── */

export default function Checkout() {
  const plans = useLoaderData() || [];
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const intent = useMemo(() => readCheckoutIntent(), []);
  const plan = useMemo(
    () =>
      plans.find((p) => p.priceId === intent?.priceId) ||
      plans.find((p) => String(p._id) === String(intent?.planId)) ||
      null,
    [plans, intent]
  );

  const [consented, setConsented] = useState(false);
  const openedRef = useRef(false);

  // Nothing chosen (or a stale visit) — send them back to pick a plan.
  useEffect(() => {
    if (!intent || !plan) navigate("/billing", { replace: true });
  }, [intent, plan, navigate]);

  // After consent, embed the Paddle inline checkout into the frame.
  useEffect(() => {
    if (!consented || openedRef.current || !plan || !intent) return;
    openedRef.current = true;
    openInlineCheckout({
      priceId: intent.priceId || plan.priceId,
      planId: intent.planId || plan._id,
      user,
      successUrl: intent.successUrl,
      consentAt: new Date().toISOString(),
    }).catch((e) => {
      console.error("Inline checkout failed:", e);
      openedRef.current = false;
    });
  }, [consented, plan, intent, user]);

  if (!plan) return null;

  const features = plan.features || plan.limitations || [];

  return (
    <div
      className="min-h-screen"
      style={{ background: "linear-gradient(160deg, var(--primary), var(--primary-2))" }}
    >
      {/* Minimal dark header */}
      <header className="flex items-center justify-between px-4 py-4 sm:px-8">
        <Brand tone="light" />
        <button
          type="button"
          onClick={() => navigate("/billing")}
          className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/[0.08] px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/[0.14]"
        >
          <ArrowLeft size={15} /> Back to plans
        </button>
      </header>

      <div className="mx-auto grid w-full max-w-5xl gap-6 px-4 pb-16 pt-4 sm:px-8 lg:grid-cols-2 lg:gap-10">
        {/* ── Order summary ── */}
        <div className="lg:pt-6">
          <p className="text-xs font-bold uppercase tracking-[0.08em] text-(--secondary)">
            Order summary
          </p>
          <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-white">
            {plan.displayName || plan.name} plan
          </h1>
          <div className="mt-3 flex items-end gap-1">
            <span className="text-4xl font-extrabold text-white">${plan.price}</span>
            <span className="mb-1 text-white/60">/ month</span>
          </div>
          {plan.description && (
            <p className="mt-3 max-w-md text-sm leading-6 text-white/70">{plan.description}</p>
          )}

          {features.length > 0 && (
            <ul className="mt-6 space-y-2.5">
              {features.map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-sm text-white/80">
                  <span
                    className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full"
                    style={{
                      background: "color-mix(in srgb, var(--secondary) 18%, transparent)",
                      color: "var(--secondary)",
                    }}
                  >
                    <Check size={12} strokeWidth={3} />
                  </span>
                  {f}
                </li>
              ))}
            </ul>
          )}

          <div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-white/50">
            <span className="inline-flex items-center gap-1.5"><Lock size={13} /> Encrypted &amp; secure</span>
            <span className="inline-flex items-center gap-1.5"><ShieldCheck size={13} /> Payments by Paddle</span>
            <span>Cancel anytime</span>
          </div>
        </div>

        {/* ── Payment ── */}
        <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5 shadow-2xl sm:p-6">
          <h2 className="text-lg font-bold text-white">Payment details</h2>
          <p className="mt-1 text-sm text-white/60">
            Your monitoring starts as soon as your payment is confirmed.
          </p>

          {/* Consent to immediate start */}
          <label className="mt-4 flex cursor-pointer items-start gap-2.5 rounded-xl border border-white/15 bg-white/[0.03] p-3 text-xs leading-relaxed text-white/70">
            <input
              type="checkbox"
              checked={consented}
              onChange={(e) => setConsented(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded accent-(--secondary)"
            />
            <span>
              I agree to the{" "}
              <a href="https://intelshift.ai/terms" target="_blank" rel="noreferrer" className="font-semibold text-(--secondary) underline">Terms</a>{" "}
              and{" "}
              <a href="https://intelshift.ai/refund" target="_blank" rel="noreferrer" className="font-semibold text-(--secondary) underline">Refund Policy</a>, and consent to
              the service starting immediately — I understand I then lose the
              14-day right of withdrawal and fees are non-refundable except where
              required by law.
            </span>
          </label>

          {/* Inline Paddle frame (dark) — mounts once consent is given */}
          <div className="mt-4 min-h-[360px]">
            {consented ? (
              <div className="paddle-checkout-frame" />
            ) : (
              <div className="flex min-h-[300px] items-center justify-center rounded-2xl border border-dashed border-white/15 px-6 text-center text-sm text-white/45">
                Tick the box above to load the secure payment form.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
