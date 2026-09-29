import React from "react";

function Radio({ checked = false, onChange, disabled = false, name, value }) {
  return (
    <label
      className={`relative inline-flex items-center justify-center
      w-5 h-5 rounded-full border transition-all duration-200
      ${
        disabled
          ? "opacity-40 cursor-not-allowed"
          : "cursor-pointer hover:scale-105"
      }
      ${
        checked
          ? "border-(--accent)"
          : "border-gray-500 hover:border-(--accent)"
      }
      `}
    >
      {/* Hidden native input */}
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="absolute w-full h-full opacity-0 cursor-pointer"
      />

      {/* Inner dot */}
      <span
        className={`w-2.5 h-2.5 rounded-full bg-(--accent) transition-all duration-200
        ${checked ? "scale-100 opacity-100" : "scale-50 opacity-0"}
        `}
      />
    </label>
  );
}

export default Radio;