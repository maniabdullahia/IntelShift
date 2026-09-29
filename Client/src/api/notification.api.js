import api from "./api";

export const getNotifications = async () => {
  const res = await api.get("/notifications");
  return res.data; // { notifications: [...], unread: n }
};

export const markNotificationsRead = async (id) => {
  const res = await api.put("/notifications/read", id ? { id } : {});
  return res.data;
};
