// Load env BEFORE reading it. ESM evaluates this module's top-level code when it's
// first imported — which happens before index.js runs dotenv.config() — so without
// this the key check below fires against an unpopulated process.env and crashes the
// process with "PADDLE_API_KEY is missing" even when it's set in .env.
import "dotenv/config"
import { Paddle } from "@paddle/paddle-node-sdk"
if(!process.env.PADDLE_API_KEY) {
    throw new Error("PADDLE_API_KEY is missing");
}

const paddle = new Paddle({
    apiKey: process.env.PADDLE_API_KEY,
    options: {
        // Env-driven: sandbox only when the base URL points at Paddle's sandbox.
        // Live (https://api.paddle.com) → false, so a live key hits the live API.
        sandbox: (process.env.PADDLE_BASE_URL || "").includes("sandbox"),
    }
})

export default paddle;