import User from "../models/user.js";

/**
 * Middleware to check if user account is active.
 * Allows "pending" status for onboarding flows, but blocks "suspended".
 */
const checkAccountActive = async (req, res, next) => {
    try {
        const user = await User.findById(req.user.id);

        if (!user) {
            return res.status(401).json({ message: "User not found" });
        }

        if (user.accountStatus === "suspended") {
            return res.status(403).json({ message: "Account is suspended" });
        }

        req.userAccount = user;
        next();
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

/**
 * Middleware to check if user account is fully active (not pending).
 * Use this for features that require a subscription/plan.
 */
const checkAccountFullyActive = async (req, res, next) => {
    try {
        const user = await User.findById(req.user.id);

        if (!user) {
            return res.status(401).json({ message: "User not found" });
        }

        if (user.accountStatus === "suspended") {
            return res.status(403).json({ message: "Account is suspended" });
        }

        if (user.accountStatus === "pending") {
            return res.status(402).json({
                message: "Account is pending activation. Please subscribe to a plan.",
            });
        }

        req.userAccount = user;
        next();
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

export { checkAccountActive, checkAccountFullyActive };
