// PM2 process config.
//
// Secrets are NOT hardcoded here — they're read from Server/.env via
// process.env, so `.env` is the single source of truth. This file is safe to
// commit. Start everything with:
//
//     pm2 start ecosystem.config.cjs --env production
//
// (dotenv is loaded here so process.env is populated when PM2 evaluates this
// config; __dirname keeps it working regardless of the cwd PM2 starts from.)
require("dotenv").config({ path: require("path").join(__dirname, ".env") });

// Every process (API + workers) calls the Python service, so they all get the
// SAME absolute URL. It must include the /api prefix (the Node client calls
// paths like /v1/analyze-page).
const PYTHON_SERVER_URL = process.env.PYTHON_SERVER_URL || "http://127.0.0.1:8000/api";

// Shared by the API server and all workers.
const SHARED = {
  MONGO_URI: process.env.MONGO_URI,
  REDIS_HOST: process.env.REDIS_HOST || "127.0.0.1",
  REDIS_PORT: process.env.REDIS_PORT || 6379,
  REDIS_PASSWORD: process.env.REDIS_PASSWORD,
  ACCESS_TOKEN_SECRET: process.env.ACCESS_TOKEN_SECRET,
  REFRESH_TOKEN_SECRET: process.env.REFRESH_TOKEN_SECRET,
  OPENAI_API_KEY: process.env.OPENAI_API_KEY,
  ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY,
  AI_PROVIDER: process.env.AI_PROVIDER,
  PYTHON_SERVER_URL,
  PYTHON_API_KEY: process.env.PYTHON_API_KEY,
  BCRYPT_SALT_ROUNDS: 10,
};

// The API server runs bootstrap.js (it sets up the global logger). Workers are
// plain node entry points; each loads .env itself. `node` (not tsx) — the code
// is plain ESM JavaScript, and tsx is only a dev dependency.
const worker = (name, script, extra = {}) => ({
  name,
  script,
  interpreter: "node",
  instances: 1,
  exec_mode: "fork",
  watch: false,
  env: { NODE_ENV: "development", ...SHARED, ...extra },
  env_production: { NODE_ENV: "production" },
  log_file: `./logs/${name}.log`,
  error_file: `./logs/${name}-error.log`,
  out_file: `./logs/${name}-out.log`,
  // A worker that dies is restarted, but not in a tight crash loop.
  max_restarts: 20,
  min_uptime: "30s",
  restart_delay: 5000,
});

module.exports = {
  apps: [
    {
      ...worker("server", "./bootstrap.js", {
        PORT: process.env.PORT || 5000,
        ACCESS_TOKEN_EXPIRATION: process.env.ACCESS_TOKEN_EXPIRATION || "15m",
        REFRESH_TOKEN_EXPIRATION: process.env.REFRESH_TOKEN_EXPIRATION || "7d",
        TRUST_PROXY: process.env.TRUST_PROXY || "1",
        PADDLE_BASE_URL: process.env.PADDLE_BASE_URL || "https://sandbox-api.paddle.com", // https://api.paddle.com for production
        PADDLE_API_KEY: process.env.PADDLE_API_KEY,
        PADDLE_WEBHOOK_SECRET: process.env.PADDLE_WEBHOOK_SECRET,
        PADDLE_PRICE_STARTER: process.env.PADDLE_PRICE_STARTER,
        PADDLE_PRICE_GROWTH: process.env.PADDLE_PRICE_GROWTH,
        PADDLE_PRICE_PRO: process.env.PADDLE_PRICE_PRO,
        CLIENT_URL: process.env.CLIENT_URL || "https://app.intelshift.ai",
        AUTH0_BASE_URL: process.env.AUTH0_BASE_URL,
        AUTH0_CLIENT_ID: process.env.AUTH0_CLIENT_ID,
        AUTH0_SECRET: process.env.AUTH0_SECRET,
        BASE_URL: process.env.BASE_URL || "https://api.intelshift.ai",
        RESEND_API_KEY: process.env.RESEND_API_KEY,
        EMAIL_DOMAIN: process.env.EMAIL_DOMAIN || "mail.intelshift.ai",
        EMAIL_LOGO_URL: process.env.EMAIL_LOGO_URL || "https://intelshift.ai/logo.png",
        SEARCH_PROVIDER: process.env.SEARCH_PROVIDER,
        SEARXNG_URL: process.env.SEARXNG_URL,
        BRAVE_API_KEY: process.env.BRAVE_API_KEY,
      }),
      ignore_watch: ["node_modules", "logs", ".git", "public/data"],
    },

    // Recon: breadth-only capture of each store during capture-first onboarding.
    // Without it, onboarding sits in "recon" forever.
    worker("recon-worker", "./app/workers/recon.worker.js", {
      SEARCH_PROVIDER: process.env.SEARCH_PROVIDER,
      SEARXNG_URL: process.env.SEARXNG_URL,
      BRAVE_API_KEY: process.env.BRAVE_API_KEY,
    }),
    worker("analysis-worker", "./app/workers/analysis.worker.js"),
    worker("competitor-worker", "./app/workers/competitor.worker.js"),
    worker("workspace-worker", "./app/workers/workspace.worker.js"),
    worker("alert-worker", "./app/workers/alert.worker.js", {
      RESEND_API_KEY: process.env.RESEND_API_KEY,
      EMAIL_DOMAIN: process.env.EMAIL_DOMAIN || "mail.intelshift.ai",
      CLIENT_URL: process.env.CLIENT_URL || "https://app.intelshift.ai",
    }),
  ],
};
