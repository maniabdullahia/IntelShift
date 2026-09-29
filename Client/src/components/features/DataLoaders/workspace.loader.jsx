import useWorkspaceStore from "../../../store/workspace.store";

const WorkspaceLoader = async () => {
    const { syncWorkspace } = useWorkspaceStore.getState();

    return await syncWorkspace();
};

export default WorkspaceLoader;