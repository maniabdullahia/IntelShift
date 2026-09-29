import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { MailCheck } from "lucide-react";

import AuthShell, { AuthCardHeader, AuthButton } from "./AuthShell";

import { verifyEmail } from "../../api/auth.api";

function VerifyEmail() {
  const { token } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(false);
  const [verified, setVerified] = useState(false);
  const [error, setError] = useState("");

  const handleVerify = async () => {
    if (!token) {
      setError(
        "The verification link is missing its token. Please request a new email verification link."
      );
      return;
    }

    setLoading(true);
    setError("");

    try {
      await verifyEmail({ token });
      setVerified(true);

      window.setTimeout(() => {
        navigate("/login");
      }, 1600);
    } catch (verificationError) {
      setError(
        verificationError?.message ||
          "We could not verify this email. Please request a fresh verification link."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell>
      <AuthCardHeader
        icon={MailCheck}
        tint="var(--accent)"
        eyebrow="Verify your email"
        title="Confirm your inbox"
        subtitle="Click the button below to verify your email address and activate your IntelShift account."
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

        {verified ? (
          <div
            role="status"
            className="rounded-(--radius-md) border border-(--success)/20 bg-(--success)/10 px-4 py-3 text-sm font-medium text-(--primary)"
          >
            Email verified successfully. Redirecting you to sign in...
          </div>
        ) : null}

        <AuthButton
          type="button"
          onClick={handleVerify}
          loading={loading}
          disabled={verified}
        >
          {loading ? "Verifying email..." : verified ? "Verified" : "Verify Email"}
        </AuthButton>
      </div>

      <p className="mt-6 text-center text-xs text-(--text-light)">
        Didn&apos;t get the email? Check your spam folder or request a new
        verification link.
      </p>
    </AuthShell>
  );
}

export default VerifyEmail;
