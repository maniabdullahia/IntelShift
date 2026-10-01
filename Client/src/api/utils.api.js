import api from "./api";

const createTreeNode = async (url) => {
    const response = await api.post("/url-tree", { url });
    return response.data;
}

const validatePageUrl = async (url) => {
    const response = await api.post("/validate-url", { url });
    return response.data;
};

// Detect regional storefronts / currencies for a competitor URL, so the user can
// confirm which store + currency to track (store_locale_v1).
const detectStores = async (url) => {
    const response = await api.post("/detect-stores", { url });
    return response.data;
};

// Suggest direct competitors for the user's store (LLM + verification). Pass
// `categories` (array or comma string) to target specific product categories
// instead of auto-detection — used by the "target specific categories" control.
const suggestCompetitors = async (url, industry, pages = [], currency = "", categories = []) => {
    const response = await api.post("/suggest-competitors", { url, industry, pages, currency, categories });
    return response.data;
};

// Onboarding readiness check — confirms we can actually read the site (homepage +
// a collection + a product) before it's confirmed. Slow (can render JS sites in a
// real browser), so no timeout override here (the shared client has none).
const validateSite = async (url) => {
    const response = await api.post("/validate-site", { url });
    return response.data;
};

// Suggest product-to-product matches within a mapped collection pair. Local
// AI picks the like-for-like matches (Growth / Pro; server-enforced). The UI
// shows accept/reject — nothing is auto-asserted. Returns { suggestions, source, count }.
const productMatches = async (userProducts = [], competitorProducts = [], useAi = true) => {
    const response = await api.post("/product-matches", { userProducts, competitorProducts, useAi });
    return response.data;
};

// Saved accept / reject decisions: { "<category>|<userUrl>|<competitorUrl>": "accepted"|"rejected" }.
const getProductMatchDecisions = async () => {
    const response = await api.get("/product-matches/decisions");
    return response.data?.decisions || {};
};
const saveProductMatchDecisions = async (decisions) => {
    const response = await api.post("/product-matches/decisions", { decisions });
    return response.data?.decisions || {};
};

export {
    createTreeNode,
    validatePageUrl,
    detectStores,
    suggestCompetitors,
    validateSite,
    productMatches,
    getProductMatchDecisions,
    saveProductMatchDecisions,
};