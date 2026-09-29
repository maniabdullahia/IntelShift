import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

function Input({
  id,
  placeholder = "Enter text",
  value,
  onChange,
  type = "text",
  disabled = false,
  className = "",
  label,
  error,
  hint,
  ...rest
}) {
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = type === "password";

  return (
    <div className={["w-full", className].join(" ")}>
      {label ? (
        <label htmlFor={id} className="mb-2 block text-sm font-semibold text-(--primary)">
          {label}
        </label>
      ) : null}
      <div className="relative">
        <input
          id={id}
          type={isPassword ? (showPassword ? "text" : "password") : type}
          className={[
            "w-full rounded-sm border bg-white px-4 py-3 text-sm text-(--text) shadow-[0_1px_2px_var(--shadow-sm)] transition duration-200 placeholder:text-(--text-light) focus:border-(--primary) focus:shadow-[0_0_0_3px_var(--shadow-lg)] focus:outline-none",
            error ? "border-(--danger)" : "border-(--border)",
            isPassword ? "pr-11" : "",
            disabled ? "cursor-not-allowed opacity-70" : "",
          ].join(" ")}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          disabled={disabled}
          aria-disabled={disabled}
          aria-invalid={Boolean(error)}
          {...rest}
        />
        {isPassword ? (
          <button
            type="button"
            onClick={() => setShowPassword((current) => !current)}
            className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-(--text-light) transition hover:bg-black/5 hover:text-(--text)"
            aria-label={showPassword ? "Hide password" : "Show password"}
            tabIndex={disabled ? -1 : 0}
            disabled={disabled}
          >
            {showPassword ? <Eye size={16} /> : <EyeOff size={16} />}
          </button>
        ) : null}
      </div>
      {error ? <p className="mt-2 text-sm text-(--danger)">{error}</p> : null}
      {hint && !error ? <p className="mt-2 text-sm text-(--text-light)">{hint}</p> : null}
    </div>
  );
}

export default Input
