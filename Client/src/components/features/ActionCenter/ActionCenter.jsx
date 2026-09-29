import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  ChevronRight,
  ListChecks,
  Link2,
  Layers,
  Sparkles,
  CreditCard,
  LoaderCircle,
} from "lucide-react";

import { getActionCenter } from "../../../api/action.api";

const ICONS = {
  capacity: Layers,
  mapping: Link2,
  pages: ListChecks,
  feature: Sparkles,
  billing: CreditCard,
};

const TONE = {
  medium: { dot: "bg-amber-400", chip: "text-amber-700 bg-amber-50" },
  info: { dot: "bg-(--secondary)", chip: "text-(--secondary-dark) bg-[rgba(78,205,196,0.1)]" },
};

/*
| Action Center — one place that surfaces what still needs setting up: unused
| plan capacity, unmapped competitor pages, staged page changes, plan features
| to use, and any scheduled downgrade. Each item deep-links to the fix.
*/
export default function ActionCenter() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const d = await getActionCenter();
        if (alive) setItems(Array.isArray(d?.items) ? d.items : []);
      } catch {
        /* silent — panel just hides */
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-2xl border border-(--border) bg-white p-4 text-sm text-gray-500 shadow-sm">
        <LoaderCircle size={16} className="animate-spin" /> Checking your setup…
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-(--border) bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-base font-bold text-(--primary)">
          <ListChecks size={18} className="text-(--secondary)" />
          Action center
        </h3>
        <span className="rounded-full bg-[rgba(26,26,46,0.06)] px-2.5 py-0.5 text-xs font-semibold text-(--primary)">
          {items.length} to review
        </span>
      </div>

      {items.length === 0 ? (
        <div className="flex items-center gap-2 py-6 text-sm text-(--text-light)">
          <CheckCircle2 size={18} className="text-(--success)" />
          You're all set — nothing needs attention right now.
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => {
            const Icon = ICONS[item.type] || Sparkles;
            const tone = TONE[item.severity] || TONE.info;
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => item.link && navigate(item.link)}
                  className="flex w-full items-center gap-3 rounded-xl border border-gray-100 p-3 text-left transition hover:border-gray-300 hover:bg-gray-50"
                >
                  <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${tone.chip}`}>
                    <Icon size={16} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold text-(--text)">{item.title}</span>
                    <span className="block truncate text-xs text-(--text-light)">{item.body}</span>
                  </span>
                  <span className="hidden shrink-0 items-center gap-1 text-xs font-semibold text-(--secondary-dark) sm:flex">
                    {item.cta} <ChevronRight size={14} />
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
