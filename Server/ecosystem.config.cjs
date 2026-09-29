// PM2 process config.
//
// Secrets are NO LONGER hardcoded here — they're read from Server/.env via
// process.env, so `.env` is the single source of truth. Rotate a key in .env and
// both `node bootstrap.js` and PM2 pick it up. This file is safe to commit.
//
// (dotenv is loaded here so process.env is populated when PM2 evaluates this
// config; __dirname keeps it working regardless of the cwd PM2 starts from.)
require("dotenv").config({ path: require("path").join(__dirname, ".env") });

// Secrets — sourced from .env. Defined once, reused across the server + workers.
const SECRETS = {
  MONGO_URI: process.env.MONGO_URI,
  ACCESS_TOKEN_SECRET: process.env.ACCESS_TOKEN_SECRET,
  REFRESH_TOKEN_SECRET: process.env.REFRESH_TOKEN_SECRET,
  OPENAI_API_KEY: process.env.OPENAI_API_KEY,
  ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY,
};

module.exports = {
  apps: [
    /**
     * ====================
     * MAIN SERVER
     * ====================
     */
    {
      name: "server",
      script: "./bootstrap.js",
      exec_mode: "fork",
      instances: 1,
      watch: false,

      ignore_watch: [
        "node_modules",
        "logs",
        ".git",
        "public/data",
      ],
      env: {
        NODE_ENV: "development",
        PORT: 5000,
        ...SECRETS,
        ACCESS_TOKEN_EXPIRATION: "15m",
        REFRESH_TOKEN_EXPIRATION: "7d",
        BCRYPT_SALT_ROUNDS: 10,
        CORS_ORIGIN: "http://63.250.47.15",
        CORS_METHODS: "GET,POST,PUT,DELETE",
        CORS_CREDENTIALS: true,
        PADDLE_BASE_URL: process.env.PADDLE_BASE_URL || "https://sandbox-api.paddle.com", // switch to https://api.paddle.com for production
        PADDLE_API_KEY: process.env.PADDLE_API_KEY,
        PADDLE_WEBHOOK_SECRET: process.env.PADDLE_WEBHOOK_SECRET,
        CLIENT_URL: "https://app.intelshift.ai",
        AUTH0_BASE_URL: process.env.AUTH0_BASE_URL || "https://dev-sjvba6ygwr3raznj.us.auth0.com",
        AUTH0_CLIENT_ID: process.env.AUTH0_CLIENT_ID,
        AUTH0_SECRET: process.env.AUTH0_SECRET,
        BASE_URL: "https://api.intelshift.ai",
        RESEND_API_KEY: process.env.RESEND_API_KEY,
        EMAIL_DOMAIN: "mail.intelshift.ai",
        EMAIL_LOGO_URL: process.env.EMAIL_LOGO_URL || "https://intelshift.ai/logo.png",
        PYTHON_SERVER_URL: "/python",
      },
      env_production: {
        NODE_ENV: "production",
      },
      log_file: "./logs/server.log",
      error_file: "./logs/server-error.log",
      out_file: "./logs/server-out.log",
    },

    /**
     * ====================
     * WORKERS
     * ====================
     */

    /**
     * Alert Worker
     * Handles alert processing and notifications
     */
    {
      name: "alert-worker",
      script: "./app/workers/alert.worker.js",
      instances: 1,
      exec_mode: "fork",
      watch: ["app/workers/alert.worker.js"],
      ignore_watch: ["node_modules", "logs"],
      env: {
        NODE_ENV: "development",
        ...SECRETS,
        BCRYPT_SALT_ROUNDS: 10,
        PYTHON_SERVER_URL: "http://localhost:8000/api",
      },
      env_production: {
        NODE_ENV: "production",
      },
      log_file: "./logs/alert-worker.log",
      error_file: "./logs/alert-worker-error.log",
      out_file: "./logs/alert-worker-out.log",
    },

    /**
     * Analysis Worker
     * Handles data analysis and processing
     */
    {
      name: "analysis-worker",
      script: "./app/workers/analysis.worker.js",
      instances: 1,
      exec_mode: "fork",
      watch: ["app/workers/analysis.worker.js"],
      ignore_watch: ["node_modules", "logs"],
      env: {
        NODE_ENV: "development",
        ...SECRETS,
        BCRYPT_SALT_ROUNDS: 10,
        PYTHON_SERVER_URL: "http://localhost:8000/api",
      },
      env_production: {
        NODE_ENV: "production",
      },
      log_file: "./logs/analysis-worker.log",
      error_file: "./logs/analysis-worker-error.log",
      out_file: "./logs/analysis-worker-out.log",
    },

    /**
     * Competitor Worker
     * Handles competitor data collection and updates
     */
    {
      name: "competitor-worker",
      script: "./app/workers/competitor.worker.js",
      instances: 1,
      exec_mode: "fork",
      watch: ["app/workers/competitor.worker.js"],
      ignore_watch: ["node_modules", "logs"],
      env: {
        NODE_ENV: "development",
        ...SECRETS,
        BCRYPT_SALT_ROUNDS: 10,
        PYTHON_SERVER_URL: "http://localhost:8000/api",
      },
      env_production: {
        NODE_ENV: "production",
      },
      log_file: "./logs/competitor-worker.log",
      error_file: "./logs/competitor-worker-error.log",
      out_file: "./logs/competitor-worker-out.log",
    },

    /**
     * Workspace Worker
     * Handles workspace-related background tasks
     */
    {
      name: "workspace-worker",
      script: "./app/workers/workspace.worker.js",
      instances: 1,
      exec_mode: "fork",
      watch: ["app/workers/workspace.worker.js"],
      ignore_watch: ["node_modules", "logs"],
      env: {
        NODE_ENV: "development",
        ...SECRETS,
        BCRYPT_SALT_ROUNDS: 10,
        PYTHON_SERVER_URL: "http://localhost:8000/api",
      },
      env_production: {
        NODE_ENV: "production",
      },
      log_file: "./logs/workspace-worker.log",
      error_file: "./logs/workspace-worker-error.log",
      out_file: "./logs/workspace-worker-out.log",
    },
  ],

  /**
   * ====================
   * GLOBAL SETTINGS
   * ====================
   */
  deploy: {
    production: {
      user: "node",
      host: "63.250.47.15",
      ref: "origin/main",
      repo: "https://github.com/Techosols/Compintel",
      path: "/var/www/compintel-server",
      "post-deploy": "npm install && npm run build && pm2 restart ecosystem.config.js --env production",
    },
  },
};
