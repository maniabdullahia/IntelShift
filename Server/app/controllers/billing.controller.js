import { getSubscriptionByUserId } from "../services/subscription.service.js";
import { getManagementUrls, cancelAtPeriodEnd } from "../services/billing.service.js";

/*
|--------------------------------------------------------------------------
| BILLING ACTIONS (self-serve)
|--------------------------------------------------------------------------
| GET  /billing/management  -> payment-method URL + subscription status
| POST /billing/cancel      -> cancel at the end of the current period
|
| Refunds are intentionally NOT self-serve. Like most SaaS (OpenAI, Canva),
| fees are non-refundable except where required by law; any statutory or
| goodwill refund is issued manually via Paddle by an admin. Cancelling just
| stops the next renewal — the customer keeps access until the period ends.
*/

// GET /billing/management
const getBillingActions = async (req, res) => {
  try {
    const subscription = await getSubscriptionByUserId(req.user.id);
    if (!subscription || !subscription.subscriptionId) {
      // Trial/free users have no Paddle subscription to manage yet.
      return res.json({
        hasSubscription: false,
        updatePaymentMethodUrl: null,
        cancelAtPeriodEnd: false,
        status: subscription?.status || "trialing",
      });
    }

    // Paddle-hosted URLs are best-effort — never fail the whole call if Paddle
    // is briefly unreachable; the cancel/delete actions still work without them.
    let updatePaymentMethodUrl = null;
    try {
      const urls = await getManagementUrls(subscription.subscriptionId);
      updatePaymentMethodUrl = urls.updatePaymentMethod;
    } catch (e) {
      console.error("Paddle management URL fetch failed:", e.response?.data || e.message);
    }

    return res.json({
      hasSubscription: true,
      updatePaymentMethodUrl,
      cancelAtPeriodEnd: !!subscription.cancelAtPeriodEnd,
      periodEnd: subscription.currentPeriodEnd || subscription.nextBilledAt || null,
      status: subscription.status,
    });
  } catch (error) {
    console.error("getBillingActions failed:", error);
    return res.status(500).json({ message: error.message || "Failed to load billing actions" });
  }
};

// POST /billing/cancel
const cancelSubscription = async (req, res) => {
  try {
    const subscription = await getSubscriptionByUserId(req.user.id);
    if (!subscription || !subscription.subscriptionId) {
      return res.status(400).json({ message: "No active subscription to cancel." });
    }

    if (String(subscription.status).toLowerCase() === "canceled") {
      return res.status(400).json({ message: "This subscription is already canceled." });
    }

    // Always cancel at period end — the customer keeps what they paid for until
    // then. No automatic refund (that's handled manually where warranted).
    const result = await cancelAtPeriodEnd(subscription.subscriptionId);
    const effectiveAt =
      result?.scheduled_change?.effective_at ||
      subscription.currentPeriodEnd ||
      subscription.nextBilledAt ||
      null;

    return res.json({
      canceled: true,
      effective: "period_end",
      effectiveAt,
      message:
        "Your subscription is set to cancel at the end of your current billing period. You keep full access until then.",
    });
  } catch (error) {
    console.error("cancelSubscription failed:", error.response?.data || error);
    return res
      .status(500)
      .json({ message: error.response?.data?.error?.detail || error.message || "Failed to cancel subscription" });
  }
};

export { getBillingActions, cancelSubscription };
