import bcrypt from "bcrypt";

const SALT_ROUNDS = Number(process.env.BCRYPT_SALT_ROUNDS) || 10;

/* =========================
   PASSWORD
========================= */

export const hashPassword = async (password) => {
    if (!password) throw new Error("Password required");

    const salt = await bcrypt.genSalt(SALT_ROUNDS);
    return await bcrypt.hash(password, salt);
};

export const comparePassword = async (password, hashedPassword) => {
    if (!password || !hashedPassword) {
        throw new Error("Invalid input");
    }

    return await bcrypt.compare(password, hashedPassword);
};

/* =========================
   REFRESH TOKEN HASHING
========================= */

export const hashToken = async (token) => {
    if (!token) throw new Error("Token required");

    const salt = await bcrypt.genSalt(SALT_ROUNDS);
    return await bcrypt.hash(token, salt);
};

export const compareToken = async (token, hashedToken) => {
    if (!token || !hashedToken) {
        throw new Error("Invalid token comparison");
    }

    return await bcrypt.compare(token, hashedToken);
};