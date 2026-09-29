import Notification from "../models/notification.js";

const getNotifications = async (req, res) => {
    try {
        const userId = req.user.id;
        const notifications = await Notification.find({ userId })
            .sort({ createdAt: -1 })
            .limit(30)
            .lean();
        const unread = await Notification.countDocuments({ userId, read: false });
        res.json({ notifications, unread });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

const markNotificationsRead = async (req, res) => {
    try {
        const userId = req.user.id;
        const { id } = req.body || {};
        if (id) {
            await Notification.updateOne({ _id: id, userId }, { $set: { read: true } });
        } else {
            await Notification.updateMany({ userId, read: false }, { $set: { read: true } });
        }
        res.json({ message: "ok" });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

export { getNotifications, markNotificationsRead };
