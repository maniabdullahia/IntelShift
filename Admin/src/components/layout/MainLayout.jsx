/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useState, useRef, useCallback } from "react";

import { Outlet } from "react-router-dom";

import Header from "./Header";
import Sidebar from "./Sidebar";

import useAuthStore from "../../store/auth.store.js";
import useWorkspaceStore from "../../store/workspace.store.js";
import useUserStore from "../../store/user.store.js";
import useAIUsageStore from "../../store/usage.ai.store.js";
import useCompetitorStore from "../../store/competitor.store.js";
import useJobStore from "../../store/jobs.store.js";

const MainLayout = () => {
    const [initializing, setInitializing] = useState(true);
    const [error, setError] = useState(null);
    const [progress, setProgress] = useState({
        workspaces: "idle",
        users: "idle",
    });
    const isMounted = useRef(true);

    const isAuthenticated = useAuthStore(
        (state) => state.isAuthenticated
    );

    const loadWorkspaces = useWorkspaceStore(
        (state) => state.loadWorkspaces
    );

    const loadCompetitors = useCompetitorStore(
        (state) => state.loadCompetitors
    );

    const loadJobs = useJobStore(
        (state) => state.loadJobs
    );

    const loadUsers = useUserStore(
        (state) => state.loadUsers
    );

    const loadAIUsage = useAIUsageStore(
        (state) => state.loadUsage
    );
    
    const workspaces = useWorkspaceStore((state) => state.workspaces);
    const users = useUserStore((state) => state.users);
    // const aiUsage = useAIUsageStore((state) => state.usage);

    const initialize = async () => {
        const withTimeout = (promise, ms, label) =>
            new Promise((resolve, reject) => {
                const timer = setTimeout(() => {
                    reject(new Error(`${label} timed out after ${ms}ms`));
                }, ms);

                promise
                    .then((res) => {
                        clearTimeout(timer);
                        resolve(res);
                    })
                    .catch((err) => {
                        clearTimeout(timer);
                        reject(err);
                    });
            });

        const attempt = async (fn, label, retries = 2, backoff = 500) => {
            let lastError;
            for (let i = 0; i <= retries; i++) {
                try {
                    const result = await fn();
                    return result;
                } catch (err) {
                    lastError = err;
                    // small exponential backoff
                    // don't delay after the last attempt
                    if (i < retries) {
                        // eslint-disable-next-line no-await-in-loop
                        await new Promise((r) => setTimeout(r, backoff * (i + 1)));
                    }
                }
            }
            throw new Error(`${label} failed: ${lastError?.message || lastError}`);
        };

        try {
            setInitializing(true);
            setError(null);
            setProgress({ workspaces: "pending", users: "pending" });

            const workspacePromise = attempt(
                () => withTimeout(loadWorkspaces(1, 100), 15000, "Load workspaces"),
                "Load workspaces",
                2
            ).then(() => {
                if (isMounted.current) setProgress((p) => ({ ...p, workspaces: "success" }));
            }).catch((err) => {
                if (isMounted.current) setProgress((p) => ({ ...p, workspaces: "failed" }));
                throw err;
            });

            const usersPromise = attempt(
                () => withTimeout(loadUsers(1, 100), 15000, "Load users"),
                "Load users",
                2
            ).then(() => {
                if (isMounted.current) setProgress((p) => ({ ...p, users: "success" }));
            }).catch((err) => {
                if (isMounted.current) setProgress((p) => ({ ...p, users: "failed" }));
                throw err;
            });

            const competitorsPromise = attempt(
                () => withTimeout(loadCompetitors(1, 100), 15000, "Load competitors"),
                "Load competitors",
                2
            ).then(() => {
                if (isMounted.current) setProgress((p) => ({ ...p, competitors: "success" }));
            }).catch((err) => {
                if (isMounted.current) setProgress((p) => ({ ...p, competitors: "failed" }));
                throw err;
            });

            const jobsPromise = attempt(
                () => withTimeout(loadJobs(1, 100), 15000, "Load jobs"),
                "Load jobs",
                2
            ).then(() => {
                if (isMounted.current) setProgress((p) => ({ ...p, jobs: "success" }));
            }).catch((err) => {
                if (isMounted.current) setProgress((p) => ({ ...p, jobs: "failed" }));
                throw err;
            });

            const aiUsagePromise = attempt(
                () => withTimeout(loadAIUsage(), 15000, "Load AI usage"),
                "Load AI usage",
                2
            ).then(() => {
                if (isMounted.current) setProgress((p) => ({ ...p, aiUsage: "success" }));
            }).catch((err) => {
                if (isMounted.current) setProgress((p) => ({ ...p, aiUsage: "failed" }));
                throw err;
            });

            const results = await Promise.allSettled([workspacePromise, usersPromise, competitorsPromise, jobsPromise, aiUsagePromise]);

            const failed = results.filter((r) => r.status === "rejected");
            if (failed.length) {
                const messages = failed.map((f) => (f.reason?.message ? f.reason.message : String(f.reason)));
                const message = `Initialization errors: ${messages.join("; ")}`;
                console.error(message);
                if (isMounted.current) setError(message);
            } else {
                console.log("MainLayout initialized");
            }
        } catch (err) {
            console.error(err);
            if (isMounted.current) setError(err.message || "Initialization failed");
        } finally {
            if (isMounted.current) setInitializing(false);
        }
    };

    useEffect(() => {
        return () => {
            isMounted.current = false;
        };
    }, []);

    const handleRetry = useCallback(() => {
        // reset state and re-run initialize
        setError(null);
        setProgress({ workspaces: "idle", users: "idle", competitors: "idle", aiUsage: "idle" });
        initialize();
    }, []);

    // If stores already have data (e.g. persisted), clear initializing
    useEffect(() => {
        if (!initializing) return;

        const workspacesLoaded = Array.isArray(workspaces) && workspaces.length > 0;
        const usersLoaded = Array.isArray(users) && users.length > 0;

        if (workspacesLoaded || usersLoaded) {
            setInitializing(false);
        }
    }, [workspaces, users, initializing]);

    // If both progress tasks are not pending, make sure we clear the loading state
    useEffect(() => {
        if (!initializing) return;
        const nonePending = progress.workspaces !== "pending" && progress.users !== "pending";
        // eslint-disable-next-line react-hooks/set-state-in-effect
        if (nonePending) setInitializing(false);
    }, [progress, initializing]);

    useEffect(() => {
        if (isAuthenticated) {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            initialize();
        } else {
            setInitializing(false);
        }
    }, [isAuthenticated]);

    // Improved loading / error UI
    if (initializing) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <div className="w-full max-w-md rounded-lg bg-white p-6 shadow">
                    <div className="flex items-center space-x-3">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
                        <div>
                            <div className="font-semibold">Initializing application...</div>
                            <div className="text-sm text-gray-600">Loading required data to start.</div>
                        </div>
                    </div>

                    <div className="mt-4 space-y-2">
                        <div className="flex items-center justify-between">
                            <div>Workspaces</div>
                            <div>
                                {progress.workspaces === "pending" && <span className="text-sm text-gray-500">Loading...</span>}
                                {progress.workspaces === "success" && <span className="text-sm text-green-600">Loaded</span>}
                                {progress.workspaces === "failed" && <span className="text-sm text-red-600">Failed</span>}
                            </div>
                        </div>

                        <div className="flex items-center justify-between">
                            <div>Users</div>
                            <div>
                                {progress.users === "pending" && <span className="text-sm text-gray-500">Loading...</span>}
                                {progress.users === "success" && <span className="text-sm text-green-600">Loaded</span>}
                                {progress.users === "failed" && <span className="text-sm text-red-600">Failed</span>}
                            </div>
                        </div>
                    </div>

                    {error ? (
                        <div className="mt-4 flex items-center justify-between">
                            <div className="text-sm text-red-600">{error}</div>
                            <div className="flex space-x-2">
                                <button
                                    type="button"
                                    onClick={handleRetry}
                                    className="rounded bg-blue-600 px-3 py-1 text-white"
                                >
                                    Retry
                                </button>
                            </div>
                        </div>
                    ) : null}
                </div>
            </div>
        );
    }

    // Prevent layout rendering if not authenticated
    if (!isAuthenticated) {
        return <Outlet />;
    }

    return (
        <div
            className="flex min-h-screen bg-(--bg)"
        >
            <Sidebar />

            <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
                <Header />

                <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
                    <Outlet />
                </div>
            </main>
        </div>
    );
};

export default MainLayout;