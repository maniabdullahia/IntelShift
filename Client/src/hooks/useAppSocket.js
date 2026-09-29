import { useEffect } from "react";
import useAuthStore from "../store/auth.store";

import {
  connectSocket,
  disconnectSocket,
  joinUserRoom,
} from "../socket/socketManager";

import { initializeSocketHandlers } from "../socket/handlers";

const useAppSocket = () => {
  const { hasHydrated, user } = useAuthStore();

  useEffect(() => {
    if (!hasHydrated || !user?.id) return;

    connectSocket();
    initializeSocketHandlers();
    joinUserRoom(user.id);

    return () => {
      disconnectSocket();
    };
  }, [hasHydrated, user?.id]);
};

export default useAppSocket;