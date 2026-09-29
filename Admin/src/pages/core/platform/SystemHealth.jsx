import Button from '../../../components/ui/Button.jsx';
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeadCell } from '../../../components/ui/Table.jsx';
import { CheckCircle2, Activity } from 'lucide-react';

function SystemHealth() {
  const services = [
    { name: 'Frontend / Vercel', detail: 'Build healthy • Edge responses normal', status: 'Operational' },
    { name: 'API / NestJS', detail: 'p95 410ms • error rate 0.4%', status: 'Operational' },
    { name: 'Workers', detail: 'Queue depth elevated', status: 'Degraded' },
    { name: 'MongoDB Atlas', detail: 'Indexes healthy', status: 'Operational' },
  ];

  const incidents = [
    {
      title: 'JS-heavy crawl duration spike',
      component: 'Playwright Workers',
      severity: 'Medium',
      started: 'Today 7:20 AM',
      status: 'Monitoring',
      owner: 'Backend',
    },
    {
      title: 'Email template preview timeout',
      component: 'Reports',
      severity: 'Low',
      started: 'Yesterday',
      status: 'Resolved',
      owner: 'Product',
    },
  ];

  return (
    <div className="p-10 space-y-8">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="font-['DM_Serif_Display'] text-4xl font-bold text-(--primary) mb-2">
            System Health
          </h1>
          <p className="text-(--text-light) text-base max-w-2xl">
            Technical admin dashboard for API, workers, database, Redis queue, crawler fallback, email, and error tracking.
          </p>
        </div>
        <Button title="Open Sentry" variant="secondary" />
      </div>

      {/* Two Column Grid */}
      <div className="grid grid-cols-2 gap-6">
        {/* Service Status */}
        <div className="bg-white border border-(--border) rounded-lg p-6">
          <h2 className="text-lg font-bold text-(--primary) mb-4">Service Status</h2>
          <div className="space-y-2">
            {services.map((service, idx) => (
              <div
                key={idx}
                className="p-4 bg-(--bg) rounded-lg border border-(--border) flex items-start justify-between"
              >
                <div className="flex items-start gap-3 flex-1">
                  <div className={`mt-1 ${
                    service.status === 'Operational'
                      ? 'text-green-500'
                      : service.status === 'Degraded'
                      ? 'text-yellow-500'
                      : 'text-red-500'
                  }`}>
                    <CheckCircle2 size={16} />
                  </div>
                  <div>
                    <div className="font-bold text-(--text)">{service.name}</div>
                    <div className="text-sm text-(--text-light)">{service.detail}</div>
                  </div>
                </div>
                <span className={`px-2 py-1 text-xs font-bold rounded ${
                  service.status === 'Operational'
                    ? 'bg-green-50 text-green-600'
                    : service.status === 'Degraded'
                    ? 'bg-yellow-50 text-yellow-600'
                    : 'bg-red-50 text-red-600'
                }`}>
                  {service.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Error Trends Chart */}
        <div className="bg-white border border-(--border) rounded-lg p-6">
          <h2 className="text-lg font-bold text-(--primary) mb-4">Error Trends</h2>
          <div className="h-40 bg-(--bg) rounded-lg border border-(--border) flex items-center justify-center text-(--text-light)">
            <div className="text-center">
              <BarChart3 size={32} className="mx-auto mb-2 opacity-50" />
              <span className="text-sm font-bold">Error rate / crawl failures / AI validation</span>
            </div>
          </div>
        </div>
      </div>

      {/* Incidents Table */}
      <Table>
        <TableHead>
          <TableRow>
            <TableHeadCell>Incident</TableHeadCell>
            <TableHeadCell>Component</TableHeadCell>
            <TableHeadCell>Severity</TableHeadCell>
            <TableHeadCell>Started</TableHeadCell>
            <TableHeadCell>Status</TableHeadCell>
            <TableHeadCell>Owner</TableHeadCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {incidents.map((incident, idx) => (
            <TableRow key={idx}>
              <TableCell className="font-bold text-(--text)">{incident.title}</TableCell>
              <TableCell>{incident.component}</TableCell>
              <TableCell>
                <span className={`inline-block px-2 py-1 text-xs font-bold rounded ${
                  incident.severity === 'High'
                    ? 'bg-red-50 text-red-600'
                    : incident.severity === 'Medium'
                    ? 'bg-yellow-50 text-yellow-600'
                    : 'bg-blue-50 text-blue-600'
                }`}>
                  {incident.severity}
                </span>
              </TableCell>
              <TableCell className="text-sm text-(--text-light)">{incident.started}</TableCell>
              <TableCell>
                <span className={`inline-block px-2 py-1 text-xs font-bold rounded ${
                  incident.status === 'Monitoring'
                    ? 'bg-blue-50 text-blue-600'
                    : 'bg-green-50 text-green-600'
                }`}>
                  {incident.status}
                </span>
              </TableCell>
              <TableCell>{incident.owner}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function BarChart3() {
  return (
    <Activity />
  );
}

export default SystemHealth;
