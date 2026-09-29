
import Button from '../../../components/ui/Button.jsx';
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeadCell } from '../../../components/ui/Table.jsx';
import { CreditCard } from 'lucide-react';

function BillingAdmin() {
  const stats = [
    { label: 'MRR', value: '$18.4k', detail: '+9.2% this month', color: 'text-green-600' },
    { label: 'Trials', value: '31', detail: '12 ending this week' },
    { label: 'Past Due', value: '7', detail: 'Requires dunning', color: 'text-red-600' },
    { label: 'Plan Upgrades', value: '18', detail: 'Last 30 days', color: 'text-blue-600' },
  ];

  const subscriptions = [
    {
      workspace: 'Acme Corp',
      plan: 'Growth',
      status: 'Paid',
      limits: '10 competitors / 200 insights',
      invoice: '$99 paid',
      nextBilling: 'Jun 1',
      action: 'Manage',
    },
    {
      workspace: 'BrightCart',
      plan: 'Growth',
      status: 'Past Due',
      limits: '10 competitors / 200 insights',
      invoice: '$99 failed',
      nextBilling: 'Retry May 9',
      action: 'Send Reminder',
    },
    {
      workspace: 'LaunchPilot',
      plan: 'Starter',
      status: 'Trial',
      limits: '3 competitors / 40 insights',
      invoice: 'No invoice',
      nextBilling: 'Trial ends May 12',
      action: 'Extend Trial',
    },
  ];

  return (
    <div className="p-10 space-y-8">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="font-['DM_Serif_Display'] text-4xl font-bold text-(--primary) mb-2">
            Billing Admin
          </h1>
          <p className="text-(--text-light) text-base max-w-2xl">
            Stripe subscription status, plan limits, invoices, trials, upgrades, and failed payments.
          </p>
        </div>
        <Button title="Open Stripe Dashboard" variant="secondary" />
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-6">
        {stats.map((stat, idx) => (
          <div
            key={idx}
            className="bg-white border border-(--border) rounded-lg p-6 shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
          >
            <div className="text-xs font-bold uppercase tracking-wider text-(--text-light) mb-2">
              {stat.label}
            </div>
            <div className={`text-3xl font-bold mb-1 ${stat.color || 'text-(--primary)'}`}>
              {stat.value}
            </div>
            <div className="text-sm text-(--text-light)">{stat.detail}</div>
          </div>
        ))}
      </div>

      {/* Subscriptions Table */}
      <Table>
        <TableHead>
          <TableRow>
            <TableHeadCell>Workspace</TableHeadCell>
            <TableHeadCell>Plan</TableHeadCell>
            <TableHeadCell>Stripe Status</TableHeadCell>
            <TableHeadCell>Limits</TableHeadCell>
            <TableHeadCell>Invoice</TableHeadCell>
            <TableHeadCell>Next Billing</TableHeadCell>
            <TableHeadCell>Action</TableHeadCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {subscriptions.map((sub, idx) => (
            <TableRow key={idx}>
              <TableCell className="font-bold text-(--text)">{sub.workspace}</TableCell>
              <TableCell>
                <span className="inline-block px-2 py-1 text-xs font-bold bg-blue-50 text-blue-600 rounded">
                  {sub.plan}
                </span>
              </TableCell>
              <TableCell>
                <span className={`inline-block px-3 py-1 text-xs font-bold rounded ${
                  sub.status === 'Paid'
                    ? 'bg-green-50 text-green-600'
                    : sub.status === 'Past Due'
                    ? 'bg-red-50 text-red-600'
                    : 'bg-yellow-50 text-yellow-600'
                }`}>
                  {sub.status}
                </span>
              </TableCell>
              <TableCell className="text-sm text-(--text)">{sub.limits}</TableCell>
              <TableCell className="text-sm text-(--text-light)">{sub.invoice}</TableCell>
              <TableCell className="text-sm text-(--text-light)">{sub.nextBilling}</TableCell>
              <TableCell>
                <Button title={sub.action} variant="ghost" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default BillingAdmin;
