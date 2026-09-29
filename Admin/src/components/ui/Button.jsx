
const variantClasses = {
  primary: "bg-(--accent) text-white shadow-[0_12px_24px_rgba(255,107,107,0.22)] hover:bg-[#ff5757]",
  secondary: "bg-(--primary) text-white shadow-[0_8px_18px_var(--shadow-sm)] hover:bg-[#0f0f22]",
  danger: "bg-(--danger) text-white shadow-[0_12px_24px_rgba(252,92,101,0.18)] hover:bg-[#f54d57]",
  black: "bg-(--primary) text-white shadow-[0_12px_24px_rgba(26,26,46,0.2)] hover:bg-[#10101f]",
  ghost: "bg-white border border-(--border) text-(--primary) hover:bg-(--bg)",
  outline: "border border-(--border) bg-transparent text-(--primary) hover:bg-white",
};

function Button({
  title,
  children,
  onClick,
  variant = "primary",
  fullWidth = false,
  disabled = false,
  className = "",
  type = "button",
  loading = false,
  ...rest
}) {
  const content = children ?? title;

  return (
    <button
      type={type}
      className={[
        "inline-flex items-center justify-center gap-2 transition duration-200 focus-visible:ring-2 focus-visible:ring-(--accent) focus-visible:ring-offset-2",
        fullWidth ? "w-full" : "w-auto",
        disabled || loading ? "cursor-not-allowed opacity-60" : "hover:-translate-y-0.5 active:translate-y-0",
        variantClasses[variant] || variantClasses.primary,
        className,
      ].join(" ")}
      style={{ padding: '12px 18px', borderRadius: '8px', fontWeight: '700', fontFamily: "'DM Sans', sans-serif", fontSize: '14px', border: 'none', cursor: disabled || loading ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap' }}
      onClick={onClick}
      aria-busy={loading}
      aria-disabled={disabled || loading}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" aria-hidden="true" />
      ) : content}
    </button>
  );
}

export default Button


