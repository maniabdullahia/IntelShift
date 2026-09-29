import { verifyAccessToken } from "../../utils/jwt.js";
import Admin from "../models/admin.js";

const adminAuthenticate = async (req, res, next) => {
    try {
        const authHeader = req.headers.authorization;

        if (!authHeader || !authHeader.startsWith("Bearer ")) {
            return res.status(401).json({ message: "Unauthorized" });
        }

        const token = authHeader.substring(7);

        const decoded = verifyAccessToken(token);

        const admin = await Admin.findById(decoded.id);

        if (!admin) {
            return res.status(401).json({ message: "Unauthorized" });
        }
        next();
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
}

export default adminAuthenticate;