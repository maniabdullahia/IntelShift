import React from "react";

function Spinner({ size = 64 }) {
  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      {/* Outer Ring */}
      <div
        className="absolute rounded-full border-4 border-(--border)"
        style={{
          width: size,
          height: size,
        }}
      />

      {/* Animated Ring */}
      <div
        className="absolute animate-spin rounded-full border-4 border-transparent border-t-(--accent) border-r-(--secondary)"
        style={{
          width: size,
          height: size,
          animationDuration: "900ms",
        }}
      />

      {/* Inner Pulse */}
      <div
        className="animate-pulse rounded-full bg-(--primary)"
        style={{
          width: size * 0.28,
          height: size * 0.28,
        }}
      />
    </div>
  );
}

export default Spinner;