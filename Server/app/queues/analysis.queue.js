import { Queue } from "bullmq";
import connection from "../config/redis.js";

const analysisQueue = new Queue("analysis", {
  connection,
});

export default analysisQueue;