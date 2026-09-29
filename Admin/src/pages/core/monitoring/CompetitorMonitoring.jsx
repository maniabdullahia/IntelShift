
import Button from '../../../components/ui/Button.jsx';
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeadCell } from '../../../components/ui/Table.jsx';
import { Globe } from 'lucide-react';
import useCompetitorStore from '../../../store/competitor.store.js';

import { formatTimeAgo } from '../../../utils/time.js';


function CompetitorMonitoring() {
  // const domains = [
  //   {
  //     domain: 'notion.so',
  //     workspace: 'Acme Corp',
  //     pages: 12,
  //     crawlMethod: 'Playwright',
  //     robots: 'Allow',
  //     lastCrawl: '2 minutes ago',
  //     health: 'Healthy',
  //   },
  //   {
  //     domain: 'airtable.com',
  //     workspace: 'ScaleOps',
  //     pages: 8,
  //     crawlMethod: 'Fetch',
  //     robots: 'Allow',
  //     lastCrawl: '15 minutes ago',
  //     health: 'Healthy',
  //   },
  //   {
  //     domain: 'monday.com',
  //     workspace: 'Acme Corp',
  //     pages: 15,
  //     crawlMethod: 'Mixed',
  //     robots: 'Partial',
  //     lastCrawl: '1 hour ago',
  //     health: 'Warning',
  //   },
  // ];
  
    const competitors = useCompetitorStore((state) => state.competitors);    
  
  
  return (
    <div className="p-10 space-y-6">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="font-['DM_Serif_Display'] text-4xl font-bold text-(--primary) mb-2">
            Competitor Monitor
          </h1>
          <p className="text-(--text-light) text-base max-w-2xl">
            Admin-level overview of all monitored domains, page types, robots status, crawl method, and failure patterns.
          </p>
        </div>
        <Button title="+ Add Manual Monitor" variant="primary" />
      </div>

      {/* Domains Table */}
      <Table>
        <TableHead>
          <TableRow>
            <TableHeadCell>Domain</TableHeadCell>
            <TableHeadCell>Workspace</TableHeadCell>
            <TableHeadCell>Pages</TableHeadCell>
            <TableHeadCell>Crawl Method</TableHeadCell>
            <TableHeadCell>Robots</TableHeadCell>
            <TableHeadCell>Last Crawl</TableHeadCell>
            <TableHeadCell>Health</TableHeadCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {competitors.map((comp) => (
            <TableRow key={comp?._id}>
              <TableCell>
                <div className="flex items-center gap-2">
                  <Globe size={16} className="text-(--secondary)" />
                  <span className="font-bold text-(--text)">{comp?.domain}</span>
                </div>
              </TableCell>
              <TableCell>{comp?.workspaceId?.name || 'N/A'}</TableCell>
              <TableCell>
                <span className="font-bold text-(--primary)">{comp?.pages?.length || 'N/A'}</span>
              </TableCell>
              <TableCell>
                <span className="inline-block px-2 py-1 text-xs font-bold bg-purple-50 text-purple-600 rounded">
                  {comp?.crawlMethod || 'N/A'}
                </span>
              </TableCell>
              <TableCell>
                <span className="text-sm text-(--text)">{comp?.robots || 'N/A'}</span>
              </TableCell>
              <TableCell className="text-(--text-light) text-sm">{formatTimeAgo(comp?.lastRebuiltAt) || 'N/A'}</TableCell>
              <TableCell>
                <span className={`inline-block px-3 py-1 text-xs font-bold rounded ${
                  comp?.health === 'Healthy'
                    ? 'bg-green-50 text-green-600'
                    : comp?.health === 'Warning'
                    ? 'bg-yellow-50 text-yellow-600'
                    : 'bg-red-50 text-red-600'
                }`}>
                  {comp?.health || 'N/A'}
                </span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default CompetitorMonitoring;
