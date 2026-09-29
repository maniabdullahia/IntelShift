// entitlement.middleware.js — refuse mutating requests when the account is
// read-only (ended trial / canceled). The backstop behind the UI: even if a button
// isn't disabled, the API rejects the change with a clear, machine-readable reason
// the client can turn into an "Upgrade to continue" prompt.

import { getEntitlement } from "../services/entitlement.service.js";

export const blockReadOnly = async (req, res, next) => {
    try {
        const userId = req.user?.id;
        if (!userId) return res.status(401).json({ message: "Unauthorized" });

        const ent = await getEntitlement(userId);
        if (ent.readOnly) {
            return res.status(403).json({
                code: "READ_ONLY",
                reason: ent.trialExpired ? "trial_expired" : "inactive",
                message: ent.trialExpired
                    ? "Your free trial has ended. Upgrade to make changes and resume monitoring."
                    : "Your subscription is inactive. Upgrade to make changes.",
            });
        }
        next();
    } catch (err) {
        next(err);
    }
};

export default blockReadOnly;
