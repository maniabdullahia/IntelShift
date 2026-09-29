import Logger from "./utils/logger.js";
import dotenv from "dotenv";
import dns from "dns";

// Load environment variables first
dotenv.config({
//   path:
//     process.env.NODE_ENV === "production"
//       ? ".env.production"
//       : ".env.development",
  quiet: true,
});

// Initialize globals
const logger = new Logger({
  logToFile: false,
  filePath: "app.log",
});

global.Log = logger;

// Optional DNS configuration
// dns.setDefaultResultOrder("ipv4first");

// Start the application
await import("./index.js");