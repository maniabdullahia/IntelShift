import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useAuth0 } from "@auth0/auth0-react"
import { User, Mail, Lock, UserPlus, Check } from "lucide-react"

import AuthShell, {
  AuthCardHeader,
  AuthField,
  AuthButton,
  AuthDivider,
  SocialButton,
} from "./AuthShell"

import useModelStore from "../../store/model.store"
import Swal from "../../components/shared/Alert"

import useAuthStore from "../../store/auth.store"

import { getPaddleCheckout } from "../../services/paddle/paddle.service"

// Social login icons
const GoogleIcon = () => (
  <svg
    width='20'
    height='20'
    viewBox='0 0 24 24'
    fill='none'
    xmlns='http://www.w3.org/2000/svg'
    aria-hidden='true'>
    <path
      d='M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z'
      fill='#4285F4'
    />
    <path
      d='M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z'
      fill='#34A853'
    />
    <path
      d='M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z'
      fill='#FBBC05'
    />
    <path
      d='M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z'
      fill='#EA4335'
    />
  </svg>
)

const FacebookIcon = () => (
  <svg
    width='20'
    height='20'
    viewBox='0 0 24 24'
    fill='none'
    xmlns='http://www.w3.org/2000/svg'
    aria-hidden='true'>
    <path
      d='M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z'
      fill='#1877F2'
    />
  </svg>
)

function Signup() {
  const [formData, setFormData] = useState({
    fullname: "",
    email: "",
    password: "",
    confirmPassword: "",
    planType: "trial",
    termsAccepted: false,
  })

  // Loading state
  const [loading, setLoading] = useState(false)

  const [searchParams] = useSearchParams()
  const planId = searchParams.get("plan")

  const register = useAuthStore((state) => state.register)
  const openModel = useModelStore((state) => state.openModel)

  const { loginWithPopup, getIdTokenClaims } = useAuth0()

  async function loginWithGoogle() {
    await loginWithPopup({
      authorizationParams: {
        connection: "google-oauth2",
        screen_hint: "signup",
      },
    })

    const claims = await getIdTokenClaims()

    if (!claims) {
      return
    }

    const { name, email, sub, email_verified, picture } = claims

    const result = await register({
      name: name,
      email: email,
      password: "",
      provider: "google",
      socialSub: sub,
      planId: planId,
      isEmailVerified: email_verified,
      profilePicture: picture || "",
    })

    if (result && result.priceId) {
      await getPaddleCheckout(
        result.priceId,
        result.planId,
        result.user,
        "billing-success"
      )
    }
  }

  async function loginWithFacebook() {
    await loginWithPopup({
      authorizationParams: {
        connection: "facebook",
        screen_hint: "signup",
      },
    })

    const claims = await getIdTokenClaims()

    // NOTE: the original code destructured `claims` without a null guard here,
    // unlike loginWithGoogle. A cancelled popup would throw.
    if (!claims) {
      return
    }

    const { name, email, sub, email_verified, picture } = claims

    if (!email) {
      console.log("[Email Not Found]")

      let selectedEmail = await openModel("mail-prompt", {
        title: "Email Required",
      })

      const result = await register({
        name: name,
        email: selectedEmail,
        password: "",
        provider: "facebook",
        socialSub: sub,
        planId: planId,
        isEmailVerified: false,
        profilePicture: picture || "",
      })

      if (result && result.priceId) {
        await getPaddleCheckout(
          result.priceId,
          result.planId,
          result.user,
          "billing-success"
        )
      }

      return
    }

    const result = await register({
      name: name,
      email: email,
      password: "",
      provider: "facebook",
      planId: planId,
      socialSub: sub,
      isEmailVerified: email_verified,
      profilePicture: picture || "",
    })

    if (result && result.priceId) {
      await getPaddleCheckout(
        result.priceId,
        result.planId,
        result.user,
        "billing-success"
      )
    }
  }

  const handleChange = (e) => {
    const { id, value, type, checked } = e.target
    setFormData({
      ...formData,
      [id]: type === "checkbox" ? checked : value,
    })
  }

  // Live password requirement checks (mirrors the hint, but functional).
  const pw = formData.password
  const pwChecks = {
    length: pw.length >= 8,
    upper: /[A-Z]/.test(pw),
    lower: /[a-z]/.test(pw),
    number: /\d/.test(pw),
  }
  const pwValid = Object.values(pwChecks).every(Boolean)
  const PW_RULES = [
    ["8+ characters", pwChecks.length],
    ["One uppercase", pwChecks.upper],
    ["One lowercase", pwChecks.lower],
    ["One number", pwChecks.number],
  ]

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (
      !formData.fullname ||
      !formData.email ||
      !formData.password ||
      !formData.confirmPassword
    ) {
      Swal.fire({
        icon: "error",
        title: "Missing Fields",
        text: "Please fill in all required fields before submitting the form.",
      })
      return
    }

    if (!pwValid) {
      Swal.fire({
        icon: "error",
        title: "Weak password",
        text: "Your password needs at least 8 characters, with an uppercase letter, a lowercase letter, and a number.",
      })
      return
    }

    if (formData.password !== formData.confirmPassword) {
      Swal.fire({
        icon: "error",
        title: "Password Mismatch",
        text: "The password and confirm password fields do not match. Please check your input and try again.",
      })
      return
    }

    if (!formData.termsAccepted) {
      Swal.fire({
        icon: "error",
        title: "Terms Required",
        text: "Please accept the Terms of Service and Privacy Policy before continuing.",
      })
      return
    }

    try {
      setLoading(true)

      const result = await register({
        name: formData.fullname,
        email: formData.email,
        password: formData.password,
        provider: "local",
        planId: planId,
        isEmailVerified: false,
      })

      if (result && result.priceId) {
        await getPaddleCheckout(
          result.priceId,
          result.planId,
          result.user,
          "billing-success"
        )
      }
    } catch (error) {
      console.error("Error setting loading state:", error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell>
      <AuthCardHeader
        icon={UserPlus}
        tint='var(--accent)'
        eyebrow='Create account'
        title='Get started'
        subtitle='Set up your IntelShift workspace in a couple of minutes.'
      />

      <form className='mt-6 space-y-3.5' onSubmit={handleSubmit}>
        <AuthField
          id='fullname'
          label='Full Name'
          icon={User}
          placeholder='Enter your full name'
          autoComplete='name'
          value={formData.fullname}
          onChange={handleChange}
        />

        <AuthField
          id='email'
          label='Email Address'
          type='email'
          icon={Mail}
          placeholder='name@example.com'
          autoComplete='email'
          value={formData.email}
          onChange={handleChange}
        />

        <div>
          <AuthField
            id='password'
            label='Password'
            type='password'
            icon={Lock}
            placeholder='Create a password'
            autoComplete='new-password'
            value={formData.password}
            onChange={handleChange}
          />

          {formData.password.length > 0 && (
            <ul className='mt-2 grid grid-cols-2 gap-x-3 gap-y-1'>
              {PW_RULES.map(([label, ok]) => (
                <li
                  key={label}
                  className={`flex items-center gap-1.5 text-xs transition-colors ${
                    ok ? 'text-(--success)' : 'text-(--text-light)'
                  }`}
                >
                  {ok ? (
                    <Check size={13} strokeWidth={3} />
                  ) : (
                    <span className='inline-block h-1.5 w-1.5 rounded-full bg-(--text-light)/50' />
                  )}
                  {label}
                </li>
              ))}
            </ul>
          )}
        </div>

        <AuthField
          id='confirmPassword'
          label='Confirm Password'
          type='password'
          icon={Lock}
          placeholder='Confirm your password'
          autoComplete='new-password'
          error={
            formData.confirmPassword.length > 0 &&
            formData.password !== formData.confirmPassword
          }
          value={formData.confirmPassword}
          onChange={handleChange}
        />

        <label
          htmlFor='termsAccepted'
          className='flex cursor-pointer items-start gap-2.5 text-xs leading-relaxed text-(--text-light)'>
          <input
            id='termsAccepted'
            type='checkbox'
            checked={formData.termsAccepted}
            onChange={handleChange}
            className='mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border-(--border) accent-(--accent)'
          />
          <span>
            I agree to the{" "}
            <a
              href='https://intelshift.ai/terms'
              target='_blank'
              rel='noreferrer'
              className='font-semibold text-(--accent) transition hover:opacity-80'>
              Terms of Service
            </a>{" "}
            and{" "}
            <a
              href='https://intelshift.ai/privacy-policy'
              target='_blank'
              rel='noreferrer'
              className='font-semibold text-(--accent) transition hover:opacity-80'>
              Privacy Policy
            </a>
          </span>
        </label>

        <AuthButton type='submit' loading={loading}>
          {loading ? "Creating account..." : "Create Account"}
        </AuthButton>
      </form>

      <AuthDivider label='Or sign up with' />

      <div className='grid grid-cols-2 gap-3'>
        <SocialButton
          label='Sign up with Google'
          brandColor='#4285F4'
          onClick={loginWithGoogle}>
          <GoogleIcon />
        </SocialButton>

        <SocialButton
          label='Sign up with Facebook'
          brandColor='#1877F2'
          onClick={loginWithFacebook}>
          <FacebookIcon />
        </SocialButton>
      </div>

      <div className='mt-6 border-t border-(--border) pt-4 text-center'>
        <p className='text-sm text-(--text-light)'>
          Already have an account?{" "}
          <Link
            to='/login'
            className='font-semibold text-(--accent) transition hover:opacity-80'>
            Sign In
          </Link>
        </p>
      </div>
    </AuthShell>
  )
}

export default Signup
