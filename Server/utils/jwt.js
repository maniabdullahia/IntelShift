import jwt from "jsonwebtoken";

/* =========================
   ENV VALIDATION (SAFE)
========================= */

const getAccessSecret = () => {
    const secret = process.env.ACCESS_TOKEN_SECRET;
    if (!secret) throw new Error("ACCESS_TOKEN_SECRET missing");
    return secret;
};

const getRefreshSecret = () => {
    const secret = process.env.REFRESH_TOKEN_SECRET;
    if (!secret) throw new Error("REFRESH_TOKEN_SECRET missing");
    return secret;
};

/* =========================
   EXPIRY CONFIG
========================= */

const ACCESS_EXPIRY = process.env.ACCESS_TOKEN_EXPIRATION || "15m";
const REFRESH_EXPIRY = process.env.REFRESH_TOKEN_EXPIRATION || "7d";

/* =========================
   TOKEN GENERATION
========================= */

export const generateAccessToken = (payload) => {
    return jwt.sign(payload, getAccessSecret(), {
        expiresIn: ACCESS_EXPIRY,
    });
};

export const generateRefreshToken = (payload) => {
    return jwt.sign(payload, getRefreshSecret(), {
        expiresIn: REFRESH_EXPIRY,
    });
};

/* =========================
   TOKEN VERIFICATION
========================= */

export const verifyAccessToken = (token) => {
    return jwt.verify(token, getAccessSecret());
};

export const verifyRefreshToken = (token) => {
    return jwt.verify(token, getRefreshSecret());
};