// entitlement.service.js — single source of truth for "can this account make
// changes?". When a free trial ends (status still "trialing" but past trialEnd),
// the account becomes READ-ONLY: monitoring is already stopped by the scheduler,
// and mutations (workspace, competitors, alerts, pages) are refused here.

import Subscription from "../models/subscription.js";

/**
 * Derive entitlement from a subscription document.
 * @returns {{status, active, trialExpired, readOnly, trialEnd}}
 */
export const computeEntitlement = (sub) => {
    const status = sub?.status || null;
    const now = Date.now();
    const trialEndMs = sub?.trialEnd ? new Date(sub.trialEnd).getTime() : null;

    const trialExpired = status === "trialing" && trialEndMs != null && trialEndMs < now;
    const active = status === "active" || (status === "trialing" && !trialExpired);

    // Read-only when the trial has ended, or the account is canceled / has no
    // subscription. (past_due / paused are transient dunning states handled
    // elsewhere and are intentionally NOT hard-locked here.)
    const readOnly = trialExpired || status === "canceled" || !sub;

    return {
        status,
        active,
        trialExpired,
        readOnly,
        trialEnd: sub?.trialEnd || null,
    };
};

export const getEntitlement = async (userId) => {
    if (!userId) return computeEntitlement(null);
    const sub = await Subscription.findOne({ userId }).lean();
    return computeEntitlement(sub);
};

export default getEntitlement;
