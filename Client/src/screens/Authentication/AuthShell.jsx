import { useState } from "react";
import { Eye, EyeOff, LoaderCircle, Check } from "lucide-react";
import Brand from "../../components/shared/Brand";

/* ────────────────────────────────────────────────────────────────
   IntelShift — shared shell for every authentication screen.

   All six auth screens render through this so the card, spacing,
   icon badge and heading treatment stay identical.

   Headings: Inter, weight 800, var(--primary), no italic, one colour.
   Accent:   var(--accent) everywhere - icon badges, eyebrow pills,
             primary buttons and links all use the same red.

   NOTE ON BUTTON COLOURS
   Button background/text colours are set with inline styles, not
   Tailwind classes. In Tailwind v4 `bg-(--accent-dark)` is ambiguous
   (background-color vs background-image) and needs a `bg-(color:...)`
   hint; without it the class silently produces no rule. That is what
   made the primary buttons turn white on hover and swallow their
   label. Inline styles avoid the ambiguity entirely.
──────────────────────────────────────────────────────────────── */

export function AuthCardHeader({
  icon: Icon,
  tint = "var(--accent)",
  eyebrow,
  title,
  subtitle,
}) {
  return (
    <header className="text-center">
      {Icon ? (
        <div
          className="mx-auto flex h-12 w-12 items-center justify-center rounded-full"
          style={{
            background: `color-mix(in srgb, ${tint} 12%, transparent)`,
            color: tint,
          }}
        >
          <Icon size={22} strokeWidth={1.75} />
        </div>
      ) : null}

      {eyebrow ? (
        <span
          className="mt-4 inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-bold uppercase"
          style={{
            background: "color-mix(in srgb, var(--accent) 10%, transparent)",
            border:
              "1px solid color-mix(in srgb, var(--accent) 25%, transparent)",
            color: "var(--accent)",
            letterSpacing: "0.08em",
          }}
        >
          {eyebrow}
        </span>
      ) : null}

      <h1
        className={eyebrow ? "mt-3" : "mt-4"}
        style={{
          fontFamily: "var(--font-heading)",
          fontSize: "clamp(22px, 3vw, 26px)",
          fontWeight: 800,
          fontStyle: "normal",
          letterSpacing: "-0.025em",
          lineHeight: 1.15,
          color: "var(--primary)",
        }}
      >
        {title}
      </h1>

      {subtitle ? (
        <p className="mt-2 text-sm leading-6 text-(--text-light)">{subtitle}</p>
      ) : null}
    </header>
  );
}

/* Single text/email/password field. Password fields get a reveal
   toggle automatically. `hint` renders under the input. */
export function AuthField({
  id,
  label,
  type = "text",
  icon: Icon,
  hint,
  error,
  ...inputProps
}) {
  const [revealed, setRevealed] = useState(false);
  const isPassword = type === "password";
  const resolvedType = isPassword && revealed ? "text" : type;

  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 block text-sm font-semibold text-(--text)"
      >
        {label}
      </label>

      <div className="relative">
        {Icon ? (
          <Icon
            size={18}
            aria-hidden="true"
            className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-(--text-light)"
          />
        ) : null}

        <input
          id={id}
          type={resolvedType}
          aria-invalid={error ? "true" : undefined}
          aria-describedby={hint ? `${id}-hint` : undefined}
          style={{
            backgroundColor: "var(--card)",
            borderColor: error ? "var(--danger)" : "var(--border)",
            color: "var(--text)",
          }}
          className={`w-full rounded-(--radius-md) border py-2.5 outline-none transition placeholder:text-(--text-light) focus:border-(--accent) focus:ring-2 focus:ring-(--accent)/20 disabled:cursor-not-allowed ${
            Icon ? "pl-11" : "pl-4"
          } ${isPassword ? "pr-11" : "pr-4"}`}
          {...inputProps}
        />

        {isPassword ? (
          <button
            type="button"
            onClick={() => setRevealed((v) => !v)}
            aria-label={revealed ? "Hide password" : "Show password"}
            aria-pressed={revealed}
            className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-(--text-light) transition hover:text-(--text) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--accent)/40"
          >
            {revealed ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        ) : null}
      </div>

      {hint ? (
        <p id={`${id}-hint`} className="mt-1.5 text-xs text-(--text-light)">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

/* Mirrors .btn / .btn-primary from index.html: 15px, weight 700,
   12px radius, coral glow, -2px lift on hover.
   Colours are inline - see the note at the top of this file. */
export function AuthButton({
  children,
  loading = false,
  variant = "primary",
  className = "",
  disabled,
  style,
  ...props
}) {
  const isPrimary = variant === "primary";
  const isDisabled = disabled || loading;

  const restingBg = isPrimary ? "var(--accent)" : "var(--card)";
  // Red primary buttons turn teal (with white text) on hover, matching the app.
  const hoverBg = isPrimary ? "var(--secondary)" : "var(--bg)";
  const restingShadow = isPrimary ? "0 8px 24px rgba(255,107,107,0.3)" : "none";
  const hoverShadow = isPrimary ? "0 12px 32px rgba(78,205,196,0.35)" : "none";

  return (
    <button
      disabled={isDisabled}
      className={`flex w-full items-center justify-center gap-2 rounded-(--radius-md) px-6 py-3 text-[15px] font-bold transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-70 focus:outline-none focus-visible:ring-2 focus-visible:ring-(--accent)/40 ${className}`}
      style={{
        backgroundColor: restingBg,
        color: isPrimary ? "#ffffff" : "var(--primary)",
        border: isPrimary ? "none" : "1px solid var(--border)",
        boxShadow: isDisabled ? "none" : restingShadow,
        ...style,
      }}
      onMouseEnter={(e) => {
        if (isDisabled) return;
        e.currentTarget.style.backgroundColor = hoverBg;
        e.currentTarget.style.color = isPrimary ? "#ffffff" : "var(--primary)";
        e.currentTarget.style.boxShadow = hoverShadow;
        if (isPrimary) e.currentTarget.style.transform = "translateY(-2px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = restingBg;
        e.currentTarget.style.color = isPrimary ? "#ffffff" : "var(--primary)";
        e.currentTarget.style.boxShadow = isDisabled ? "none" : restingShadow;
        e.currentTarget.style.transform = "translateY(0)";
      }}
      {...props}
    >
      {loading ? <LoaderCircle size={18} className="animate-spin" /> : null}
      {children}
    </button>
  );
}

/* "Or continue with" rule. */
export function AuthDivider({ label = "Or continue with" }) {
  return (
    <div className="my-4 flex items-center gap-3">
      <span className="h-px flex-1" style={{ background: "var(--border)" }} />
      <span
        className="text-[11px] font-extrabold uppercase text-(--text-light)"
        style={{ letterSpacing: "0.08em" }}
      >
        {label}
      </span>
      <span className="h-px flex-1" style={{ background: "var(--border)" }} />
    </div>
  );
}

/* Icon-only social provider button. */
export function SocialButton({ label, brandColor, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="flex items-center justify-center rounded-(--radius-md) py-3 shadow-(--shadow-sm) transition-all duration-200 hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-(--accent)/40"
      style={{
        backgroundColor: "var(--card)",
        border: "1px solid var(--border)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = brandColor;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "var(--border)";
      }}
    >
      {children}
    </button>
  );
}

/* The value bullets shown on the brand panel. */
const BRAND_POINTS = [
  "Automatic competitor monitoring",
  "AI insight on every meaningful change",
  "Alerts the moment prices or pages move",
];

function AuthShell({ children, width = "max-w-md" }) {
  return (
    <div
      className="min-h-screen w-full lg:grid lg:h-screen lg:grid-cols-[minmax(0,400px)_1fr] lg:overflow-hidden"
      style={{ fontFamily: "var(--font-body)", backgroundColor: "var(--bg)" }}
    >
      {/* ── Brand panel — dark, high-contrast, glow orbs (desktop only) ── */}
      <aside
        className="relative hidden overflow-hidden p-10 lg:flex lg:h-screen lg:flex-col lg:justify-between"
        style={{ background: "linear-gradient(160deg, var(--primary), var(--primary-2))" }}
      >
        <div
          className="pointer-events-none absolute -left-24 -top-28 h-80 w-80 rounded-full blur-3xl"
          style={{ background: "var(--glow-teal)" }}
        />
        <div
          className="pointer-events-none absolute -right-20 bottom-8 h-80 w-80 rounded-full blur-3xl"
          style={{ background: "var(--glow-coral)" }}
        />

        <Brand tone="light" className="relative" />

        <div className="relative max-w-sm">
          <h2 className="text-3xl font-extrabold leading-tight tracking-tight text-white">
            Know what your{" "}
            <span className="serif text-(--secondary)">competitors</span> change,
            before they announce it.
          </h2>
          <ul className="mt-6 space-y-3">
            {BRAND_POINTS.map((point) => (
              <li key={point} className="flex items-center gap-3 text-sm text-white/75">
                <span
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full"
                  style={{ background: "color-mix(in srgb, var(--secondary) 18%, transparent)", color: "var(--secondary)" }}
                >
                  <Check size={14} strokeWidth={3} />
                </span>
                {point}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-white/40">© 2026 IntelShift AI</p>
      </aside>

      {/* ── Form area — no card; it already lives in its own column.
          The inner wrapper keeps its padding even when a tall form scrolls,
          so the top never clips and there's always breathing room. ── */}
      <main className="lg:h-screen lg:overflow-y-auto">
        <div className="flex min-h-screen items-center justify-center px-6 py-10 sm:px-10 lg:min-h-full lg:px-14">
          <div className={`w-full ${width}`}>
            {/* Compact brand for mobile, where the panel is hidden. */}
            <div className="mb-6 flex justify-center lg:hidden">
              <Brand tone="dark" />
            </div>

            {children}
          </div>
        </div>
      </main>
    </div>
  );
}

export default AuthShell;
