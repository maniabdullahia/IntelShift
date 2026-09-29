
import { login, getRefreshCookieOptions } from "../services/admin.auth.service.js";

const adminLogin = async (req, res) => {
    try {
        const { email, password } = req.body;

        const { accessToken, refreshToken, admin } = await login({ email, password });

        res.cookie("refreshToken", refreshToken, getRefreshCookieOptions());

        res.status(200).json({ accessToken, admin });
    } catch (error) {
        console.error("Error during admin login:", error);
        res.status(500).json({ message: error.message });
    }
}

export { adminLogin };