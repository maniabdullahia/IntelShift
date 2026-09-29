import { verifyAccessToken } from "../../utils/jwt.js";

const authenticate = async (req, res, next) => {
    try {
        const authHeader = req.headers.authorization;

        if (!authHeader || !authHeader.startsWith("Bearer ")) {
            return res.status(401).json({ message: "Unauthorized" });
        }

        const token = authHeader.substring(7);

        const decoded = verifyAccessToken(token);

        req.user = decoded;
        next();

    } catch (error) {
        return res.status(401).json({ message: "Unauthorized Access" });
    }
};

export default authenticate;