import { useCallback, useEffect, useState } from "react";

import useWorkspaceStore from "../store/workspace.store";
import { fetchMonitoringStatus } from "../components/features/WeeklyMonitoring/changeDetection.api";

/**
 * Loads the monitoring status payload that powers the Dashboard and
 * ChangeDetails screens. Reads the current workspace id from the store, so
 * callers don't have to pass it. Re-fetches when the workspace changes.
 *
 * @returns {{ status: object|null, loading: boolean, error: string|null,
 *             workspaceId: string|undefined, refetch: () => Promise<void> }}
 */
export default function useMonitoringStatus() {
  const workspaceId = useWorkspaceStore(
    (state) => state.workspace?._id || state.workspace?.id
  );

  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(
    async ({ signalMounted, attempt = 0 } = {}) => {
      if (!workspaceId) {
        setStatus(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const res = await fetchMonitoringStatus({ workspaceId });
        if (signalMounted && !signalMounted()) return;

        // A just-finished analysis can lag the monitoring-status endpoint by a moment,
        // so the first load right after landing on the dashboard can come back empty
        // (causing the "run your first analysis" flash). Retry a few times — but ONLY
        // when the workspace actually expects analysis, so a genuinely-new user still
        // sees the empty state immediately.
        const empty = !(res?.competitors?.length) && !(res?.reports?.length);
        const ws = useWorkspaceStore.getState().workspace;
        const expectsAnalysis =
          (ws?.analysis?.length || 0) > 0 || ws?.setupStage === "ready" || !!ws?.introCompleted;
        if (empty && expectsAnalysis && attempt < 4) {
          setTimeout(() => {
            if (!signalMounted || signalMounted()) load({ signalMounted, attempt: attempt + 1 });
          }, 1500);
          return; // keep the loading state; don't settle on empty yet
        }

        setStatus(res);
        setLoading(false);
      } catch (e) {
        if (signalMounted && !signalMounted()) return;
        setError(
          e?.response?.data?.message || e?.message || "Failed to load monitoring status"
        );
        setLoading(false);
      }
    },
    [workspaceId]
  );

  useEffect(() => {
    let mounted = true;
    load({ signalMounted: () => mounted });
    return () => {
      mounted = false;
    };
  }, [load]);

  const refetch = useCallback(() => load(), [load]);

  return { status, loading, error, workspaceId, refetch };
}
