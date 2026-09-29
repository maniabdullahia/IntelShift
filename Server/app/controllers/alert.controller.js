import User from "../models/user.js";
import Workspace from "../models/workspace.js";
import Notification from "../models/notification.js";
import { sendChangeAlertMail } from "../services/email.service.js";

/*
|--------------------------------------------------------------------------
| SEND TEST ALERT
|--------------------------------------------------------------------------
| Fires a sample change-alert email + in-app notification to the logged-in
| user, so email delivery (Resend + sending domain) can be verified on demand
| without waiting for a real monitoring change.
*/
const sendTestAlert = async (req, res) => {
    try {
        const user = await User.findById(req.user.id);
        if (!user) return res.status(404).json({ message: "User not found" });
        if (!user.email) return res.status(400).json({ message: "No email on file" });

        const workspace = await Workspace.findOne({ ownerId: user._id });

        const items = [
            {
                domain: "example-competitor.com",
                totalChanges: 3,
                severity: "high",
                changeScore: 72,
                topChanges: ["Price dropped 12% on a top product", "New product added to the catalog"],
            },
        ];

        // Respect the email channel preference (defaults on).
        if (user.settings?.notifications?.email !== false) {
            await sendChangeAlertMail(
                user.email,
                user.name,
                workspace?.name,
                items,
                `${process.env.CLIENT_URL || ""}/dashboard`
            );
        }

        await Notification.create({
            userId: user._id,
            type: "change_alert",
            title: "Test alert",
            body: "This is a sample change alert — your alerts are set up correctly.",
            link: "/dashboard",
        });

        return res.json({ sent: true, email: user.email });
    } catch (error) {
        console.error("Test alert failed:", error);
        return res.status(500).json({ message: error.message || "Failed to send test alert" });
    }
};

export { sendTestAlert };
