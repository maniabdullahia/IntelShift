import User from "../models/user.js";
import Plan from "../models/plan.js";
import Subscription from "../models/subscription.js";

import jwt from "jsonwebtoken"

import {
    hashPassword,
    comparePassword,
    hashToken,
    compareToken,
} from "../../utils/bcrypt.js";

import {
    generateAccessToken,
    generateRefreshToken,
    verifyRefreshToken,
} from "../../utils/jwt.js";

import {
    sendPasswordResetMail,
    sendEmailVerificationMail,
    sendWelcomeMail
} from "./email.service.js";



// Fallback limits used only when a plan document can't be read. Kept IN SYNC
// with plan.seeder.js (the real source of truth) so no code path grants a
// different limit than the DB plan does.
const PLAN_DEFAULTS = {
    trial: {
        competitors: 1,
        pagesPerCompetitor: 10,
        reportFrequency: "weekly",
    },
    starter: {
        competitors: 2,
        pagesPerCompetitor: 20,
        reportFrequency: "3D",
    },
    growth: {
        competitors: 5,
        pagesPerCompetitor: 50,
        reportFrequency: "daily",
    },
    pro: {
        competitors: 10,
        pagesPerCompetitor: 150,
        reportFrequency: "daily",
    },
};

const PLAN_FEATURE_DEFAULTS = {
    alerts: false,
    aiInsights: false,
    exports: false,
};

const capitalize = (value) => value ? value.charAt(0).toUpperCase() + value.slice(1) : value;

// =========================
// COOKIE OPTIONS
// =========================

const getRefreshCookieOptions = () => {
    const isProduction = process.env.NODE_ENV === "production";

    return {
        httpOnly: true,
        secure: isProduction,
        sameSite: isProduction ? "none" : "lax",
        maxAge: 7 * 24 * 60 * 60 * 1000,
        path: "/",
    };
};

const buildPlanSnapshot = (planName, planDoc = null) => {
    // If no plan is set, return null
    if (!planName) {
        return null;
    }

    const defaults = PLAN_DEFAULTS[planName] || PLAN_DEFAULTS.trial;

    if (!planDoc) {
        return {
            name: planName,
            displayName: capitalize(planName),
            stripePriceId: null,
            limits: { ...defaults },
            features: { ...PLAN_FEATURE_DEFAULTS },
            isActive: planName === "trial",
        };
    }

    return {
        name: planDoc.name,
        displayName: planDoc.displayName || capitalize(planDoc.name),
        stripePriceId: planDoc.stripePriceId || null,
        limits: {
            competitors: planDoc.limits?.competitors ?? defaults.competitors,
            pagesPerCompetitor: planDoc.limits?.pagesPerCompetitor ?? defaults.pagesPerCompetitor,
            reportFrequency: planDoc.limits?.reportFrequency ?? defaults.reportFrequency,
        },
        features: {
            alerts: planDoc.features?.alerts ?? PLAN_FEATURE_DEFAULTS.alerts,
            aiInsights: planDoc.features?.aiInsights ?? PLAN_FEATURE_DEFAULTS.aiInsights,
            exports: planDoc.features?.exports ?? PLAN_FEATURE_DEFAULTS.exports,
        },
        isActive: planDoc.isActive ?? true,
    };
};

const findPlan = async (planName) => {
    if (planName === "trial") {
        return Plan.findOne({ name: planName }).lean();
    }

    const plan = await Plan.findOne({ name: planName }).lean();

    if (!plan || plan.isActive === false) {
        throw new Error("Selected plan is not available");
    }

    return plan;
};

const getUserPlanState = async (user) => {
    const subscription = await Subscription.findOne({ userId: user._id })
        .sort({ createdAt: -1 })
        .lean();

    const planName = subscription?.plan || user.plan;
    const planDoc = await Plan.findOne({ name: planName }).lean();
    const planSnapshot = buildPlanSnapshot(planName, planDoc);

    const subscriptionState = subscription
        ? {
            id: subscription._id.toString(),
            userId: subscription.userId.toString(),
            stripeCustomerId: subscription.stripeCustomerId,
            stripeSubscriptionId: subscription.stripeSubscriptionId,
            stripePriceId: subscription.stripePriceId,
            plan: subscription.plan,
            status: subscription.status,
            currentPeriodStart: subscription.currentPeriodStart,
            currentPeriodEnd: subscription.currentPeriodEnd,
            cancelAtPeriodEnd: subscription.cancelAtPeriodEnd,
            canceledAt: subscription.canceledAt,
            trialStart: subscription.trialStart,
            trialEnd: subscription.trialEnd,
            metadata: subscription.metadata,
            // The client reads plan limits/name from subscription.planId — attach the
            // resolved plan snapshot so limits (e.g. pagesPerCompetitor) reach the UI
            // instead of falling back to a hard-coded default.
            planId: planSnapshot,
        }
        : null;

    return {
        plan: planSnapshot,
        subscription: subscriptionState,
    };
};

const buildAuthUser = async (user) => {
    const plainUser = user.toObject ? user.toObject() : { ...user };

    delete plainUser.password;
    delete plainUser.refreshToken;
    delete plainUser.emailVerificationToken;
    delete plainUser.emailVerificationExpires;
    delete plainUser.passwordResetToken;
    delete plainUser.passwordResetExpires;
    delete plainUser.__v;

    const planState = await getUserPlanState(user);

    return {
        ...plainUser,
        ...planState,
    };
};



// =========================
// REGISTER SERVICE
// =========================

const register = async ({ name, email, password, provider, socialSub, role = "user", planId, isEmailVerified, profilePicture }) => {
    if (!email) {
        throw new Error("Email required");
    }

    const exists = await User.findOne({ email });

    if (exists) {
        // Social sign-up is idempotent. A previous attempt may have created the
        // account and then failed later in the flow, or the person may simply
        // have signed up before — either way, log them in instead of erroring
        // with "Email already exists".
        const isSocial = provider && provider !== "local";
        if (isSocial) {
            // Backfill the social identity if a prior partial signup didn't
            // persist it, so the socialLogin lookup (by socialSub) succeeds.
            if (socialSub && exists.socialSub !== socialSub) {
                exists.socialSub = socialSub;
                if (!exists.provider || exists.provider === "local") exists.provider = provider;
                await exists.save();
            }
            return await socialLogin({ email, socialSub: socialSub || exists.socialSub });
        }
        throw new Error("Email already exists");
    }

    const hashedPassword = password ? (await hashPassword(password)) : '';

    const user = await User.create({
        name,
        email,
        password: hashedPassword,
        role,
        provider: provider,
        socialSub: socialSub ? socialSub : null,
        // Google/Facebook supply an avatar URL in the OIDC `picture` claim.
        profilePicture: typeof profilePicture === "string" ? profilePicture : "",
        accountStatus: "pending",
        isEmailVerified: isEmailVerified || false,
    });

    const payload = {
        id: user._id,
        email: user.email,
        role: user.role,
    };

    const accessToken = generateAccessToken(payload);
    const refreshToken = generateRefreshToken(payload);

    user.refreshToken = await hashToken(refreshToken);
    await user.save();

    // Google/Facebook have already verified the email address, so there's nothing
    // for the user to confirm — mark it verified and send a welcome email instead
    // of a verification link.
    const isSocial = provider && provider !== "local";

    if (isSocial) {
        user.isEmailVerified = true;
        await user.save();

        await sendWelcomeMail(user.email, user.name).catch((e) =>
            console.error("Welcome mail failed:", e.message)
        );
    } else {
        const emailVerificationToken = jwt.sign(
            {
                userId: user._id,
                type: "email-verification"
            },
            process.env.ACCESS_TOKEN_SECRET,
            {
                expiresIn: "3h"
            }
        );

        const emailVerificationTokenHashed = await hashToken(emailVerificationToken);
        const emailVerificationExpires = new Date(Date.now() + 3 * 60 * 60 * 1000);
        const emailVerificationLink = `${process.env.CLIENT_URL}/verify-email/${emailVerificationToken}`;

        user.emailVerificationToken = emailVerificationTokenHashed;
        user.emailVerificationExpires = emailVerificationExpires;
        await user.save();

        await sendEmailVerificationMail(user.email, user.name, emailVerificationLink, "3 hours");
    }

    // Build the returned user AFTER the verify/welcome branch so it reflects the
    // final state (social accounts come back already verified).
    const authUser = await buildAuthUser(user);

    return {
        user: authUser,
        accessToken,
        refreshToken
    };
};



// =========================
// LOGIN SERVICE EMAIL/PASSWORD
// =========================

const login = async ({ email, password }) => {
    const user = await User.findOne({ email }).select("+password +refreshToken");

    if (!user) {
        throw new Error("User does not exist");
    }

    if (user.accountStatus === "suspended") {
        throw new Error("Account is suspended");
    }

    if (user.isSuspended) {
        throw new Error("Account is suspended");
    }

    if (user.accountStatus === "deactivated" || user.deletion?.status === "deactivated") {
        throw new Error("This account has been deactivated as part of account closure. Contact support to restore it.");
    }

    if (typeof user.isLocked === "function" && user.isLocked()) {
        throw new Error("Account is locked");
    }

    const isMatch = await comparePassword(password, user.password);

    if (!isMatch) {
        throw new Error("Invalid credentials");
    }

    const payload = {
        id: user._id,
        email: user.email,
        role: user.role,
    };

    const accessToken = generateAccessToken(payload);
    const refreshToken = generateRefreshToken(payload);

    user.refreshToken = await hashToken(refreshToken);
    user.lastLoginAt = new Date();
    await user.save();

    return {
        user: await buildAuthUser(user),
        accessToken,
        refreshToken,
    };
};

// =========================
// LOGIN SERVICE EMAIL/PASSWORD
// =========================

const socialLogin = async ({ email, socialSub }) => {
    const user = await User.findOne({ socialSub }).select("+socialSub +refreshToken");

    if (!user) {
        throw new Error("User does not exist");
    }

    if (user.accountStatus === "suspended") {
        throw new Error("Account is suspended");
    }

    if (user.isSuspended) {
        throw new Error("Account is suspended");
    }

    if (user.accountStatus === "deactivated" || user.deletion?.status === "deactivated") {
        throw new Error("This account has been deactivated as part of account closure. Contact support to restore it.");
    }

    if (typeof user.isLocked === "function" && user.isLocked()) {
        throw new Error("Account is locked");
    }

    const isMatch = (socialSub === user.socialSub)

    if (!isMatch) {
        throw new Error("Invalid credentials");
    }

    const payload = {
        id: user._id,
        email: user.email,
        role: user.role,
    };

    const accessToken = generateAccessToken(payload);
    const refreshToken = generateRefreshToken(payload);

    user.refreshToken = await hashToken(refreshToken);
    user.lastLoginAt = new Date();
    await user.save();

    return {
        user: await buildAuthUser(user),
        accessToken,
        refreshToken,
    };
};




// =========================
// REFRESH TOKEN SERVICE
// =========================

const refreshAccessToken = async ({ token }) => {
    if (!token) {
        throw new Error("No refresh token");
    }

    const decoded = verifyRefreshToken(token);

    const user = await User.findById(decoded.id).select("+refreshToken");

    if (!user) {
        throw new Error("User not found");
    }

    if (!user.refreshToken) {
        throw new Error("Invalid refresh token");
    }

    const isValid = await compareToken(token, user.refreshToken);

    if (!isValid) {
        throw new Error("Invalid refresh token");
    }

    const payload = {
        id: user._id,
        email: user.email,
        role: user.role,
    };

    const newAccessToken = generateAccessToken(payload);
    const newRefreshToken = generateRefreshToken(payload);

    user.refreshToken = await hashToken(newRefreshToken);
    await user.save();

    return {
        accessToken: newAccessToken,
        refreshToken: newRefreshToken,
        user: await buildAuthUser(user),
    };
};


// ================================
// CREATE ACCOUNT USING THIRD PARTY 
// ================================

const createSocialAccount = async ({ token }) => {

}



// =========================
// LOGOUT SERVICE
// =========================

const logout = async ({ userId, token }) => {
    let resolvedUserId = userId;

    if (!resolvedUserId && token) {
        try {
            const decoded = verifyRefreshToken(token);
            resolvedUserId = decoded.id;
        } catch {
            resolvedUserId = null;
        }
    }

    const user = resolvedUserId ? await User.findById(resolvedUserId).select("+refreshToken") : null;

    if (user) {
        user.refreshToken = null;
        await user.save();
    }

    return true;
};


// =========================
// FORGET PASSWORD
// =========================

const forgetPassword = async (email) => {

    if (!email) {
        throw new Error("Email required")
    }

    const user = await User.findOne({ email })

    if (!user) {
        throw new Error("User does not exist")
    }

    if (user.provider && user.provider !== "local") {
        throw new Error(`Password reset is not available for ${user.provider} accounts. Your account is registered via ${user.provider}. Please use the ${user.provider} login method to access your account.`)
    }

    const token = jwt.sign(
        {
            userId: user._id,
            type: "password-reset"
        },
        process.env.ACCESS_TOKEN_SECRET,
        {
            expiresIn: "3h"
        }
    )

    user.passwordResetToken = await hashToken(token)
    user.passwordResetExpires = new Date(Date.now() + 3 * 60 * 60 * 1000)
    await user.save()

    const url = `${process.env.CLIENT_URL}/reset-password/${token}`

    await sendPasswordResetMail(email, url)
}

// =========================
// RESET PASSWORD
// =========================

const resetPassword = async (token, newPassword) => {

    if (!token || !newPassword) {
        throw new Error("Token and new password are required");
    }

    let decoded;

    try {
        decoded = jwt.verify(token, process.env.ACCESS_TOKEN_SECRET);
    } catch (error) {
        throw new Error("Invalid or expired token");
    }
    


    if (decoded.type !== "password-reset") {
        throw new Error("Invalid token type");
    }



    const user = await User.findById(decoded.userId).select(
        "+password +passwordResetToken +passwordResetExpires"
    );

    if (!user) {
        throw new Error("User does not exist");
    }

    // The reset link may already have been used (token cleared after a
    // successful reset) or belong to an account with none pending.
    if (!user.passwordResetToken) {
        throw new Error("This reset link is no longer valid. Please request a new one.");
    }

    const isTokenValid = await compareToken(token, user.passwordResetToken);

    if (!isTokenValid) {
        throw new Error("Invalid or expired token");
    }

    const hashedPassword = await hashPassword(newPassword);
    user.password = hashedPassword;
    user.passwordResetToken = null;
    user.passwordResetExpires = null;
    await user.save();
}

// =========================
// RESET PASSWORD
// =========================

const verifyEmail = async (token) => {
    if (!token) {
        throw new Error("Token is required");
    }

    let decoded;

    try {
        decoded = jwt.verify(token, process.env.ACCESS_TOKEN_SECRET);
    }
    catch (error) {
        throw new Error("Invalid or expired token");
    }

    if (decoded.type !== "email-verification") {
        throw new Error("Invalid token type");
    }

    const user = await User.findById(decoded.userId);

    if (!user) {
        throw new Error("User does not exist");
    }

    user.isEmailVerified = true;
    user.emailVerificationToken = null;
    user.emailVerificationExpires = null;
    await user.save();
}

const sendEmailVerification = async (email) => {
    const user = await User.findOne({ email }).select("+emailVerificationToken +emailVerificationExpires");

    if (!user) {
        throw new Error("User does not exist");
    }

    const token = jwt.sign(
        {
            userId: user._id,
            type: "email-verification"
        },
        process.env.ACCESS_TOKEN_SECRET,
        {
            expiresIn: "3h"
        }
    );

    const emailVerificationTokenHashed = await hashToken(token);
    const emailVerificationExpires = new Date(Date.now() + 3 * 60 * 60 * 1000);
    const emailVerificationLink = `${process.env.CLIENT_URL}/verify-email/${token}`;

    user.emailVerificationToken = emailVerificationTokenHashed;
    user.emailVerificationExpires = emailVerificationExpires;
    await user.save();

    await sendEmailVerificationMail(user.email, user.name, emailVerificationLink, "3 hours");
}


// =========================
// EXPORT
// =========================

export const authService = {
    register,
    login,
    forgetPassword,
    socialLogin,
    refreshAccessToken,
    resetPassword,
    verifyEmail,
    sendEmailVerification,
    logout,
    getRefreshCookieOptions,
};