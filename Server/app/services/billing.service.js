import paddleApi from "../../api/paddle.api.js";
import Subscription from "../models/subscription.js";

/*
|--------------------------------------------------------------------------
| BILLING SERVICE
|--------------------------------------------------------------------------
| Self-serve billing actions that talk to Paddle (Merchant of Record):
|   • update payment method  -> Paddle-hosted page (we never touch card data)
|   • cancel at period end    -> keeps access until the paid period runs out
|   • cancel + 14-day refund  -> first-time subscribers, within the window
|
| Paddle is the seller of record, so refunds are requested as "adjustments"
| and may be created pending Paddle's approval.
*/

// Statutory-style money-back window for a customer's first paid subscription.
export const REFUND_WINDOW_DAYS = 14;
const DAY_MS = 86400000;

/**
 * Fetch Paddle's hosted management URLs for a subscription — notably the
 * update-payment-method page and Paddle's own cancel page.
 * @returns {{ updatePaymentMethod: string|null, cancel: string|null }}
 */
export const getManagementUrls = async (subscriptionId) => {
    if (!subscriptionId) return { updatePaymentMethod: null, cancel: null };
    const res = await paddleApi.get(`/subscriptions/${subscriptionId}`);
    const urls = res?.data?.data?.management_urls || {};
    return {
        updatePaymentMethod: urls.update_payment_method || null,
        cancel: urls.cancel || null,
    };
};

/**
 * Is this subscription still inside its first-time-subscriber money-back window?
 * Eligible when: it has a first-billing stamp, hasn't already been refunded,
 * is currently paid-current, and we're within REFUND_WINDOW_DAYS of that stamp.
 * @returns {{ eligible: boolean, daysLeft: number, deadline: Date|null }}
 */
export const getRefundEligibility = (subscription) => {
    const first = subscription?.firstBilledAt ? new Date(subscription.firstBilledAt) : null;
    const status = String(subscription?.status || "").toLowerCase();
    const paidCurrent = status === "active" || status === "trialing";

    if (!first || subscription?.refundedAt || !paidCurrent) {
        return { eligible: false, daysLeft: 0, deadline: null };
    }

    const deadline = new Date(first.getTime() + REFUND_WINDOW_DAYS * DAY_MS);
    const msLeft = deadline.getTime() - Date.now();
    return {
        eligible: msLeft > 0,
        daysLeft: Math.max(0, Math.ceil(msLeft / DAY_MS)),
        deadline,
    };
};

/**
 * Cancel at the end of the current billing period. The customer keeps full
 * access to everything they've paid for until then; Paddle fires
 * `subscription.canceled` at period end, which stops monitoring.
 */
export const cancelAtPeriodEnd = async (subscriptionId) => {
    const res = await paddleApi.post(`/subscriptions/${subscriptionId}/cancel`, {
        effective_from: "next_billing_period",
    });
    // Reflect the scheduled cancellation locally so the UI can show it at once.
    await Subscription.findOneAndUpdate(
        { subscriptionId },
        { $set: { cancelAtPeriodEnd: true } }
    );
    return res?.data?.data || null;
};

/**
 * Full refund of a transaction via a Paddle adjustment. Reads the transaction's
 * line items and refunds each in full. Paddle may hold the adjustment for
 * approval since Paddle is the merchant of record.
 */
const refundTransactionFully = async (transactionId, reason) => {
    if (!transactionId) throw new Error("No transaction to refund");

    const txnRes = await paddleApi.get(`/transactions/${transactionId}`);
    const lineItems = txnRes?.data?.data?.details?.line_items || [];
    if (!lineItems.length) throw new Error("Transaction has no line items to refund");

    const items = lineItems.map((li) => ({ item_id: li.id, type: "full" }));

    const adjRes = await paddleApi.post(`/adjustments`, {
        action: "refund",
        transaction_id: transactionId,
        reason: reason || "14-day money-back guarantee",
        items,
    });
    return adjRes?.data?.data || null;
};

/**
 * Immediate cancellation plus a full refund — used only when the subscription
 * is inside its first-time 14-day window. Access stops now, money is returned.
 */
export const cancelImmediatelyWithRefund = async (subscription) => {
    const subscriptionId = subscription.subscriptionId;

    // Refund first; if the refund request fails we don't want to have already
    // killed their access with nothing back.
    const adjustment = await refundTransactionFully(
        subscription.transactionId,
        "14-day money-back guarantee (first-time subscriber)"
    );

    await paddleApi.post(`/subscriptions/${subscriptionId}/cancel`, {
        effective_from: "immediately",
    });

    await Subscription.findOneAndUpdate(
        { subscriptionId },
        { $set: { refundedAt: new Date(), cancelAtPeriodEnd: false } }
    );

    return { adjustment };
};
