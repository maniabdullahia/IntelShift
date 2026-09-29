import api from "./api";

const createCheckoutSession = async (priceId, isFreeTrial) => {
    try {
        const response = await api.post("/create-checkout-session", { priceId, isFreeTrial });
        return response.data;
    } catch (error) {
        console.error("Error creating checkout session:", error);
        throw error;
    }
};

export {
    createCheckoutSession,
};