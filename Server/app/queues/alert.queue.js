import { Queue } from "bullmq";
import connection from "../config/redis.js";

const alertQueue = new Queue("alert", {
  connection,
});

export default alertQueue;
