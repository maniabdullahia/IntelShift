import api from "./api";

/**
 * Billing actions status: Paddle-hosted payment-method URL, whether the account
 * is still inside its 14-day money-back window, and any scheduled cancellation.
 * @returns {Promise<{
 *   hasSubscription: boolean,
 *   updatePaymentMethodUrl: string|null,
 *   refund: { eligible: boolean, daysLeft: number, deadline?: string, windowDays: number },
 *   cancelAtPeriodEnd: boolean,
 *   periodEnd?: string|null,
 *   status: string,
 * }>}
 */
export const getBillingActions = async () => {
  const res = await api.get("/billing/management");
  return res.data;
};

/**
 * Cancel / unsubscribe. The server decides the outcome: a full refund + immediate
 * stop if within the 14-day first-timer window, otherwise cancel at period end.
 * @returns {Promise<{ canceled: boolean, refunded: boolean, effective: 'immediate'|'period_end', effectiveAt?: string, message: string }>}
 */
export const cancelSubscription = async () => {
  const res = await api.post("/billing/cancel");
  return res.data;
};
