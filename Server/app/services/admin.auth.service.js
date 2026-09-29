import Admin from '../models/admin.js';

import { generateAccessToken, generateRefreshToken, verifyRefreshToken } from '../../utils/jwt.js';
import bcrypt from 'bcrypt';

const getRefreshCookieOptions = () => {
    return {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "strict",
        maxAge: 7 * 24 * 60 * 60 * 1000 // 7 days
    };
}


const login = async ({ email, password }) => {

    if(!email || !password) {
        throw new Error("Email and password are required");
    }

    const admin = await Admin.findOne({ email });

    if (!admin) {
        throw new Error("Admin not found");
    }

    
    const payload = { id: admin._id, email: admin.email };

    const accessToken = generateAccessToken(payload);
    const refreshToken = generateRefreshToken(payload);

    admin.refreshToken = refreshToken;
    await admin.save();

    return { accessToken, refreshToken, admin };
}   

export { login, getRefreshCookieOptions };