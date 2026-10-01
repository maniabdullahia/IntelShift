import React, { useEffect, useMemo, useState } from 'react';
import { Check, X, Sparkles, ArrowLeftRight } from 'lucide-react';
import { pickSource, Card, Pill, getMatchups, getDomains, getCurrency, arr, money, cleanProductName } from './_helpers';
import { productMatches as fetchProductMatches, getProductMatchDecisions, saveProductMatchDecisions } from '../../../api/utils.api';
import useAuthStore from '../../../store/auth.store';

// Map a pipeline product to the shape the matcher expects.
const toProduct = (p) => ({
  name: cleanProductName(p?.name || p?.title),
  productUrl: p?.url || p?.productUrl || '',
  priceValue: Number(p?.price ?? p?.priceValue) || null,
});

/*
  Growth / Pro: within each MAPPED collection pair, AI picks the like-for-like
  competitor product for each of the user's leftover (unmatched) products. Analyses
  already include the AI matches; this card lets the user re-run on leftovers and
  accept / reject each suggestion. Decisions are saved to the workspace.
*/
export default function SuggestedMatches(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const matchups = getMatchups(ai, comparison, aiPayload);
  const domains = getDomains(ai, comparison, aiPayload);
  const currency = getCurrency(ai, comparison, aiPayload);

  // Collection pairs that actually have unmatched products on BOTH sides — the only
  // pairs where a suggestion is meaningful.
  const candidates = useMemo(() => arr(matchups)
    .map((m) => ({
      category: m.category || m.userCollection?.title || m.competitorCollection?.title || 'Products',
      user: arr(m.userUnmatchedProducts).map(toProduct).filter((p) => p.name),
      competitor: arr(m.competitorUnmatchedProducts).map(toProduct).filter((p) => p.name),
    }))
    .filter((c) => c.user.length && c.competitor.length), [matchups]);

  const [loading, setLoading] = useState(false);
  const [groups, setGroups] = useState(null); // [{ category, suggestions:[...] }]
  const [decisions, setDecisions] = useState({}); // key -> 'accepted' | 'rejected'
  const [error, setError] = useState('');

  // Product-level matching is a Growth+ capability (pairingScope includes products).
  // Permissive: if we can't read the plan, show it rather than hide a paid feature.
  const user = useAuthStore((s) => s.user);
  const pairingScope = user?.subscription?.planId?.limits?.pairingScope;
  const productMatchingAllowed = !pairingScope || pairingScope !== 'collections';

  // Load saved decisions once (best-effort — the card still works without them).
  useEffect(() => {
    if (!candidates.length || !productMatchingAllowed) return undefined;
    let alive = true;
    getProductMatchDecisions().then((d) => { if (alive && d) setDecisions(d); }).catch(() => {});
    return () => { alive = false; };
  }, [candidates.length, productMatchingAllowed]);

  if (!candidates.length || !productMatchingAllowed) return null;

  const keyOf = (cat, s) => `${cat}|${s.userUrl || s.userName}|${s.competitorUrl || s.competitorName}`;

  const run = async () => {
    setLoading(true); setError(''); setGroups(null);
    try {
      const out = [];
      for (const c of candidates) {
        const res = await fetchProductMatches(c.user, c.competitor, true);
        const suggestions = arr(res?.suggestions);
        if (suggestions.length) out.push({ category: c.category, suggestions, source: res?.source });
      }
      setGroups(out);
      if (!out.length) setError('No confident product matches found in the paired collections.');
    } catch (e) {
      setError(
        e?.response?.status === 403
          ? 'Product matching is available on the Growth and Pro plans.'
          : e?.response?.data?.message || e?.message || 'Could not fetch suggestions.'
      );
    } finally {
      setLoading(false);
    }
  };

  const decide = (k, v) => {
    const next = decisions[k] === v ? null : v;
    setDecisions((d) => ({ ...d, [k]: next || undefined }));
    // Persist (fire-and-forget); a failed save just means it won't survive reload.
    saveProductMatchDecisions({ [k]: next }).catch(() => {});
  };

  const gap = (a, b) => {
    if (a == null || b == null || !b) return null;
    const pct = Math.round(((a - b) / b) * 100);
    if (pct === 0) return 'same price';
    return pct > 0 ? `you +${pct}%` : `you ${pct}%`;
  };

  const acceptedCount = Object.values(decisions).filter((v) => v === 'accepted').length;

  return (
    <Card
      title="Suggested product matches"
      subtitle="AI pairs leftover products within each matched collection. Confirm the ones that are true like-for-like matches — your choices are saved."
    >
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={run}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-full bg-(--primary) px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
        >
          <Sparkles size={15} />
          {loading ? 'Finding matches…' : groups ? 'Re-run' : 'Suggest matches'}
        </button>


        {acceptedCount > 0 && (
          <Pill tone="secondary">{acceptedCount} confirmed</Pill>
        )}
      </div>

      {error && <p className="text-sm text-(--text-light)">{error}</p>}

      {groups && groups.map((g) => (
        <div key={g.category} className="mb-5">
          <div className="mb-2 flex items-center gap-2">
            <h4 className="text-sm font-semibold text-(--text)">{g.category}</h4>
            {(g.source === 'ai' || g.source === 'ai_confirmed') && <Pill tone="secondary">AI-matched</Pill>}
            <span className="text-xs text-(--text-light)">{g.suggestions.length} suggested</span>
          </div>

          <div className="space-y-2">
            {g.suggestions.map((s) => {
              const k = keyOf(g.category, s);
              const state = decisions[k];
              const g2 = gap(s.userPrice, s.competitorPrice);
              return (
                <div
                  key={k}
                  className={`rounded-xl border p-3 transition ${
                    state === 'accepted' ? 'border-(--secondary) bg-(--glow-teal)'
                    : state === 'rejected' ? 'border-(--border) bg-transparent opacity-50'
                    : 'border-(--border) bg-(--card)'
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <a href={s.userUrl || undefined} target="_blank" rel="noreferrer" className="text-sm font-medium text-(--secondary-dark) hover:underline">
                      {s.userName}
                    </a>
                    <ArrowLeftRight size={14} className="text-(--text-light)" />
                    <a href={s.competitorUrl || undefined} target="_blank" rel="noreferrer" className="text-sm font-medium text-(--accent) hover:underline">
                      {s.competitorName}
                    </a>
                  </div>

                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-(--text-light)">
                    <span>{domains.user || 'You'}: {s.userPrice != null ? money(s.userPrice, currency) : '—'}</span>
                    <span>{domains.competitor || 'Them'}: {s.competitorPrice != null ? money(s.competitorPrice, currency) : '—'}</span>
                    {g2 && <span className="font-medium">{g2}</span>}
                    {typeof s.confidence === 'number' && <span>· {Math.round(s.confidence * 100)}% match</span>}
                    {s.reason && <span>· {s.reason}</span>}
                  </div>

                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      onClick={() => decide(k, 'accepted')}
                      className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-semibold ${state === 'accepted' ? 'border-(--secondary) text-(--secondary-dark)' : 'border-(--border) text-(--text)'}`}
                    >
                      <Check size={13} /> {state === 'accepted' ? 'Confirmed' : 'Confirm'}
                    </button>
                    <button
                      type="button"
                      onClick={() => decide(k, 'rejected')}
                      className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-semibold ${state === 'rejected' ? 'border-(--accent) text-(--accent)' : 'border-(--border) text-(--text-light)'}`}
                    >
                      <X size={13} /> Not a match
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </Card>
  );
}
