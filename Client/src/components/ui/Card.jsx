import { Check } from "lucide-react";
import { useState } from "react";
import Button from "./Button";
import Alert from "../shared/Alert";
import useAuthStore from "../../store/auth.store";
import useModelStore from "../../store/model.store";
import { useLoaderData } from "react-router-dom";
import useWorkspaceStore from "../../store/workspace.store";

import { calculateDaysLeft } from "../../../utils/Time";

import { getPaddleCheckout } from "../../services/paddle/paddle.service";
import { scheduleDowngrade } from "../../api/downgrade.api";

const CADENCE_LABEL = {
  daily: "every day",
  "2d": "every 2 days",
  "3d": "every 3 days",
  weekly: "weekly",
  monthly: "monthly",
  once: "one-time",
};
const cadenceLabel = (c) => CADENCE_LABEL[String(c || "").toLowerCase()] || "on your plan's schedule";
const fmtDate = (d) =>
  d ? new Date(d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "your next renewal";

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

const esc = (s) => String(s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const Card = ({
  planType,
  price,
  limitations,
  isCurrent,
  planId: cardPlanId,
  description,
  buttonText = "Upgrade",
  onButtonClick,
  priceId,
}) => {
  const [isChangingPlan, setIsChangingPlan] = useState(false);
  const user = useAuthStore((state) => state.user);
  const changePlan = useAuthStore((state) => state.changePlan);
  const planId = useAuthStore((state) => state.user?.plan);
  const subscription = useAuthStore(
    (state) => state.user?.subscription,
  );

  const nextBilledAt = subscription?.nextBilledAt;
  const daysLeft = nextBilledAt ? calculateDaysLeft(nextBilledAt) : null;

  // A scheduled downgrade locks plan changes until it's applied or cancelled.
  const hasPendingDowngrade = !!subscription?.pendingDowngrade?.planId;

  const subscriptionId = subscription?.subscriptionId;
  const planLimit = useLoaderData();
  const workspace = useWorkspaceStore((state) => state.workspace);
  // Exclude competitors staged for removal — they'll be gone after the next run,
  // so they shouldn't count toward limits or appear in the downgrade selection.
  const filteredCompetitors = (workspace?.competitors || []).filter(
    (c) => c.role === "Competitor" && c.pendingChange !== "remove"
  );
  const currentCompetitorCount = filteredCompetitors.length;

  const openModel = useModelStore((state) => state.openModel);
  const targetPlan = planLimit?.find((plan) => plan._id === cardPlanId);

  const refreshUser = async () => {
    try { await useAuthStore.getState().syncUser?.(); } catch { /* ignore */ }
  };

  async function handlePlanChange(newPlanId, subscriptionId, priceId) {
    if (newPlanId === planId) return; // No change
    if (!subscriptionId) return console.error("No active subscription found for the user.");
    if (!priceId) return console.error("Price ID is required to change the plan.");
    await changePlan(newPlanId, subscriptionId, priceId);
  }

  // Upgrade → confirm the prorated charge + new limits, then apply immediately.
  async function confirmUpgrade() {
    const r = await Alert.fire({
      icon: "info",
      title: `Upgrade to ${planType}?`,
      html: `<div style="text-align:left;font-size:14px;line-height:1.6">
        <p>You'll be charged the <strong>prorated difference</strong> for the rest of this billing period, and your new limits apply <strong>immediately</strong>.</p>
        <ul style="margin:10px 0 0;padding-left:18px;color:#636e72">
          <li>Up to <strong>${targetPlan?.limits?.competitors ?? "—"}</strong> competitors</li>
          <li>Up to <strong>${targetPlan?.limits?.pagesPerCompetitor ?? "—"}</strong> pages per competitor</li>
          <li>Monitoring <strong>${cadenceLabel(targetPlan?.planReportingFrequency)}</strong></li>
        </ul></div>`,
      showCancelButton: true,
      confirmButtonText: `Upgrade — pay $${price}/mo`,
      cancelButtonText: "Cancel",
      confirmButtonColor: "#4ecdc4",
    });
    if (!r.isConfirmed) return;
    await handlePlanChange(cardPlanId, subscriptionId, priceId);
    await refreshUser();
    Alert.fire({ icon: "success", title: "You're on " + planType, text: "Your new limits are active.", timer: 2600, showConfirmButton: false });
  }

  // Downgrade → scheduled for renewal. Upfront, the user picks which competitors
  // to keep (if over that limit) and which pages to keep per competitor (if over
  // that limit). Anything not chosen is removed / auto-trimmed at the switch.
  async function handleDownGrade() {
    const competitorLimit = targetPlan?.limits?.competitors;
    const pageLimit = targetPlan?.limits?.pagesPerCompetitor;
    if (competitorLimit == null) return console.error("Target plan limits not found");

    const effective = fmtDate(nextBilledAt);
    const trackedPages = (c) =>
      (c.pages || []).filter((p) => p.pendingChange !== "remove" && !isHomepageUrl(p.url));

    const overComp = currentCompetitorCount > competitorLimit;
    const overPageComps = pageLimit != null
      ? filteredCompetitors.filter((c) => trackedPages(c).length > pageLimit)
      : [];

    // Nothing exceeds the new plan → simple confirm.
    if (!overComp && overPageComps.length === 0) {
      const r = await Alert.fire({
        icon: "warning",
        title: `Downgrade to ${planType}?`,
        html: `<div style="font-size:14px;line-height:1.6">
          <p>You'll keep your current plan until <strong>${effective}</strong>, then switch to ${planType}. <strong>No charge now.</strong></p>
        </div>`,
        showCancelButton: true,
        confirmButtonText: "Schedule downgrade",
        cancelButtonText: "Cancel",
        confirmButtonColor: "#fc5c65",
      });
      if (!r.isConfirmed) return;
      await scheduleDowngrade({ planId: cardPlanId, keepCompetitorIds: filteredCompetitors.map((c) => c._id) });
      await refreshUser();
      Alert.fire({ icon: "success", title: "Downgrade scheduled", text: `Takes effect on ${effective}. Cancel anytime before then.` });
      return;
    }

    // Build the upfront keep-selection.
    let html = `<div style="text-align:left;font-size:14px;line-height:1.6;max-height:52vh;overflow:auto">
      <p>You keep everything until <strong>${effective}</strong>, then switch to ${planType}. Choose what to keep within the new limits — the rest is removed then. If you skip this, we keep the most recent automatically.</p>`;

    if (overComp) {
      html += `<p style="margin-top:14px;font-weight:600">Competitors — keep up to ${competitorLimit}</p>`;
      html += filteredCompetitors
        .map((c, i) => `<label style="display:flex;gap:8px;align-items:center;padding:4px 0">
          <input type="checkbox" class="keep-comp" value="${c._id}" ${i < competitorLimit ? "checked" : ""}/> ${esc(c.name || c.domain)}${c.pendingChange === "add" ? ' <span style="color:#b88a00;font-size:11px">(pending)</span>' : ""}
        </label>`)
        .join("");
    }

    // Only ask about pages for competitors that will be KEPT. When over the
    // competitor limit, the first `competitorLimit` are kept by default; sections
    // show/hide live as the user changes the competitor selection (see didOpen).
    const initiallyKept = overComp
      ? new Set(filteredCompetitors.slice(0, competitorLimit).map((c) => String(c._id)))
      : new Set(filteredCompetitors.map((c) => String(c._id)));

    overPageComps.forEach((c) => {
      const pages = trackedPages(c);
      const shown = initiallyKept.has(String(c._id));
      html += `<div class="page-section" data-comp="${c._id}" style="display:${shown ? "block" : "none"}">`;
      html += `<p style="margin-top:14px;font-weight:600">${esc(c.name || c.domain)}${c.pendingChange === "add" ? ' <span style="color:#b88a00;font-size:11px">(pending)</span>' : ""} — keep up to ${pageLimit} page(s)</p>`;
      html += pages
        .map((p, i) => `<label style="display:flex;gap:8px;align-items:center;padding:3px 0;word-break:break-all">
          <input type="checkbox" class="keep-page" data-comp="${c._id}" value="${p._id}" ${i < pageLimit ? "checked" : ""}/>
          <span style="font-size:12px;color:#636e72">${esc(p.url)}</span>
        </label>`)
        .join("");
      html += `</div>`;
    });
    html += `</div>`;

    const r = await Alert.fire({
      title: `Downgrade to ${planType}`,
      html,
      showCancelButton: true,
      confirmButtonText: "Schedule downgrade",
      cancelButtonText: "Cancel",
      confirmButtonColor: "#fc5c65",
      didOpen: () => {
        if (!overComp) return; // all kept — every page section already visible
        // Show a competitor's page section only while it's checked to keep.
        const sync = () => {
          document.querySelectorAll(".keep-comp").forEach((cb) => {
            const sec = document.querySelector(`.page-section[data-comp="${cb.value}"]`);
            if (sec) sec.style.display = cb.checked ? "block" : "none";
          });
        };
        document.querySelectorAll(".keep-comp").forEach((cb) => cb.addEventListener("change", sync));
        sync();
      },
      preConfirm: () => {
        const keepCompetitorIds = overComp
          ? Array.from(document.querySelectorAll(".keep-comp:checked")).map((el) => el.value)
          : filteredCompetitors.map((c) => c._id);
        if (overComp && keepCompetitorIds.length > competitorLimit) {
          Alert.showValidationMessage(`Keep at most ${competitorLimit} competitor(s).`);
          return false;
        }
        const keepCompSet = new Set(keepCompetitorIds.map(String));
        // Only keep pages for competitors we're actually keeping.
        const keepPageIds = Array.from(document.querySelectorAll(".keep-page:checked"))
          .filter((el) => keepCompSet.has(el.getAttribute("data-comp")))
          .map((el) => el.value);
        for (const c of overPageComps) {
          if (!keepCompSet.has(String(c._id))) continue; // being removed — skip
          const chosen = Array.from(document.querySelectorAll(`.keep-page[data-comp="${c._id}"]:checked`)).length;
          if (chosen > pageLimit) {
            Alert.showValidationMessage(`Keep at most ${pageLimit} page(s) for ${c.name || c.domain}.`);
            return false;
          }
        }
        return { keepCompetitorIds, keepPageIds };
      },
    });
    if (!r.isConfirmed) return;
    await scheduleDowngrade({ planId: cardPlanId, keepCompetitorIds: r.value.keepCompetitorIds, keepPageIds: r.value.keepPageIds });
    await refreshUser();
    Alert.fire({ icon: "success", title: "Downgrade scheduled", text: `Takes effect on ${effective}. Cancel anytime before then.` });
  }

  async function handleSubscribe() {
    try {
      
      console.log("Initiating subscription process for priceId:", priceId, "and cardPlanId:", cardPlanId, "for user:", user );

      await getPaddleCheckout(priceId, cardPlanId, user, 'billing-success');
    } catch (error) {
      console.error("Error during subscription process:", error);
      openModel("error", {
        title: "Subscription Failed",
        text: "An error occurred while processing your subscription. Please try again.",
      });
      throw error;
    }
  }

 return (
  <div
    className={`relative flex h-full flex-col rounded-4xl border p-8 transition-all duration-300 hover:-translate-y-1 hover:shadow-(--shadow-lg)
      ${
        isCurrent
          ? "border-(--secondary) bg-[rgba(78,205,196,0.08)] shadow-[0_0_0_1px_var(--secondary),0_24px_64px_rgba(78,205,196,0.18)]"
          : planType === "Growth"
            ? "border-(--accent) bg-white shadow-[0_0_0_1px_var(--accent),0_24px_64px_rgba(255,107,107,0.15)]"
            : "border-(--border) bg-white"
      }`}
  >
    {isCurrent ? (
      <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-(--secondary) px-4 py-1 text-[11px] font-black uppercase tracking-[0.06em] text-(--primary)">
        Current Plan
      </div>
    ) : (
      planType === "Growth" && (
        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-(--accent) px-4 py-1 text-[11px] font-black uppercase tracking-[0.06em] text-white">
          Most Popular
        </div>
      )
    )}

    {/* Plan */}
    <div className="mb-2 text-[14px] font-extrabold uppercase tracking-[0.06em] text-(--text-light)">
      {planType}
    </div>

    {/* Price */}
    <div className="mb-1 flex items-end">
      <h1 className="text-[52px] leading-none font-black tracking-[-0.03em] text-(--primary) font-[Inter]">
        ${price}
      </h1>

      <span className="ml-1 mb-1 text-[15px] font-medium text-(--text-light)">
        /mo
      </span>
    </div>

    {/* Description */}
    <p className="mb-6 border-b border-(--border) pb-6 text-[14px] leading-[1.6] text-(--text-light)">
      {description}
    </p>

    {/* Features */}
    <ul className="mb-7 flex flex-1 flex-col gap-2.5">
      {limitations.map((limitation, index) => (
        <li
          key={index}
          className="flex items-start gap-2.5 text-[14px] text-(--text)"
        >
          <div className="mt-px flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded-full bg-[rgba(38,222,129,0.12)]">
            <Check size={10} className="text-(--success)" />
          </div>

          <span>{limitation}</span>
        </li>
      ))}
    </ul>

    {/* Button */}
    <div className="mt-auto">
      {isCurrent ? (
        <Button
          title="Current Plan"
          variant="secondary"
          disabled
          fullWidth
        />
      ) : hasPendingDowngrade ? (
        <div>
          <Button title="Change locked" variant="secondary" disabled fullWidth />
          <p className="mt-2 text-center text-xs text-(--text-light)">
            A downgrade is scheduled — cancel it to change plans.
          </p>
        </div>
      ) : (
        <Button
          title={buttonText}
          loading={isChangingPlan}
          fullWidth
          onClick={async () => {
            try {
              setIsChangingPlan(true);

              if (onButtonClick) {
                await onButtonClick(priceId, false);
              } else if (buttonText === "Subscribe") {
                await handleSubscribe();
              } else if (buttonText === "Downgrade") {
                await handleDownGrade();
              } else {
                // Upgrade — confirm the prorated charge + new limits first.
                await confirmUpgrade();
              }
            } finally {
              setIsChangingPlan(false);
            }
          }}
        />
      )}
    </div>
  </div>
);
};

export default Card;
