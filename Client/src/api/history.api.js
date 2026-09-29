import api from "./api";

/** Historical timeline for a competitor. Returns { tier, advanced, timeline, trend, locked }. */
export const getCompetitorHistory = async (competitorId) => {
  const res = await api.get(`/history/${competitorId}`);
  return res.data;
};
