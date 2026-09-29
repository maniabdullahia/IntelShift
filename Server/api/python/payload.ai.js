import pythonApi from "../python.api.js";

const buildAiPayload = async (comparisonData) => {
    try {
        const response = await pythonApi.post("/v1/build-ai-payload", { comparison: comparisonData });
        return response.data;
    } catch (error) {
        console.error("Error building AI payload:", error);
        throw error;
    }
}

const compareSitesAiPayload = async () => {
    try {
        const response = await pythonApi.get("/v1/compare-sites-ai-payload");
        return response.data;
    } catch (error) {
        console.error("Error fetching compare sites AI payload:", error);
        throw error;
    }
}

const compareSiteAiPayload = async (siteData) => {
    try {
        const response = await pythonApi.post("/v1/compare-one-ai-payload", { siteData });
        return response.data;
    } catch (error) {
        console.error("Error fetching compare site AI payload:", error);
        throw error;
    }
}

const buildOpenAiInsights = async (comparisonData) => {
    try {
        const response = await pythonApi.post("/v1/openai-insights-request", { 
            comparison: comparisonData,
            options: {
                "model": "gpt-4",
                "temperature": 0.7,
            }
        });
        return response.data;
    } catch (error) {
        console.error("Error building OpenAI insights:", error);
        throw error;
    }
}

export { buildAiPayload, compareSitesAiPayload, compareSiteAiPayload, buildOpenAiInsights };