import Button from '../../../components/ui/Button.jsx';
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeadCell } from '../../../components/ui/Table.jsx';
function AuditLog() {
  const logs = [
    {
      time: 'Today 10:51 AM',
      actor: 'admin@Intelshift.com',
      action: 'Impersonated workspace',
      target: 'Acme Corp',
      source: 'Admin Console',
      result: 'Allowed',
    },
    {
      time: 'Today 10:34 AM',
      actor: 'system',
      action: 'Retried failed Stripe webhook',
      target: 'BrightCart',
      source: 'billing-webhook',
      result: 'Synced',
    },
    {
      time: 'Today 9:44 AM',
      actor: 'worker-us-03',
      action: 'Generated AI insight',
      target: 'change_8821',
      source: 'BullMQ',
      result: 'Validated',
    },
    {
      time: 'Yesterday 6:12 PM',
      actor: 'admin@Intelshift.com',
      action: 'Suspended workspace',
      target: 'Test Account',
      source: 'Admin Console',
      result: 'Manual',
    },
  ];

  return (
    <div className="p-10 space-y-6">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="font-['DM_Serif_Display'] text-4xl font-bold text-(--primary) mb-2">
            Audit Log
          </h1>
          <p className="text-(--text-light) text-base max-w-2xl">
            Track critical admin and system actions for security, billing, support, and compliance.
          </p>
        </div>
        <Button title="Export Audit Log" variant="secondary" />
      </div>

      {/* Audit Log Table */}
      <Table>
        <TableHead>
          <TableRow>
            <TableHeadCell>Time</TableHeadCell>
            <TableHeadCell>Actor</TableHeadCell>
            <TableHeadCell>Action</TableHeadCell>
            <TableHeadCell>Target</TableHeadCell>
            <TableHeadCell>IP / Source</TableHeadCell>
            <TableHeadCell>Result</TableHeadCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {logs.map((log, idx) => (
            <TableRow key={idx}>
              <TableCell className="text-sm text-(--text-light)">{log.time}</TableCell>
              <TableCell>
                <span className="font-bold text-(--text)">{log.actor}</span>
              </TableCell>
              <TableCell>{log.action}</TableCell>
              <TableCell className="font-bold text-(--primary)">{log.target}</TableCell>
              <TableCell className="text-sm text-(--text-light)">{log.source}</TableCell>
              <TableCell>
                <span className="inline-block px-3 py-1 text-xs font-bold bg-green-50 text-green-600 rounded">
                  {log.result}
                </span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default AuditLog;
