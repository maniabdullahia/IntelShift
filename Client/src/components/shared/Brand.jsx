import logo from "../../assets/logo.png";

/**
 * IntelShift brand lockup — matched EXACTLY to the marketing site's nav:
 *   • white circular tile (44px, fully round) behind the mark
 *   • 10px gap to the wordmark
 *   • wordmark: Inter, 18px, weight 800, letter-spacing -0.03em
 *
 *   tone="light" → white wordmark (dark backgrounds: sidebar, onboarding, auth panel)
 *   tone="dark"  → navy wordmark (light backgrounds: logout header, mobile auth)
 */
export default function Brand({ tone = "dark", size = 44, showText = true, className = "" }) {
  const img = Math.round(size * 0.82); // 36px mark inside a 44px tile, like the site
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <span
        className="flex shrink-0 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-black/5"
        style={{ width: size, height: size }}
      >
        <img
          src={logo}
          alt="IntelShift AI"
          style={{ width: img, height: img }}
          className="object-contain"
        />
      </span>
      {showText && (
        <span
          className={`font-[Inter] font-extrabold whitespace-nowrap ${
            tone === "light" ? "text-white" : "text-(--primary)"
          }`}
          style={{ fontSize: "18px", letterSpacing: "-0.03em" }}
        >
          IntelShift AI
        </span>
      )}
    </span>
  );
}
