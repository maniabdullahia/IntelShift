
import { recordAIUsage } from "../app/services/ai.service.js";

function isValidJson(jsonString) {
    try {
        JSON.parse(jsonString);
        return true;
    }
    catch (error) {
        return false;
    }
}

/**
 *
 * Generates AI stats based on the analysis result and records the usage.
 * @param {*} userId
 * @param {*} analysisResult
 */
async function generateAiStats(userId, analysisResult) {

    // The analyzers return null when a page overflows the model / can't be read.
    // Reading `.usage` off null used to THROW here, turning a soft analysis miss
    // into a hard job crash (and a retry storm that hung the workspace). Treat a
    // missing/failed result as a recorded failure instead of crashing.
    const tokensUsed = analysisResult?.usage?.total_tokens || 0;
    const stats = {
        tokensUsed,
        cost: (tokensUsed / 1000) * 0.002, // Assuming $0.002 per 1K tokens
        isValidJson: isValidJson(analysisResult?.output_text),
        failure: !analysisResult || analysisResult?.status === "failed" ? 1 : 0,
    };

    await recordAIUsage(userId, stats.tokensUsed, stats.cost, stats.isValidJson, stats.failure);
}

export { generateAiStats };