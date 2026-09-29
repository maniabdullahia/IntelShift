import api from "./api";

// Ask to close the account — triggers a confirmation email. Nothing changes yet.
export const requestAccountDeletion = async () => {
  const res = await api.post("/account/delete-request");
  return res.data;
};

// Confirm closure from the emailed link (token proves identity; no auth needed).
export const confirmAccountDeletion = async (token) => {
  const res = await api.post("/account/delete-confirm", { token });
  return res.data; // { confirmed, accessEndsAt, deleteAt }
};

// Cancel a pending closure and restore the account.
export const reactivateAccount = async () => {
  const res = await api.post("/account/reactivate");
  return res.data;
};
