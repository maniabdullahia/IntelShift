function Select({
  id,
  label,
  error,
  hint,
  className = "",
  options = [],
  value,
  onChange,
  disabled = false,
  placeholder,
  ...rest
}) {
  return (
    <div className={["w-full", className].join(" ")}>
      {label ? (
        <label htmlFor={id} className="mb-2 block text-sm font-semibold text-(--primary)">
          {label}
        </label>
      ) : null}
      <select
        id={id}
        value={value}
        onChange={onChange}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        className={[
          "w-full appearance-none rounded-sm border bg-white px-4 py-3 text-sm text-(--text) shadow-[0_1px_2px_var(--shadow-sm)] transition duration-200 focus:border-(--primary) focus:shadow-[0_0_0_3px_var(--shadow-lg)] focus:outline-none",
          error ? "border-(--danger)" : "border-(--border)",
          disabled ? "cursor-not-allowed opacity-70" : "",
        ].join(" ")}
        {...rest}
      >
        {placeholder ? <option value="">{placeholder}</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error ? <p className="mt-2 text-sm text-(--danger)">{error}</p> : null}
      {hint && !error ? <p className="mt-2 text-sm text-(--text-light)">{hint}</p> : null}
    </div>
  );
}

export default Select;
