import { useState } from "react";
import { Link } from "react-router-dom";
import { Mail, LockKeyhole, ArrowLeft } from "lucide-react";

import AuthShell, {
  AuthCardHeader,
  AuthField,
  AuthButton,
} from "./AuthShell";

// Use the shared Alert wrapper so styling matches Login/Signup,
// rather than importing sweetalert2 directly.
import Swal from "../../components/shared/Alert";

import { forgetPassword } from "../../api/auth.api";

function ForgetPassword() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    if (!email.trim()) {
      Swal.fire({
        icon: "error",
        title: "Error",
        text: "Please enter your email address.",
      });
      return;
    }

    setSubmitting(true);

    try {
      await forgetPassword({ email: email.trim() });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell>
      <AuthCardHeader
        icon={LockKeyhole}
        tint="var(--accent)"
        eyebrow="Password reset"
        title="Forgot your password?"
        subtitle="Enter your email address and we'll send you a password reset link."
      />

      <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
        <AuthField
          id="email"
          label="Email Address"
          type="email"
          icon={Mail}
          placeholder="name@example.com"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <AuthButton type="submit" loading={submitting}>
          {submitting ? "Sending link..." : "Send Reset Link"}
        </AuthButton>
      </form>

      <div className="mt-8 border-t border-(--border) pt-5">
        <Link
          to="/login"
          className="flex items-center justify-center gap-2 text-sm font-medium text-(--primary) transition hover:text-(--accent)"
        >
          <ArrowLeft size={16} />
          Back to Login
        </Link>
      </div>
    </AuthShell>
  );
}

export default ForgetPassword;
