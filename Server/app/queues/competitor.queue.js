import connection from "../config/redis.js";
import { Queue } from "bullmq";

const competitorQueue = new Queue("competitor", {
    connection,
});

export default competitorQueue;