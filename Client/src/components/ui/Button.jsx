import { useState } from "react";

function Button({
  title = "Click Me",
  onClick,
  variant = "primary",
  fullWidth = false,
  disabled = false,
  loading = false,
  className = "",
  type = "button",
  style = {},
  showLoading = false,
}) {
  const [isLoading, setIsLoading] = useState(false);

  const handleClick = async (e) => {
    if (disabled || isLoading || loading) return;

    try {
      if (showLoading) {
        setIsLoading(true);
      }

      await Promise.resolve(onClick?.(e));
    } catch (error) {
      console.error("Button click error:", error);
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  };

  const isBusy = disabled || loading || isLoading;

  const sharedStyles = {
    padding: "0.75rem 1.25rem",
    borderRadius: "var(--radius-md)",
    fontWeight: "600",
    cursor: isBusy ? "not-allowed" : "pointer",
    transition:
      "transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease, background-color 0.2s ease",
    fontFamily: "var(--font-body)",
    fontSize: "14px",
    width: fullWidth ? "100%" : "auto",
    opacity: isBusy ? "0.6" : "1",
    pointerEvents: isBusy ? "none" : "auto",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "0.5rem",
    minHeight: "44px",
    outline: "none",
  };

  const primaryStyles = {
    ...sharedStyles,
    backgroundColor: "var(--accent)",
    color: "white",
    border: "none",
    boxShadow: "0 8px 18px rgba(255, 107, 107, 0.22)",
  };

  const secondaryStyles = {
    ...sharedStyles,
    backgroundColor: "var(--card)",
    color: "var(--primary)",
    border: "1px solid var(--border)",
    boxShadow: "0 4px 12px rgba(26, 26, 46, 0.08)",
  };

  const dangerStyles = {
    ...sharedStyles,
    backgroundColor: "var(--danger)",
    color: "white",
    border: "none",
    boxShadow: "0 8px 18px rgba(252, 92, 101, 0.2)",
  };

  const styles =
    variant === "secondary"
      ? secondaryStyles
      : variant === "danger"
      ? dangerStyles
      : primaryStyles;

  return (
    <button
      type={type}
      className={`${className} ${
        !isBusy ? "hover:-translate-y-0.5 active:translate-y-0" : ""
      } focus-visible:ring-2 focus-visible:ring-(--accent) focus-visible:ring-offset-2`}
      style={{ ...styles, ...style }}
      onClick={handleClick}
      onMouseEnter={(e) => {
        // Red (primary/danger) buttons turn teal with white text on hover.
        if (isBusy || variant === "secondary") return;
        e.currentTarget.style.backgroundColor = "var(--secondary)";
        e.currentTarget.style.color = "#fff";
      }}
      onMouseLeave={(e) => {
        if (variant === "secondary") return;
        e.currentTarget.style.backgroundColor = styles.backgroundColor;
        e.currentTarget.style.color = styles.color;
      }}
      disabled={isBusy}
      aria-busy={loading || isLoading}
      aria-disabled={isBusy}
    >
      {loading || isLoading ? (
        <div
          className={`h-5 w-5 animate-spin rounded-full border-2 border-t-transparent ${
            variant === "secondary"
              ? "border-(--primary)"
              : "border-white"
          }`}
          aria-hidden="true"
        />
      ) : (
        title
      )}
    </button>
  );
}

export default Button;