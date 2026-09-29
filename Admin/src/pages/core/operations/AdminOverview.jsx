import Button from '../../../components/ui/Button.jsx';
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeadCell } from '../../../components/ui/Table.jsx';

function AdminOverview() {
  const stats = [
    { label: 'Active Workspaces', value: '248', change: '+18 this month', valueClass: 'text-(--primary)' },
    { label: 'Pages Monitored', value: '4,812', change: 'Across 1,206 competitors', valueClass: 'text-(--blue)' },
    { label: 'Crawl Success', value: '97.8%', change: 'Last 24 hours', valueClass: 'text-(--success)' },
    { label: 'AI Cost Today', value: '$184', change: '72% of daily cap', valueClass: '#d4a500' },
  ];

  const queueJobs = [
    { label: 'Crawl jobs running', desc: 'Scheduled public-page crawls currently in workers', badge: '386 active', badgeColor: 'badge-blue' },
    { label: 'Diff jobs waiting', desc: 'Snapshots waiting for text/structure comparison', badge: '74 waiting', badgeColor: 'badge-warning' },
    { label: 'AI insight jobs', desc: 'Meaningful changes above threshold', badge: '42 queued', badgeColor: 'badge-purple' },
    { label: 'Email delivery jobs', desc: 'Weekly reports and high-impact alerts', badge: '18 sending', badgeColor: 'badge-success' },
  ];

  const platformHealth = [
    { label: 'API', desc: 'p95 response: 410ms', status: 'Healthy', statusClass: 'badge-success' },
    { label: 'MongoDB Atlas', desc: 'Read/write latency normal', status: 'Healthy', statusClass: 'badge-success' },
    { label: 'Playwright Fallback', desc: 'Higher JS-heavy page volume', status: 'Watch', statusClass: 'badge-warning' },
    { label: 'Email Provider', desc: 'Delivery rate 99.2%', status: 'Healthy', statusClass: 'badge-success' },
  ];

  const recentAttention = [
    { title: 'AI spend spike detected', desc: 'Usage 42% above 7-day average', workspace: 'Acme Corp Intelligence', type: 'Cost Control', status: 'Needs Review', statusClass: 'badge-warning' },
    { title: 'Repeated crawl failures', desc: '403 responses from 12 competitor URLs', workspace: 'ScaleOps', type: 'Crawling', status: 'Failing', statusClass: 'badge-danger' },
    { title: 'Stripe webhook retry', desc: 'Payment status sync delayed', workspace: 'LaunchPilot', type: 'Billing', status: 'Retrying', statusClass: 'badge-warning' },
  ];

  const getBadgeStyles = (badgeColor) => {
    const badgeMap = {
      'badge-blue': { background: 'rgba(75, 123, 236, 0.12)', color: 'var(--blue)', padding: '4px 8px', borderRadius: '5px', fontSize: '12px', fontWeight: '600' },
      'badge-warning': { background: 'rgba(254, 211, 48, 0.18)', color: '#b88b00', padding: '4px 8px', borderRadius: '5px', fontSize: '12px', fontWeight: '600' },
      'badge-purple': { background: 'rgba(136, 84, 208, 0.12)', color: 'var(--purple)', padding: '4px 8px', borderRadius: '5px', fontSize: '12px', fontWeight: '600' },
      'badge-success': { background: 'rgba(38, 222, 129, 0.14)', color: '#16a65c', padding: '4px 8px', borderRadius: '5px', fontSize: '12px', fontWeight: '600' },
      'badge-danger': { background: 'rgba(252, 92, 101, 0.14)', color: 'var(--danger)', padding: '4px 8px', borderRadius: '5px', fontSize: '12px', fontWeight: '600' },
    };
    return badgeMap[badgeColor] || {};
  };

  return (
    <div className="page-container px-10 max-w-375 mx-auto">
      {/* Page Header */}
      <div className="page-header flex items-start justify-between gap-6 mb-8">
        <div>
          <h1 className="page-title text-[36px] mb-2 font-bold font-(DM Serif Display) text-primary">
            Admin Overview
          </h1>
          <p className="text-base max-w-195 text-(--text-light)">
            Operational control center for customers, monitoring jobs, AI usage, billing status, and platform health.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button title="Refresh" variant="ghost" />
          <Button title="Run Health Check" variant="secondary" />
        </div>
      </div>

      {/* Stats Grid - 4 columns */}
      <div className="stats-grid grid grid-cols-4 gap-6 mb-8">
        {stats.map((stat, idx) => (
          <div
            key={idx}
            className="stat-card bg-white p-6 rounded-lg border"
            style={{ border: '1px solid var(--border)' }}
          >
            <div className="text-xs font-bold uppercase mb-2 tracking-[0.6px] text-(--text-light)">
              {stat.label}
            </div>
            <div className="text-[34px] font-extrabold mb-1" style={{ color: stat.valueClass }}>
              {stat.value}
            </div>
            <div className="text-sm text-(--text-light)">
              {stat.change}
            </div>
          </div>
        ))}
      </div>

      {/* Grid 2: Left card and Right card */}
      <div className="grid-2 gap-6 mb-8 grid grid-cols-[1.2fr_0.8fr]" >
        {/* Left Card - Live Operations Queue */}
        <div className="card bg-white rounded-lg p-6 border">
          <div className="flex items-center justify-between mb-4">
            <div className="text-[18px] font-bold text-(--primary)">Live Operations Queue</div>
            <span className="py-1 px-2 text-xs font-semibold rounded-sm bg-(--bg) text-(--text-light)">
              BullMQ / Redis
            </span>
          </div>
          <div className="flex flex-col">
            {queueJobs.map((job, idx) => (
              <div key={idx} className="flex items-start justify-between gap-4 p-4 rounded-md mb-2 bg-(--bg)" style={{ marginBottom: idx === queueJobs.length - 1 ? '0' : '10px' }}>
                <div>
                  <div className="font-bold text-(--text)">{job.label}</div>
                  <div className="text-sm mt-1 text-(--text-light)">{job.desc}</div>
                </div>
                <span style={{ ...getBadgeStyles(job.badgeColor), whiteSpace: 'nowrap' }}>
                  {job.badge}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Right Card - Platform Health */}
        <div className="card bg-white rounded-lg p-6 border">
          <div className="text-[18px] font-bold mb-4 text-(--primary)">Platform Health</div>
          <div className="flex flex-col">
            {platformHealth.map((health, idx) => (
              <div key={idx} className="flex items-start justify-between gap-4 p-4 rounded-md mb-2 bg-(--bg)" style={{ marginBottom: idx === platformHealth.length - 1 ? '0' : '10px' }}>
                <div className="flex gap-3 items-start">
                  <div className="w-2.5 h-2.5 rounded-full mt-1.75 bg-(--success) shrink-0"></div>
                  <div>
                    <div className="font-bold text-(--text)">{health.label}</div>
                    <div className="text-sm mt-1 text-(--text-light)">{health.desc}</div>
                  </div>
                </div>
                <span style={{ ...getBadgeStyles(health.statusClass), whiteSpace: 'nowrap' }}>
                  {health.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Table: Recent Admin Attention */}
      <div className="table-container bg-white rounded-lg overflow-hidden border mb-8">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeadCell>Recent Admin Attention</TableHeadCell>
              <TableHeadCell>Workspace</TableHeadCell>
              <TableHeadCell>Type</TableHeadCell>
              <TableHeadCell>Status</TableHeadCell>
              <TableHeadCell>Action</TableHeadCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {recentAttention.map((item, idx) => (
              <TableRow key={idx}>
                <TableCell className="py-4.5 px-5">
                  <div className="font-bold text-(--text)">{item.title}</div>
                  <div className="text-sm mt-1 text-(--text-light)">{item.desc}</div>
                </TableCell>
                <TableCell className="py-4.5 px-5">{item.workspace}</TableCell>
                <TableCell className="py-4.5 px-5">{item.type}</TableCell>
                <TableCell className="py-4.5 px-5">
                  <span style={getBadgeStyles(item.statusClass)}>
                    {item.status}
                  </span>
                </TableCell>
                <TableCell className="py-4.5 px-5">
                  <Button title="Inspect" variant="ghost" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

export default AdminOverview;
