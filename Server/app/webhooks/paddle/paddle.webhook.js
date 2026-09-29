import paddle from "../../services/paddle.service.js";
import processEvent from "./handlers/index.js";
import WebhookEvent from "../../models/webhookEvent.js";

const handlePaddleWebhook = async (req, res) => {
    const signature = req.headers["paddle-signature"];
    const webhookSecret = process.env.PADDLE_WEBHOOK_SECRET;

    if (!signature || !webhookSecret) {
        console.error("Missing Paddle webhook signature or secret");

        return res.status(400).json({
            message: "Bad Request",
        });
    }

    try {
        const rawRequestBody = req.body.toString();

        const isValidSignature =
            await paddle.webhooks.isSignatureValid(
                rawRequestBody,
                webhookSecret,
                signature
            );

        if (!isValidSignature) {
            console.error("Invalid Paddle webhook signature");

            return res.status(400).json({
                message: "Invalid signature",
            });
        }

        const event = JSON.parse(rawRequestBody);

        const eventId = event.event_id;
        const eventType = event.event_type;

        /*
         * Atomic duplicate prevention
         * Prevents race conditions when Paddle retries quickly
         */
        const result = await WebhookEvent.updateOne(
            { eventId },
            {
                $setOnInsert: {
                    eventId,
                    eventType,
                    processedAt: new Date(),
                },
            },
            {
                upsert: true,
            }
        );

        /*
         * If matchedCount > 0
         * event already existed
         */
        if (result.matchedCount > 0) {
            // console.log(
            //     "Duplicate Paddle webhook ignored:",
            //     eventType,
            //     `[${event.data?.id || "unknown"}]`
            // );

            return res.status(200).json({
                success: true,
                message: "Duplicate event ignored",
            });
        }

        await processEvent(event);

        return res.status(200).json({
            success: true,
            received: true,
        });

    } catch (error) {

        /*
         * Duplicate key fallback protection
         */
        if (error.code === 11000) {
            console.log("Duplicate webhook event detected");

            return res.status(200).json({
                success: true,
                message: "Duplicate webhook ignored",
            });
        }

        console.error("Error processing Paddle webhook:", error);

        return res.status(500).json({
            success: false,
            message: "Internal Server Error",
        });
    }
};

export default handlePaddleWebhook;