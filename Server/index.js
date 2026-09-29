// import dotenv from "dotenv";
// dotenv.config({
//   path: process.env.NODE_ENV === "production" ? ".env.production" : ".env.development",
//   quiet: true,
// });

import express from "express";
import cors from "cors";
import cookieParser from "cookie-parser";
import http from "http";
import { auth } from "express-openid-connect"

import connectDB from "./app/config/database.js";
import router from "./app/routes/routes.js";
import adminRouter from "./app/routes/admin.routes.js";
import initializeSocket from "./app/socket/socket.js";
import initializeAppListeners from "./app/listners/index.js";
import handlePaddleWebhook from "./app/webhooks/paddle/paddle.webhook.js";
import { startEventRouter } from "./utils/eventRouter.js";
import "./app/Queues Events/index.js";
import seedAll from "./app/seeder/seeder.js";
import { startWorkspaceScheduler } from "./app/scheduler/workspace.scheduler.js";

// import "./bootstrap.js";

const PORT = process.env.PORT || 5000;

const app = express();

/* =========================
   CORS
========================= */
app.use(
  cors({
    origin: [
      "https://intelshift.ai",
      "https://app.intelshift.ai",
      "https://admin.intelshift.ai",
      "http://localhost:5173",
      "http://localhost:5174",
    ],
    credentials: true,
    methods: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allowedHeaders: ["Content-Type", "Authorization"],
  })
);

// Handle preflight requests
app.options(/.*/, cors());

app.post(
  "/webhooks/paddle",
  express.raw({ type: "application/json" }),
  handlePaddleWebhook
);

/* =========================
   NORMAL BODY PARSERS
   (AFTER WEBHOOK ONLY)
========================= */
// Raised from the 100kb default so base64 profile-picture uploads (capped at
// 2MB client-side → ~2.7MB encoded) fit in the request body.
app.use(express.json({ limit: "5mb" }));
app.use(express.urlencoded({ extended: true, limit: "5mb" }));
app.use(cookieParser());

app.use(express.static("public"));

/* =========================
   REQUEST LOGGER (SAFE)
========================= */
app.use((req, res, next) => {
  const start = Date.now();

  console.log("Request Body:", req.body);

  res.on("finish", () => {
    const duration = Date.now() - start;

    console.log(`${req.method} ${req.originalUrl} - ${res.statusCode} (${duration}ms)`);
  });

  next();
});

app.use(
  auth({
    authRequired: false, // set to true to require authentication for all routes
    auth0Logout: true,
    secret: process.env.AUTH0_SECRET,
    baseURL: process.env.BASE_URL,
    clientID: process.env.AUTH0_CLIENT_ID,
    issuerBaseURL: process.env.AUTH0_BASE_URL,
  })
);

/* =========================
   ROUTES
========================= */
app.get("/", (req, res) => {
  res.json({ message: "IntelShift API!" });
});

app.use("/api/admin", adminRouter);
app.use("/api", router);

/* =========================
   ERROR HANDLER
========================= */
app.use((err, req, res, next) => {
  console.error("Global Error Handler:", err);
  res.status(500).json({ message: "Internal Server Error" });
});

/* =========================
   HTTP SERVER
========================= */
const server = http.createServer(app);

/* =========================
   START SERVER
========================= */
const startServer = async () => {
  try {
    await connectDB();

    initializeAppListeners();
    initializeSocket(server);
    startEventRouter();
    startWorkspaceScheduler();

    server.on("error", (err) => {
      if (err.code === "EADDRINUSE") {
        console.error(
          `\n❌ Port ${PORT} is already in use — another server instance is still running.\n` +
          `   Kill it, then restart:\n` +
          `     Windows (PowerShell): Get-Process -Id (Get-NetTCPConnection -LocalPort ${PORT}).OwningProcess | Stop-Process -Force\n` +
          `     Windows (cmd):        netstat -ano | findstr :${PORT}   then   taskkill /F /PID <pid>\n` +
          `     macOS / Linux:        lsof -ti:${PORT} | xargs kill -9\n`
        );
      } else {
        console.error("Server error:", err);
      }
      process.exit(1);
    });

    server.listen(PORT, "0.0.0.0", () => {
      console.log(`Server running on http://localhost:${PORT}`);
    });

    await seedAll();

  } catch (error) {
    console.error("Failed to start server:", error);
    process.exit(1);
  }
};

startServer();

// Graceful shutdown so nodemon restarts (and Ctrl-C) release port 3000 cleanly,
// instead of leaving a zombie that causes EADDRINUSE on the next start.
const shutdown = (signal) => {
  console.log(`\n${signal} received — shutting down…`);
  server.close(() => process.exit(0));
  // Force-exit if connections keep it open too long.
  setTimeout(() => process.exit(0), 5000).unref();
};
process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));