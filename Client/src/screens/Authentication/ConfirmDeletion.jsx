import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ShieldAlert } from "lucide-react";

import AuthShell, { AuthCardHeader, AuthButton } from "./AuthShell";

import { confirmAccountDeletion } from "../../api/account.api";

const fmt = (d) =>
  d
    ? new Date(d).toLocaleDateString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "";

function ConfirmDeletion() {
  const { token } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(null); // { accessEndsAt, deleteAt }
  const [error, setError] = useState("");

  const handleConfirm = async () => {
    if (!token) {
      setError("This confirmation link is missing its token. Please start the closure again from Settings.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await confirmAccountDeletion(token);
      setDone(res);
    } catch (e) {
      setError(e?.message || "This confirmation link is invalid or has expired.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell>
      <AuthCardHeader
        icon={ShieldAlert}
        tint="var(--danger)"
        eyebrow="Account closure"
        title="Confirm account closure"
        subtitle="This schedules your IntelShift account for closure. You'll keep full access until the end of your paid period, and can reactivate anytime before then."
      />

      <div className="mt-8 space-y-4">
        {error ? (
          <div
            role="alert"
            className="rounded-(--radius-md) border border-(--danger)/20 bg-(--danger)/5 px-4 py-3 text-left text-sm text-(--danger)"
          >
            {error}
          </div>
        ) : null}

        {done ? (
          <div
            role="status"
            className="rounded-(--radius-md) border border-(--success)/20 bg-(--success)/10 px-4 py-3 text-left text-sm text-(--primary)"
          >
            <p className="font-medium">Your account is scheduled to close.</p>
            <p className="mt-2 text-(--text-light)">
              Access continues until <strong>{fmt(done.accessEndsAt)}</strong>. Your data is
              permanently deleted on <strong>{fmt(done.deleteAt)}</strong>. Changed your mind?
              Reactivate from Settings → Workspace before then.
            </p>
          </div>
        ) : null}

        {done ? (
          <AuthButton type="button" onClick={() => navigate("/settings/workspace")}>
            Go to Workspace settings
          </AuthButton>
        ) : (
          <AuthButton type="button" onClick={handleConfirm} loading={loading} disabled={loading}>
            {loading ? "Confirming..." : "Confirm account closure"}
          </AuthButton>
        )}
      </div>

      <p className="mt-6 text-center text-xs text-(--text-light)">
        Didn&apos;t request this? You can safely ignore it — nothing changes unless you confirm.
      </p>
    </AuthShell>
  );
}

export default ConfirmDeletion;
