import api from "./api";

const createFreeTrialSubscription = async (priceId, planId) => {
    try {
        const response = await api.post("/free-trial-subscription", {
            priceId,
            planId,
        });
        console.log("[ API ] Free trial subscription created:", response.data);
        return response.data;
    } catch (error) {
        console.error("Error creating free trial subscription:", error);
        throw error;
    }
}

export { createFreeTrialSubscription };