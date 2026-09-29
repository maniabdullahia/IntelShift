import api from "./api";

/** Outstanding setup to-dos / gaps for the current workspace. */
export const getActionCenter = async () => {
  const res = await api.get("/action-center");
  return res.data; // { items: [...], count }
};
