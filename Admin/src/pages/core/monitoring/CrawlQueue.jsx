import BarChart from '../../../components/shared/charts/BarChart.jsx';
import Button from '../../../components/ui/Button.jsx';
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeadCell } from '../../../components/ui/Table.jsx';
import { Activity } from 'lucide-react';
import useJobStore from '../../../store/jobs.store.js';

function CrawlQueue() {
  const stats = [
    { label: 'Queued', value: '512', detail: 'Next 30 minutes' },
    { label: 'Running', value: '86', detail: 'Across 12 workers', color: 'text-blue-600' },
    { label: 'Failed', value: '23', detail: 'Needs retry / inspect', color: 'text-red-600' },
    { label: 'Avg Duration', value: '8.4s', detail: 'Fetch + render mixed' },
  ];

  function getTag(job) {
    if (job?.queueName == 'analysis') {
      return 'P';
    } else if (job?.queueName == 'competitor') {
      return 'C';
    } else if (job?.queueName == 'workspace') {
      return 'W';
    }
    return 'Domain:';
  }
    

  function generateTagColor(tag) {
      if (tag === 'P') return 'bg-blue-50 text-blue-600 rounded-full px-2 py-1 text-xs font-bold';
      if (tag === 'C') return 'bg-green-50 text-green-600 rounded-full px-2 py-1 text-xs font-bold';
      if (tag === 'W') return 'bg-purple-50 text-purple-600 rounded-full px-2 py-1 text-xs font-bold';
      return 'bg-gray-50 text-gray-600';
  }

  function generateTagLabel(tag, job) {
      if (tag === 'P') return `Page ( ${job?.pageId?.url || 'N/A'} )`;
      if (tag === 'C') return `Competitor ( ${job?.competitorId?.name || 'N/A'} )`;
      if (tag === 'W') return `Workspace ( ${job?.workspaceId?.name || 'N/A'} )`;
      return 'Domain';
  }
  


  const jobs = useJobStore((state) => state.jobs.data); 
  console.log("🚀 ~ file: CrawlQueue.jsx:34 ~ CrawlQueue ~ jobs:", jobs) 

  return (
    <div className="p-10 space-y-8">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="font-['DM_Serif_Display'] text-4xl font-bold text-(--primary) mb-2">
            Crawl Queue
          </h1>
          <p className="text-(--text-light) text-base max-w-2xl">
            Control scheduled crawls, manual crawl triggers, failed job retries, and worker status.
          </p>
        </div>
        <div className="flex gap-3">
          <Button title="Pause Queue" variant="secondary" />
          <Button title="Retry Failed" variant="secondary" />
        </div>
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

      <BarChart
        title={'Crawl Queue Stats (Last 24 Hours)'}
        labels={['12 AM', '2 AM', '4 AM', '6 AM', '8 AM', '10 AM', '12 PM', '2 PM', '4 PM', '6 PM', '8 PM', '10 PM']}
        datasets={[
          {
            label: 'Queued',
            data: [20, 35, 40, 30, 50, 45, 60, 55, 70, 65, 80, 75],
            backgroundColor: '#4b7bec',
          },
          {
            label: 'Running',
            data: [5, 10, 15, 10, 20, 18, 25, 22, 30, 28, 35, 32],
            backgroundColor: '#26de81',
          },
          {
            label: 'Failed',
            data: [1, 2, 1, 3, 2, 4, 3, 5, 4, 6, 5, 7],
            backgroundColor: '#fc5c65',
          },
        ]}
        icon={Activity}
        showActions
        onDownload={() => console.log('Download')}
        onMenu={() => console.log('Menu')}
        showGrid={false}
      />  

      {/* Jobs Table */}
      <Table>
        <TableHead>
          <TableRow>
            {/* <TableHeadCell>Job</TableHeadCell> */}
            <TableHeadCell>Domain / Page</TableHeadCell>
            <TableHeadCell>Type</TableHeadCell>
            <TableHeadCell>Worker</TableHeadCell>
            <TableHeadCell>Status</TableHeadCell>
            <TableHeadCell>Attempts</TableHeadCell>
            <TableHeadCell>Action</TableHeadCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {jobs.map((job, idx) => (
            <TableRow key={idx}>
              {/* <TableCell className="font-bold text-(--primary)">{job?.jobName}</TableCell> */}
              <TableCell>
                <span title={generateTagLabel(getTag(job), job)} className={`font-bold text-(--text) ${generateTagColor(getTag(job))}`}>
                  {getTag(job)}
                </span>
                <span> {(job?.competitorId?.name || job?.workspaceId?.name) || 'N/A'}</span>
              </TableCell>
              <TableCell>
                <span className="inline-block px-2 py-1 text-xs font-bold bg-blue-50 text-blue-600 rounded">
                  {job?.jobName || 'N/A'}
                </span>
              </TableCell>
              <TableCell className="text-sm text-(--text-light)">{job?.queueName || 'N/A'}</TableCell>
              <TableCell>
                <span className={`inline-block px-3 py-1 text-xs font-bold rounded ${
                  job?.status === 'Running'
                    ? 'bg-blue-50 text-blue-600'
                    : job?.status === 'Complete'
                    ? 'bg-green-50 text-green-600'
                    : 'bg-red-50 text-red-600'
                }`}>
                  {job?.status || 'N/A'}
                </span>
              </TableCell>
              <TableCell className="text-(--text) font-bold">{job?.maxAttempts}</TableCell>
              <TableCell>
                <Button title="View" variant="ghost" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default CrawlQueue;
