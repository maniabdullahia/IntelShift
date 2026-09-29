import useAuthStore from "../../../store/auth.store";
import useWorkspaceStore from "../../../store/workspace.store";

const onboardingLoader = async () => {
    const { syncUser } = useAuthStore.getState();
    const { syncWorkspace } = useWorkspaceStore.getState();

    await syncUser();
    await syncWorkspace();
    
}

export default onboardingLoader;