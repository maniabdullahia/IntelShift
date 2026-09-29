import useAppSocket from "./useAppSocket";

const useSocket = (workspaceId, userId, authHydrated = true) => {
	useAppSocket({
		authHydrated,
		userId,
		workspaceId,
	});
};

export default useSocket;