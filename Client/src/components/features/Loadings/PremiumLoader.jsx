import React from "react";

function PremiumLoader({
  size = 72,
  text = "Preparing your workspace...",
}) {
  return (
    <div className="flex flex-col items-center gap-6">
      <div
        className="relative"
        style={{
          width: size,
          height: size,
        }}
      >
        {/* Soft Glow */}
        <div
          className="absolute inset-0 rounded-full blur-xl opacity-30"
          style={{
            background:
              "radial-gradient(circle, var(--secondary), transparent 70%)",
          }}
        />

        {/* Outer Ring */}
        <div className="absolute inset-0 rounded-full border border-(--border)" />

        {/* Rotating Arc */}
        <div
          className="absolute inset-0 animate-spin rounded-full border-[3px] border-transparent border-t-(--accent)"
          style={{
            animationDuration: "1.1s",
          }}
        />

        {/* Reverse Arc */}
        <div
          className="absolute inset-2 animate-spin rounded-full border-[3px] border-transparent border-b-(--secondary)"
          style={{
            animationDirection: "reverse",
            animationDuration: "1.6s",
          }}
        />

        {/* Center Core */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="relative flex h-7 w-7 items-center justify-center rounded-full bg-(--primary)">
            <div className="absolute h-3 w-3 animate-ping rounded-full bg-(--accent) opacity-30" />
            <div className="h-2.5 w-2.5 rounded-full bg-white" />
          </div>
        </div>
      </div>

      <div className="text-center">
        <h3 className="font-(--font-heading) text-lg text-(--primary)">
          Intelshift
        </h3>

        <p className="mt-1 text-sm text-(--text-light)">
          {text}
        </p>
      </div>
    </div>
  );
}

export default PremiumLoader;