import React from 'react';
import { Check, X, Truck, CreditCard, RotateCcw } from 'lucide-react';
import { pickSource, Card, arr } from './_helpers';

const yn = (v) => (v === true
  ? <span className="inline-flex items-center gap-1 text-(--secondary-dark)"><Check size={14} /> Yes</span>
  : v === false
    ? <span className="inline-flex items-center gap-1 text-(--text-light)"><X size={14} /> No</span>
    : <span className="text-(--text-light)">—</span>);

const val = (v) => (v ? <span className="text-(--text)">{v}</span> : <span className="text-(--text-light)">—</span>);

/*
  Shipping & Payment posture, mined from each store's auto-tracked shipping/returns/
  payment pages: free-shipping threshold, COD / bank deposit, delivery time, returns
  window. These are conversion levers a competitor can win on without touching price —
  and exactly the kind of thing nobody selects to track but everybody should see.
*/
export default function ShippingPayment(props) {
  const { comparison } = pickSource(props);
  const block = comparison?.shippingPaymentComparison || {};
  const rows = arr(block.rows).filter((r) => r && r.hasPolicyEvidence);
  if (rows.length < 1) return null;

  const domains = rows.map((r) => r.domain);
  const cell = (r, render) => <td key={r.domain} className="px-3 py-2 text-sm">{render(r)}</td>;

  const lines = [
    { icon: Truck, label: 'Free shipping', render: (r) => yn(r.freeShipping) },
    { label: 'Free-shipping threshold', render: (r) => val(r.freeShippingThreshold) },
    { label: 'Delivery time', render: (r) => val(r.deliveryTime) },
    { icon: CreditCard, label: 'Cash on delivery', render: (r) => yn(r.codAvailable) },
    { label: 'Bank deposit / transfer', render: (r) => yn(r.bankDeposit) },
    { label: 'Card payment', render: (r) => yn(r.cardPayment) },
    { label: 'Online wallet (Easypaisa, etc.)', render: (r) => yn(r.onlineWallet) },
    { icon: RotateCcw, label: 'Returns accepted', render: (r) => yn(r.returnsAllowed) },
    { label: 'Return window', render: (r) => val(r.returnWindowDays ? `${r.returnWindowDays} days` : null) },
  ];

  return (
    <Card
      title="Shipping & Payment"
      subtitle={block.description || "Fulfilment and payment posture from each store's shipping, returns and payment pages."}
    >
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-(--border)">
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-(--text-light)">Signal</th>
              {domains.map((d) => (
                <th key={d} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-(--text-light)">{d}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {lines.map((ln, i) => (
              <tr key={i} className="border-b border-(--border)/50">
                <td className="px-3 py-2 text-sm font-medium text-(--text)">
                  <span className="inline-flex items-center gap-1.5">
                    {ln.icon ? <ln.icon size={13} className="text-(--text-light)" /> : null}
                    {ln.label}
                  </span>
                </td>
                {rows.map((r) => cell(r, ln.render))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
