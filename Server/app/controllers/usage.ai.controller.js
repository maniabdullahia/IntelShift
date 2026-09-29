import { aiStats } from "../services/ai.service.js";


const getAIStats = async (req, res) => {
    try {
        const { stats, data } = await aiStats();
        res.json({ stats, data });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
}

export { getAIStats };