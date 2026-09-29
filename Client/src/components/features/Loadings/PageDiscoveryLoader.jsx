import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

/* Page-discovery is a single request (crawl + catalog fetch + structuring), so
   there are no real progress events. Instead we advance through a short script
   of status messages on a timer, so the wait feels alive and sets expectations
   ("bigger catalogs take a little longer") rather than a dead spinner. When the
   parent flips to the "structuring" phase it swaps in that final beat. */

const SCRIPTS = {
  workspace: [
    { at: 0, text: "Finding the pages on your site…" },
    { at: 4500, text: "Larger catalogs take a little longer — hang tight." },
    { at: 9500, text: "Reading your collections and products…" },
    { at: 16000, text: "Almost there — organizing everything." },
  ],
  competitor: [
    { at: 0, text: "Finding the competitor's pages…" },
    { at: 4500, text: "Larger catalogs take a little longer — hang tight." },
    { at: 9500, text: "Reading their collections and products…" },
    { at: 16000, text: "Organizing their pages so you can map them to yours." },
  ],
  structuring: [{ at: 0, text: "Structuring the pages…" }],
};

export default function PageDiscoveryLoader({ variant = "workspace" }) {
  const script = SCRIPTS[variant] || SCRIPTS.workspace;
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    setIdx(0);
    const timers = script
      .map((step, i) =>
        i === 0 ? null : setTimeout(() => setIdx(i), step.at)
      )
      .filter(Boolean);
    return () => timers.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [variant]);

  const message = script[idx]?.text || script[0].text;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 14,
        padding: "2.5rem 1.5rem",
        textAlign: "center",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        background: "var(--card)",
        fontFamily: "var(--font-sans)",
      }}
    >
      <Loader2 size={26} className="animate-spin" style={{ color: "var(--secondary-dark)" }} />

      <p
        key={message}
        style={{
          margin: 0,
          fontSize: 14.5,
          fontWeight: 600,
          color: "var(--text)",
          animation: "fadeIn 0.35s ease",
        }}
      >
        {message}
      </p>

      <p style={{ margin: 0, fontSize: 12, color: "var(--text-light)" }}>
        This runs once, while we read the site.
      </p>

      <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(3px); } to { opacity: 1; transform: none; } }`}</style>
    </div>
  );
}
