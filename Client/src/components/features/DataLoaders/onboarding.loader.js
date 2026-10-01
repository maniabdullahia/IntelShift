import useAuthStore from "../../../store/auth.store";
import useWorkspaceStore from "../../../store/workspace.store";

// Best-effort refresh of user + workspace before onboarding renders. A failure
// (logged out, API briefly down) must not replace the page with the router's
// "Unexpected Application Error" screen — ProtectedRoute handles the auth
// redirect, and onboarding renders from whatever is already in the stores.
const onboardingLoader = async () => {
    const { syncUser } = useAuthStore.getState();
    const { syncWorkspace } = useWorkspaceStore.getState();

    try {
        await syncUser();
        await syncWorkspace();
    } catch (err) {
        console.warn("onboarding loader: sync failed (continuing):", err?.message || err);
    }
    return null;
};

export default onboardingLoader;
