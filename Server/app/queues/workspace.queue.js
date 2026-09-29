import { Queue } from 'bullmq';
import connection from "../config/redis.js";

const workspaceQueue = new Queue('workspace', {
    connection,
});

export default workspaceQueue;