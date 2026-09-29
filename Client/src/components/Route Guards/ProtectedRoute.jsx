import { Navigate } from "react-router-dom";
import { useEffect } from "react";

import useAuthStore from "../../store/auth.store";
import useBootstrapStore from "../../store/bootstrap.store";

import FreshDataSync from "../features/Loadings/FreshDataSync";
import useAppSocket from "../../hooks/useAppSocket";

import Spinner from "../features/Loadings/Spinner";
import PremiumLoader from "../features/Loadings/PremiumLoader";

import Loader from "../../assets/loader.svg";

const ProtectedRoute = ({ children }) => {
    const { hasHydrated, isAuthenticated } = useAuthStore();
    const { bootstrapped, syncing, syncData } = useBootstrapStore();

    useEffect(() => {
        if (hasHydrated && !bootstrapped && !syncing) {
            syncData();
        }
    }, [hasHydrated, bootstrapped, syncing, syncData]);

    // Initialize sockets.
    // The hook itself should only connect once the user is authenticated.
    useAppSocket();

    // Wait for Zustand persistence.
    if (!hasHydrated) {
        console.log("Waiting for Zustand persistence...");
        return <div className="flex min-h-screen items-center justify-center bg-(--background)">
            <img
                src={Loader}
                alt="Loading…"
                style={{ width: 160, height: 160 }}
            />
        </div>;
    }

    // Wait for initial data synchronization.
    if (syncing || !bootstrapped) {
        console.log("Waiting for initial data synchronization...");
        return (
            <div className="flex min-h-screen items-center justify-center bg-(--background)">
                <img
                    src={Loader}
                    alt="Loading…"
                    style={{ width: 160, height: 160 }}
                />
            </div>
        );
    }

    // User is not logged in.
    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    // App is ready.
    return children;
};

export default ProtectedRoute;