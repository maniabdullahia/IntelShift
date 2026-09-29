import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { Mail, Lock } from "lucide-react";
import LegalLinks from "../../components/shared/LegalLinks";

import AuthShell, {
  AuthCardHeader,
  AuthField,
  AuthButton,
  AuthDivider,
  SocialButton,
} from "./AuthShell";

import { login } from "../../api/auth.api";
import Swal from "../../components/shared/Alert";

// Social login icons
const GoogleIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
  </svg>
);

const FacebookIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" fill="#1877F2" />
  </svg>
);

function Login() {
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    remember: false,
  });

  const [submitting, setSubmitting] = useState(false);

  const { loginWithPopup, getIdTokenClaims } = useAuth0();

  async function loginWithGoogle() {
    await loginWithPopup({
      authorizationParams: {
        connection: "google-oauth2",
      },
    });

    const claims = await getIdTokenClaims();
    if (!claims) {
      return;
    }

    const { sub } = claims;

    await login({
      socialSub: sub,
      provider: "google",
    });
  }

  async function loginWithFacebook() {
    await loginWithPopup({
      authorizationParams: {
        connection: "facebook",
      },
    });

    const claims = await getIdTokenClaims();

    if (!claims) {
      return;
    }

    const { sub } = claims;

    await login({
      socialSub: sub,
      provider: "facebook",
    });
  }

  const handleChange = (e) => {
    const { id, type, checked, value } = e.target;
    setFormData({
      ...formData,
      [id]: type === "checkbox" ? checked : value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.email || !formData.password) {
      Swal.fire({
        icon: "error",
        title: "Missing Fields",
        text: "Please fill in both email and password fields before submitting the form.",
        confirmButtonColor: "#ff6b6b",
      });
      return;
    }

    setSubmitting(true);

    try {
      // NOTE: formData.remember is collected but never sent anywhere. If the
      // backend supports a longer-lived session, pass it through here.
      await login({
        email: formData.email,
        password: formData.password,
        provider: "local",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell>
      <AuthCardHeader
        icon={Lock}
        tint="var(--accent)"
        eyebrow="Sign in"
        title="Welcome back"
        subtitle="Sign in to your IntelShift account to continue."
      />

      <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
        <AuthField
          id="email"
          label="Email Address"
          type="email"
          icon={Mail}
          placeholder="name@example.com"
          autoComplete="email"
          value={formData.email}
          onChange={handleChange}
        />

        <AuthField
          id="password"
          label="Password"
          type="password"
          icon={Lock}
          placeholder="Enter your password"
          autoComplete="current-password"
          value={formData.password}
          onChange={handleChange}
        />

        <div className="flex items-center justify-between">
          <label
            htmlFor="remember"
            className="flex cursor-pointer items-center gap-2 text-sm font-medium text-(--text-light)"
          >
            <input
              id="remember"
              type="checkbox"
              checked={formData.remember}
              onChange={handleChange}
              className="h-4 w-4 cursor-pointer rounded border-(--border) accent-(--accent)"
            />
            Remember me
          </label>

          <Link
            to="/forgot-password"
            className="text-sm font-semibold text-(--accent) transition hover:opacity-80"
          >
            Forgot password?
          </Link>
        </div>

        <AuthButton type="submit" loading={submitting}>
          {submitting ? "Signing in..." : "Sign In"}
        </AuthButton>
      </form>

      <AuthDivider label="Or continue with" />

      <div className="grid grid-cols-2 gap-3">
        <SocialButton
          label="Sign in with Google"
          brandColor="#4285F4"
          onClick={loginWithGoogle}
        >
          <GoogleIcon />
        </SocialButton>

        <SocialButton
          label="Sign in with Facebook"
          brandColor="#1877F2"
          onClick={loginWithFacebook}
        >
          <FacebookIcon />
        </SocialButton>
      </div>

      <div className="mt-8 border-t border-(--border) pt-5 text-center">
        <p className="text-sm text-(--text-light)">
          Don&apos;t have an account?{" "}
          <Link
            to="/register"
            className="font-semibold text-(--accent) transition hover:opacity-80"
          >
            Create one
          </Link>
        </p>
      </div>

      <LegalLinks className="mt-6" />
    </AuthShell>
  );
}

export default Login;
