import { initializePaddle } from "@paddle/paddle-js";

let paddleInstance = null;

export const initPaddle = async () => {
    if (paddleInstance) return paddleInstance;

    // Environment is env-driven: set VITE_PADDLE_ENV=production in .env to go live,
    // leave unset (or "sandbox") for testing. No code change needed to switch.
    const environment = import.meta.env.VITE_PADDLE_ENV || "sandbox";
    const token = import.meta.env.VITE_PADDLE_CLIENT_TOKEN;

    // Fail loudly on a missing/placeholder token — otherwise Paddle.js just renders
    // "Something went wrong" with no hint why. The live token comes from Paddle →
    // Developer Tools → Authentication → Client-side tokens (starts with "live_"; a
    // sandbox token starts with "test_").
    if (!token || /^<|PASTE|_live_\.\.\.|your[-_ ]token/i.test(token)) {
        console.error(
            "[Paddle] VITE_PADDLE_CLIENT_TOKEN is missing or still a placeholder. " +
            "Paste your client-side token into Client/.env and restart the dev server."
        );
        throw new Error("Paddle client token not configured");
    }
    // Common mistake: pasting the SERVER API key (pdl_live_/pdl_sdbx_) into the
    // client token. Paddle.js needs a CLIENT-SIDE token (live_/test_), and shipping
    // an API key to the browser exposes a secret — refuse it.
    if (/^pdl_/i.test(token)) {
        console.error(
            "[Paddle] VITE_PADDLE_CLIENT_TOKEN looks like a SERVER API key (pdl_…). " +
            "That belongs in Server/.env only. Use the CLIENT-SIDE token (starts with " +
            "'live_' or 'test_') from Paddle → Developer Tools → Authentication → Client-side tokens."
        );
        throw new Error("Paddle client token is a server API key, not a client-side token");
    }
    if (environment === "production" && token.startsWith("test_")) {
        console.warn("[Paddle] VITE_PADDLE_ENV=production but the token is a sandbox (test_) token — they must match.");
    }
    if (environment === "sandbox" && token.startsWith("live_")) {
        console.warn("[Paddle] VITE_PADDLE_ENV=sandbox but the token is a live token — they must match.");
    }

    paddleInstance = await initializePaddle({
        environment,
        token,
        // Surface Paddle's REAL failure reason (price not found, domain not
        // approved, seller not verified, …) instead of the generic "Something went
        // wrong" shown inside the checkout frame.
        eventCallback: (ev) => {
            const name = ev?.name || ev?.type;
            if (name === "checkout.error") {
                console.error("[Paddle] checkout.error →", ev?.detail || ev?.error || ev);
            } else if (name === "checkout.warning") {
                console.warn("[Paddle] checkout.warning →", ev?.detail || ev);
            } else if (name) {
                console.debug("[Paddle] event:", name);
            }
        },
    });
    return paddleInstance;
};

export default initPaddle;