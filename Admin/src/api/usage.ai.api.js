import api from "./api";

export const getAIUsageStats = async () => {
    try {
        const response = await api.get("/admin/ai-usage");
        return response.data;
    } catch (error) {
        console.error("Error fetching AI usage stats:", error);
        throw error;
    }
}