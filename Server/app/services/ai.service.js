import { tryCatch } from "bullmq";
import AIUsage from "../models/aiUsage.js";

export const recordAIUsage = async (userId, tokens, cost, isValidJson = true, failureReason = "") => {
    try {
        const aiUsage = await AIUsage.findOne({ userId });
        if (!aiUsage) {
            const newUsage = new AIUsage({
                userId,
                totalTokens: tokens,
                cost,
                isValidJson,
                failure: failureReason ? 1 : 0,
                failureReason,
            });
            await newUsage.save();
        } else {
            aiUsage.totalTokens += tokens;
            aiUsage.cost += cost;
            aiUsage.isValidJson = isValidJson;
            if (failureReason) {
                aiUsage.failure += 1;
                aiUsage.failureReason = failureReason;
            }

            await aiUsage.save();
        }
    } catch (error) {
        console.error("Error recording AI usage:", error);
    }
}


export const aiStats = async () => {
    const response = await AIUsage.find().populate("userId", "name email").lean();

    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);

    // ---------------------------
    // BASIC STATS (single pass)
    // ---------------------------
    let totalTokens = 0;
    let totalCost = 0;
    let totalFailures = 0;
    let validJsonCount = 0;

    let todayTokens = 0;
    let todayCost = 0;

    for (const usage of response) {
        totalTokens += usage.totalTokens || 0;
        totalCost += usage.cost || 0;
        totalFailures += usage.failure || 0;

        if (usage.isValidJson) validJsonCount++;

        if (usage.createdAt >= todayStart) {
            todayTokens += usage.totalTokens || 0;
            todayCost += usage.cost || 0;
        }
    }

    const validJsonPercentage =
        response.length > 0
            ? (validJsonCount / response.length) * 100
            : 0;

    // ---------------------------
    // LAST 7 DAYS TIME SERIES
    // ---------------------------

    const last7DaysMap = new Map();

    // create last 7 days skeleton
    for (let i = 6; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        const key = date.toISOString().split("T")[0]; // YYYY-MM-DD

        last7DaysMap.set(key, {
            date: key,
            tokens: 0,
            cost: 0,
        });
    }

    // fill data
    for (const usage of response) {
        const dateKey = new Date(usage.createdAt)
            .toISOString()
            .split("T")[0];

        if (last7DaysMap.has(dateKey)) {
            const entry = last7DaysMap.get(dateKey);

            entry.tokens += usage.totalTokens || 0;
            entry.cost += usage.cost || 0;
        }
    }

    const last7DaysArray = Array.from(last7DaysMap.values());

    const stats = {
        totalTokens,
        totalCost,
        totalFailures,
        validJsonPercentage,
        todayTokens,
        todayCost,

        // 👇 PERFECT for Chart.js
        last7DaysChart: {
            labels: last7DaysArray.map(d => d.date),
            tokens: last7DaysArray.map(d => d.tokens),
            cost: last7DaysArray.map(d => d.cost),
        },
    };

    return { stats, data: response };
};