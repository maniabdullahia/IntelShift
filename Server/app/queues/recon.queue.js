import { Queue } from "bullmq";
import connection from "../config/redis.js";

// Breadth-only recon jobs (homepage + nav + collection index) — one per site,
// run before the user selects pages. Separate from the "analysis" queue, which
// does the deep per-page crawl for tracked pages only.
const reconQueue = new Queue("recon", {
  connection,
});

export default reconQueue;
