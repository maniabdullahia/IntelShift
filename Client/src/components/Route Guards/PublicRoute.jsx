import { Navigate } from "react-router-dom";

import useAuthStore from "../../store/auth.store";
import FreshDataSync from "../features/Loadings/FreshDataSync";
import Model from "../ui/Model";

import useModelStore from "../../store/model.store";

const PublicRoute = ({ children }) => {
    const { isAuthenticated, hasHydrated } = useAuthStore();
    const modelData = useModelStore((state) => state.modelData);

    if (!hasHydrated) {
        return (
            <FreshDataSync
                mode="auth"
                authHydrated={hasHydrated}
            />
        );
    }

    if (isAuthenticated) {
        return <Navigate to="/" replace />;
    }

    return (
        <>
            {children}
            {modelData && <Model />}
        </>
    );
};

export default PublicRoute;
