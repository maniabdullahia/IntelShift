

import { auth } from "express-openid-connect";
import { authService } from "../services/auth.service.js";
import { getPlanPriceId } from "../services/plan.service.js";

const resolveStatusCode = (error) => {
    const message = error?.message || "";

    if (
        message.includes("required") ||
        message.includes("already exists") ||
        message.includes("Invalid credentials") ||
        message.includes("Selected plan is not available")
    ) {
        return 400;
    }

    if (message.includes("No refresh token")) {
        return 401;
    }

    if (message.includes("Invalid refresh token") || message.includes("User not found") || message.includes("User does not exist")) {
        return 403;
    }

    return 500;
};

/* =========================
   REGISTER
========================= */

const register = async (req, res) => {
    try {
        const result = await authService.register(req.body);

        res.cookie("refreshToken", result.refreshToken, authService.getRefreshCookieOptions());

        if(!req.body.planId) {
            return res.status(201).json({
                message: "User registered successfully",
                user: result.user,
                accessToken: result.accessToken,
            });
        }

        // The account is already created at this point. Never let a plan-price
        // lookup failure turn a successful signup into an error (which would
        // leave an orphaned account the user can't get back into). Degrade
        // gracefully: log them in without a priceId — they can pick a plan next.
        let priceId = null;
        try {
            priceId = await getPlanPriceId(req.body.planId);
        } catch (planErr) {
            console.error("Plan price lookup failed after registration:", planErr.message);
        }

        return res.status(201).json({
            message: "User registered successfully",
            user: result.user,
            accessToken: result.accessToken,
            priceId: priceId,
            planId: req.body.planId,
        });
    } catch (error) {
        console.log('Registration Failed => ', error)
        return res.status(resolveStatusCode(error)).json({ message: error.message || "Register error" });
    }
};

/* =========================
   LOGIN
========================= */

const login = async (req, res) => {
    try {

        const { isSocial } = req.body;

        let result;
        // const result = await authService.login(req.body);

        if (isSocial) {
            result = await authService.socialLogin(req.body);
        } else {
            result = await authService.login(req.body)
        }

        res.cookie("refreshToken", result.refreshToken, authService.getRefreshCookieOptions());

        return res.status(200).json({
            accessToken: result.accessToken,
            user: result.user,
        });
    } catch (error) {
        console.error("Login error:", error);
        return res.status(resolveStatusCode(error)).json({ message: error.message || "Login error" });
    }
};


/* =========================
   SOCIAL LOGIN
========================= */

const socialLogin = async (req, res) => {
    try {
        const result = await authService.socialLogin(req.body);

        res.cookie("refreshToken", result.refreshToken, authService.getRefreshCookieOptions());

        return res.status(200).json({
            accessToken: result.accessToken,
            user: result.user,
        });
    } catch (error) {
        console.error("Login error:", error);
        return res.status(resolveStatusCode(error)).json({ message: error.message || "Login error" });
    }
};

/* =========================
   REFRESH TOKEN
========================= */

const refreshToken = async (req, res) => {
    try {
        const token = req.cookies?.refreshToken;
        const result = await authService.refreshAccessToken({ token });

        res.cookie("refreshToken", result.refreshToken, authService.getRefreshCookieOptions());

        return res.status(200).json({
            accessToken: result.accessToken,
            user: result.user,
        });
    } catch (error) {
        return res.status(resolveStatusCode(error)).json({ message: error.message || "Refresh error" });
    }
};

/* =========================
   LOGOUT
========================= */

const logout = async (req, res) => {
    try {
        await authService.logout({
            token: req.cookies?.refreshToken,
        });

        res.clearCookie("refreshToken", {
            ...authService.getRefreshCookieOptions(),
            maxAge: undefined,
        });

        return res.status(200).json({
            message: "Logged out successfully",
        });
    } catch (error) {
        return res.status(resolveStatusCode(error)).json({ message: error.message || "Logout error" });
    }
};

/* =========================
   FORGET PASSWORD
========================= */

const forgetPassword = async (req, res) => {
    const { email } = req.body

    if (!email) {
        res.status(400).json({ message: "Email Required" })
    }

    try {
        const result = await authService.forgetPassword(email)
        res.status(200).json({
            message: "Password reset link sent successfully",
            result
        })
    } catch (error) {
        return res.status(resolveStatusCode(error)).json({ message: error.message || "Forget Password error" });
    }
}

/* =========================
   RESET PASSWORD
========================= */

const resetPassword = async (req, res) => {
    const { token, newPassword } = req.body;

    if (!token || !newPassword) {
        return res.status(400).json({ message: "Token and new password are required" });
    }

    try {
        const result = await authService.resetPassword(token, newPassword);
        return res.status(200).json({
            message: "Password reset successfully",
            result
        });
    }
    catch (error) {
        return res.status(resolveStatusCode(error)).json({ message: error.message || "Reset Password error" });
    }
};

/* =========================
   VERIFY EMAIL
========================= */

const verifyEmail = async (req, res) => {
    const { token } = req.body;

    if (!token) {
        return res.status(400).json({ message: "Token is required" });
    }

    try {
        const result = await authService.verifyEmail(token);
        return res.status(200).json({
            message: "Email verified successfully",
            result
        });
    } catch (error) {
        return res.status(resolveStatusCode(error)).json({ message: error.message || "Email verification error" });
    }
}

/* =========================
   SEND EMAIL VERIFICATION LINK
========================= */

const sendEmailVerificationLink = async (req, res) => {
    const { email } = req.body;


    if (!email) {
        return res.status(400).json({ message: "Email is required" });
    }


    try {
        const result = await authService.sendEmailVerification(email);
        return res.status(200).json({
            message: "Email verification link sent successfully",
            result
        });
    } catch (error) {
        console.error("Send email verification link error:", error);
        return res.status(resolveStatusCode(error)).json({ message: error.message || "Send email verification link error" });
    }
}


export {
    register,
    login,
    refreshToken,
    resetPassword,
    forgetPassword,
    verifyEmail,
    sendEmailVerificationLink,
    logout,
};