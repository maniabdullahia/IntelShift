import { useState } from "react";
import { Globe } from "lucide-react";

/* Normalise any URL/domain string to a bare hostname (no scheme, no www). */
function toHost(raw) {
  const s = String(raw || "").trim();
  if (!s) return "";
  try {
    const u = new URL(/^https?:\/\//i.test(s) ? s : `https://${s}`);
    return u.hostname.replace(/^www\./, "");
  } catch {
    return s.replace(/^https?:\/\//i, "").replace(/^www\./, "").split("/")[0];
  }
}

/**
 * Site favicon for a domain/URL — fetched client-side from Google's favicon
 * service (no crawl needed; we already have the domain). Falls back to a globe
 * glyph when there's no domain or the icon fails to load.
 *
 * `tile` wraps it on a white rounded badge (like the IntelShift logo lockup),
 * which reads cleanly on coloured/shadowed cards.
 */
export default function Favicon({ domain, size = 20, className = "", rounded = "rounded", tile = false }) {
  const host = toHost(domain);
  const [failed, setFailed] = useState(false);

  const content = (px) =>
    !host || failed ? (
      <Globe size={Math.round(px * 0.66)} className="text-(--text-light)" />
    ) : (
      <img
        src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=64`}
        alt=""
        width={px}
        height={px}
        style={{ width: px, height: px }}
        className={`object-contain ${rounded}`}
        loading="lazy"
        onError={() => setFailed(true)}
      />
    );

  if (tile) {
    return (
      <span
        className={`inline-flex shrink-0 items-center justify-center rounded-lg bg-white shadow-sm ring-1 ring-black/5 ${className}`}
        style={{ width: size, height: size }}
      >
        {content(Math.round(size * 0.66))}
      </span>
    );
  }

  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center ${className}`}
      style={{ width: size, height: size }}
    >
      {content(size)}
    </span>
  );
}
