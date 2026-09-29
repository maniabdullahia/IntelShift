import {
  requestAccountDeletion,
  confirmAccountDeletion,
  reactivateAccount,
} from "../services/account.service.js";

/*
|--------------------------------------------------------------------------
| ACCOUNT CLOSURE
|--------------------------------------------------------------------------
| Staged, reversible account deletion:
|   1) delete-request  → emails a confirmation link (nothing changes yet)
|   2) delete-confirm   → cancels billing at period end, keeps access until
|                         then, schedules a hard delete after a grace window
|   3) reactivate       → cancels the whole thing while it's still pending
*/

// POST /account/delete-request   (auth)
const deleteRequest = async (req, res) => {
  try {
    await requestAccountDeletion(req.user.id);
    return res.json({
      requested: true,
      message: "Check your email to confirm account closure.",
    });
  } catch (error) {
    console.error("Account delete request failed:", error);
    return res.status(500).json({ message: error.message || "Failed to start account closure" });
  }
};

// POST /account/delete-confirm   (public — token proves identity)
const deleteConfirm = async (req, res) => {
  try {
    const { token } = req.body;
    if (!token) return res.status(400).json({ message: "Confirmation token is required" });

    const result = await confirmAccountDeletion(token);
    return res.json({
      confirmed: true,
      accessEndsAt: result.accessEndsAt,
      deleteAt: result.deleteAt,
      message: "Your account is scheduled to close.",
    });
  } catch (error) {
    console.error("Account delete confirm failed:", error);
    const code = /invalid|expired/i.test(error.message || "") ? 400 : 500;
    return res.status(code).json({ message: error.message || "Failed to confirm account closure" });
  }
};

// POST /account/reactivate   (auth)
const reactivate = async (req, res) => {
  try {
    await reactivateAccount(req.user.id);
    return res.json({ reactivated: true, message: "Your account is active again." });
  } catch (error) {
    console.error("Account reactivate failed:", error);
    return res.status(500).json({ message: error.message || "Failed to reactivate account" });
  }
};

export { deleteRequest, deleteConfirm, reactivate };
