import { useState } from "react";
import { LogOut, MailCheck, Send } from "lucide-react";

import AuthShell, {
  AuthCardHeader,
  AuthField,
  AuthButton,
} from "./AuthShell";

import useAuthStore from "../../store/auth.store";

import { sendEmailVerificationLink } from "../../api/auth.api";

import { logout } from "../../api/user.api";

function EmailVerification() {
  const { user } = useAuthStore();

  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  function handleLogout() {
    logout();
  }

  async function handleSend() {
    if (!user?.email) return;

    setSending(true);

    try {
      await sendEmailVerificationLink({ email: user.email });
      setSent(true);
    } finally {
      setSending(false);
    }
  }

  return (
    <AuthShell>
      <AuthCardHeader
        icon={MailCheck}
        tint="var(--accent)"
        eyebrow="Email verification"
        title="Verify your email"
        subtitle="We'll send a verification link to the address on your account. Request a new one if your current link has expired."
      />

      <div className="mt-8 space-y-4">
        {/* Falling back to "" keeps the input controlled even before the auth
            store hydrates, avoiding React's controlled/uncontrolled warning. */}
        <AuthField
          id="verificationEmail"
          label="Email Address"
          type="email"
          icon={Send}
          placeholder="name@example.com"
          autoComplete="email"
          readOnly
          disabled={Boolean(user?.email)}
          value={user?.email ?? ""}
          onChange={() => {}}
        />

        {sent ? (
          <div
            role="status"
            className="rounded-(--radius-md) border border-(--success)/20 bg-(--success)/10 px-4 py-3 text-sm font-medium text-(--primary)"
          >
            Verification link sent. Check your inbox, and your spam folder.
          </div>
        ) : null}

        <AuthButton type="button" onClick={handleSend} loading={sending}>
          <MailCheck size={18} />
          {sending
            ? "Sending..."
            : sent
            ? "Resend Link"
            : "Get Verification Link"}
        </AuthButton>

        <AuthButton type="button" variant="secondary" onClick={handleLogout}>
          <LogOut size={18} />
          Log out
        </AuthButton>
      </div>
    </AuthShell>
  );
}

export default EmailVerification;
