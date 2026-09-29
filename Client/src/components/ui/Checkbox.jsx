import React from "react";

function Checkbox({ checked = false, onChange, disabled = false }) {
  return (
    <label
      className={`relative inline-flex items-center justify-center
       border transition-all duration-200
      ${
        disabled
          ? "opacity-40 cursor-not-allowed"
          : "cursor-pointer hover:scale-105"
      }
      ${
        checked
          ? "bg-(--accent) border-(--accent)"
          : "bg-white border-gray-500 hover:border-(--accent)]"
      }
      `}
    >
      {/* Hidden native input */}
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="absolute w-full h-full opacity-0 cursor-pointer"
      />

      {/* Checkmark */}
      <svg
        className={`w-3 h-3 text-white transition-all duration-200
        ${checked ? "opacity-100 scale-100" : "opacity-0 scale-75"}
        `}
        viewBox="0 0 20 20"
        fill="currentColor"
      >
        <path
          fillRule="evenodd"
          d="M16.704 5.29a1 1 0 010 1.42l-7.2 7.2a1 1 0 01-1.42 0l-3.2-3.2a1 1 0 011.42-1.42l2.49 2.49 6.49-6.49a1 1 0 011.42 0z"
          clipRule="evenodd"
        />
      </svg>
    </label>
  );
}

export default Checkbox;