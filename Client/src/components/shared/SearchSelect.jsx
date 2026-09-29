import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

// Searchable dropdown with an optional ranked "Suggested" group at the top.
// Shared by the onboarding selection modal and the tracked-pages manager.
// Props: value, options [{value,label}], placeholder, onChange(value), suggested [value,...]
export default function SearchSelect({ value, options, placeholder, onChange, suggested = [] }) {
    const [open, setOpen] = useState(false);
    const [q, setQ] = useState("");
    const ref = useRef(null);
    useEffect(() => {
        if (!open) return;
        const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
        document.addEventListener("mousedown", h);
        return () => document.removeEventListener("mousedown", h);
    }, [open]);
    const selected = options.find((o) => o.value === value);
    const ql = q.trim().toLowerCase();
    const filtered = ql ? options.filter((o) => o.label.toLowerCase().includes(ql)) : options;
    const sugSet = new Set(suggested);
    const sugOpts = ql ? [] : suggested.map((v) => options.find((o) => o.value === v)).filter(Boolean);
    const restOpts = ql ? filtered : options.filter((o) => !sugSet.has(o.value));
    const pick = (v) => { onChange(v); setOpen(false); setQ(""); };
    const Opt = (o) => (
        <button
            key={o.value}
            type="button"
            onClick={() => pick(o.value)}
            onMouseEnter={(e) => (e.currentTarget.style.background = "color-mix(in srgb, var(--primary) 6%, transparent)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = o.value === value ? "color-mix(in srgb, var(--accent) 10%, transparent)" : "transparent")}
            className="block w-full truncate px-2.5 py-1.5 text-left text-sm"
            style={{ color: "var(--text)", background: o.value === value ? "color-mix(in srgb, var(--accent) 10%, transparent)" : "transparent" }}
        >
            {o.label}
        </button>
    );
    return (
        <div ref={ref} className="relative min-w-0 flex-1">
            <button type="button" onClick={() => { setOpen((o) => !o); setQ(""); }} className="flex h-9 w-full items-center justify-between gap-1 rounded-lg border px-2.5 text-sm" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
                <span className="truncate" style={{ color: selected ? "var(--text)" : "var(--text-light)" }}>{selected ? selected.label : placeholder}</span>
                <ChevronDown className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-light)" }} />
            </button>
            {open && (
                <div className="absolute left-0 right-0 z-30 mt-1 overflow-hidden rounded-lg border shadow-lg" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
                    <div className="p-1.5">
                        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className="w-full rounded-md border px-2 py-1.5 text-sm" style={{ borderColor: "var(--border)", background: "var(--bg)", color: "var(--text)" }} />
                    </div>
                    <div className="max-h-56 overflow-y-auto pb-1">
                        <button type="button" onClick={() => pick("")} className="block w-full truncate px-2.5 py-1.5 text-left text-sm" style={{ color: "var(--text-light)" }}>{placeholder}</button>
                        {sugOpts.length > 0 && (
                            <>
                                <p className="px-2.5 pt-1.5 pb-1 text-[10px] font-bold uppercase tracking-wide" style={{ color: "var(--secondary-dark, #0f6e56)" }}>Suggested</p>
                                {sugOpts.map(Opt)}
                                <div className="my-1 border-t" style={{ borderColor: "var(--border)" }} />
                            </>
                        )}
                        {restOpts.map(Opt)}
                        {ql && filtered.length === 0 && <p className="px-2.5 py-2 text-xs" style={{ color: "var(--text-light)" }}>No matches</p>}
                    </div>
                </div>
            )}
        </div>
    );
}
