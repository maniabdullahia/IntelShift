import { useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { Lock, KeyRound, ArrowLeft, Check } from "lucide-react";

import AuthShell, {
  AuthCardHeader,
  AuthField,
  AuthButton,
} from "./AuthShell";

// Replaces the raw window.alert() calls: every other auth screen
// reports validation errors through the shared Alert wrapper.
import Swal from "../../components/shared/Alert";

import { resetPassword } from "../../api/auth.api";

function ResetPassword() {
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const { token } = useParams();
  const navigate = useNavigate();

  const mismatch =
    confirmPassword.length > 0 && newPassword !== confirmPassword;

  // Same requirements as signup: 8+ chars, uppercase, lowercase, number.
  const pwChecks = {
    length: newPassword.length >= 8,
    upper: /[A-Z]/.test(newPassword),
    lower: /[a-z]/.test(newPassword),
    number: /\d/.test(newPassword),
  };
  const pwValid = Object.values(pwChecks).every(Boolean);
  const PW_RULES = [
    ["8+ characters", pwChecks.length],
    ["One uppercase", pwChecks.upper],
    ["One lowercase", pwChecks.lower],
    ["One number", pwChecks.number],
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!newPassword.trim() || !confirmPassword.trim()) {
      Swal.fire({
        icon: "error",
        title: "Missing Fields",
        text: "Please fill in both password fields.",
      });
      return;
    }

    if (!pwValid) {
      Swal.fire({
        icon: "error",
        title: "Weak password",
        text: "Your password needs at least 8 characters, with an uppercase letter, a lowercase letter, and a number.",
      });
      return;
    }

    if (newPassword !== confirmPassword) {
      Swal.fire({
        icon: "error",
        title: "Password Mismatch",
        text: "The two passwords do not match. Please check your input and try again.",
      });
      return;
    }

    setSubmitting(true);

    try {
      await resetPassword({ newPassword, token });
      // Success — send them to login to sign in with the new password.
      navigate("/login", { replace: true });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell>
      <AuthCardHeader
        icon={KeyRound}
        tint="var(--accent)"
        eyebrow="Password reset"
        title="Reset your password"
        subtitle="Create a strong password to secure your account."
      />

      <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
        <AuthField
          id="newPassword"
          label="New Password"
          type="password"
          icon={Lock}
          placeholder="Enter new password"
          autoComplete="new-password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
        />

        <AuthField
          id="confirmPassword"
          label="Confirm Password"
          type="password"
          icon={Lock}
          placeholder="Confirm new password"
          autoComplete="new-password"
          error={mismatch}
          hint={mismatch ? "Passwords do not match." : undefined}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
        />

        <div className="rounded-(--radius-md) border border-(--border) bg-(--bg) p-4">
          <p className="mb-2.5 text-sm font-semibold text-(--text)">
            Password requirements
          </p>
          <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {PW_RULES.map(([label, ok]) => (
              <li
                key={label}
                className={`flex items-center gap-1.5 text-xs transition-colors ${
                  ok ? "text-(--success)" : "text-(--text-light)"
                }`}
              >
                {ok ? (
                  <Check size={13} strokeWidth={3} />
                ) : (
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-(--text-light)/50" />
                )}
                {label}
              </li>
            ))}
          </ul>
        </div>

        <AuthButton type="submit" loading={submitting}>
          {submitting ? "Resetting..." : "Reset Password"}
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

export default ResetPassword;
