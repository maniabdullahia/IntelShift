import { createRedis } from "../app/config/redis.js"

const pub = createRedis("eventBus.publisher")

export const publishSocketEvent = async (event, data) => {
    await pub.publish("socket-events", JSON.stringify({event, data}))
}