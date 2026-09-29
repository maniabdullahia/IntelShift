import useAuthStore from "../store/auth.store";

/**
 * Client mirror of the server's entitlement logic. Lets components proactively
 * disable actions and show "trial ended" messaging instead of waiting for the API
 * to 403. The server is still the source of truth (blockReadOnly middleware).
 *
 * @returns {{ status, isTrial, trialExpired, active, readOnly, trialEnd, daysLeft }}
 */
export default function useEntitlement() {
  const user = useAuthStore((s) => s.user);
  const sub = user?.subscription;
  const status = sub?.status || null;
  const trialEnd = sub?.trialEnd ? new Date(sub.trialEnd) : null;
  const now = Date.now();

  const trialExpired = status === "trialing" && !!trialEnd && trialEnd.getTime() < now;
  const active = status === "active" || (status === "trialing" && !trialExpired);
  const readOnly = trialExpired || status === "canceled" || !sub;
  const daysLeft = trialEnd ? Math.max(0, Math.ceil((trialEnd.getTime() - now) / 86400000)) : null;

  return {
    status,
    isTrial: status === "trialing",
    trialExpired,
    active,
    readOnly,
    trialEnd,
    daysLeft,
  };
}
