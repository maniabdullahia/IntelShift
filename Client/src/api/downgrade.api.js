import api from "./api";

/**
 * Schedule a downgrade to take effect at the next renewal.
 * @param {object} params
 * @param {string} params.planId  target plan id (or name)
 * @param {string[]} [params.keepCompetitorIds]  competitors to keep within the new limit
 */
export const scheduleDowngrade = async ({ planId, keepCompetitorIds = [], keepPageIds = [] }) => {
  const res = await api.post("/downgrade/schedule", { planId, keepCompetitorIds, keepPageIds });
  return res.data; // { scheduled, effectiveAt, keepCompetitorIds }
};

/** Cancel a scheduled downgrade before it takes effect. */
export const cancelDowngrade = async () => {
  const res = await api.post("/downgrade/cancel");
  return res.data;
};
