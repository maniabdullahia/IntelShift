import initPaddle from "./paddle.config";

export const getPaddleInstance = async () => {
    const paddleInstance = await initPaddle();
    return paddleInstance;
};

const CHECKOUT_INTENT_KEY = "is_checkout_intent";

/**
 * Entry point used across the app (plan cards, Billing screen, Signup). Instead
 * of popping Paddle's overlay, we stash the chosen plan and route to our own
 * dark, OpenAI/Claude-style checkout page which embeds Paddle inline.
 *
 * Kept as the same signature so every existing call site works unchanged.
 */
export const getPaddleCheckout = async (priceId, planId, user, successUrl) => {
    try {
        sessionStorage.setItem(
            CHECKOUT_INTENT_KEY,
            JSON.stringify({ priceId, planId, successUrl: successUrl || "billing-success" })
        );
    } catch {
        // sessionStorage unavailable — fall through; the page redirects to /billing.
    }
    window.location.assign("/checkout");
};

/** Read (and optionally clear) the pending checkout intent on the /checkout page. */
export const readCheckoutIntent = () => {
    try {
        const raw = sessionStorage.getItem(CHECKOUT_INTENT_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
};

export const clearCheckoutIntent = () => {
    try {
        sessionStorage.removeItem(CHECKOUT_INTENT_KEY);
    } catch {
        /* no-op */
    }
};

/**
 * Open the Paddle checkout INLINE, rendered into our own page (frameTarget is the
 * class of the container div). Themed dark to match the brand panels. The
 * consent-to-immediate-start is captured on our page and passed through as
 * custom_data for the audit trail.
 *
 * @param {object} p
 * @param {string} p.priceId
 * @param {string} p.planId
 * @param {object} p.user       { id, email }
 * @param {string} p.successUrl relative path (e.g. "billing-success")
 * @param {string} p.consentAt  ISO timestamp of the immediate-start consent
 */
export const openInlineCheckout = async ({ priceId, planId, user, successUrl, consentAt }) => {
    const paddle = await getPaddleInstance();

    paddle.Checkout.open({
        items: [{ priceId, quantity: 1 }],
        ...(user?.email ? { customer: { email: user.email } } : {}),
        customData: {
            userId: user?.id,
            planId,
            consentToImmediateStart: "true",
            consentAt: consentAt || new Date().toISOString(),
        },
        settings: {
            displayMode: "inline",
            frameTarget: "paddle-checkout-frame",
            frameInitialHeight: 450,
            frameStyle:
                "width:100%; min-width:312px; background-color: transparent; border: none;",
            theme: "dark",
            successUrl: successUrl
                ? `${window.location.origin}/${successUrl}`
                : `${window.location.origin}/onboarding`,
        },
    });
};
