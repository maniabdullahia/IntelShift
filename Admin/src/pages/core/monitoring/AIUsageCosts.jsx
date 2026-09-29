import Button from '../../../components/ui/Button.jsx';
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeadCell } from '../../../components/ui/Table.jsx';
import { BarChart3 } from 'lucide-react';
import useAIUsageStore from '../../../store/usage.ai.store.js';

import { formatNumber } from '../../../utils/number.js';

import LineChart from '../../../components/shared/charts/LineChart';


function AIUsageAndCosts() {

  const usageStats = useAIUsageStore((state) => state.usage);



  const stats = [
    { label: 'Tokens Today', value: `${formatNumber(usageStats?.stats?.todayTokens)}`, detail: '+14% vs yesterday', color: 'text-blue-600' },
    { label: 'Cost Today', value: `${usageStats?.stats?.todayCost.toFixed(2)}$`, detail: '72% of cap', color: 'text-yellow-600' },
    { label: 'JSON Validation', value: `${usageStats?.stats?.validJsonPercentage}%`, detail: 'Retry policy active', color: 'text-green-600' },
    { label: 'AI Failures', value: `${usageStats?.stats?.totalFailures}`, detail: 'Mostly timeout', color: 'text-red-600' },
  ];

  const chartData = {
    labels: usageStats?.stats?.last7DaysChart?.labels || [],
    datasets: [
      {
        label: 'Daily Cost',
        data: usageStats?.stats?.last7DaysChart?.cost || [],
        color: 'blue',
      },
    ],
  }

  // const workspaces = [
  //   { name: 'ScaleOps', model: 'Primary LLM', insights: 188, tokens: '910k', cost: '$61', cap: '$120', status: 'Normal' },
  //   { name: 'Acme Corp', model: 'Primary LLM', insights: 144, tokens: '742k', cost: '$49', cap: '$80', status: 'Near Cap' },
  //   { name: 'LaunchPilot', model: 'Primary LLM', insights: 38, tokens: '126k', cost: '$8', cap: '$25', status: 'Normal' },
  // ];

  const workspaces = usageStats?.data?.map((usage) => ({
    name: usage.userId?.name || 'Unknown',
    model: 'Primary LLM',
    insights: Math.floor(usage.totalTokens / 1000), // Example: 1 insight per 1K tokens
    tokens: `${usage.totalTokens}`,
    cost: `$${usage.cost.toFixed(2)}`,
    cap: '$120',
    status: usage.cost >= 100 ? 'Near Cap' : 'Normal',
  })) || [];

  return (
    <div className="p-10 space-y-8">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="font-['DM_Serif_Display'] text-4xl font-bold text-(--primary) mb-2">
            AI Usage & Costs
          </h1>
          <p className="text-(--text-light) text-base max-w-2xl">
            Monitor model usage, tokens, provider performance, failed validations, and workspace-level cost caps.
          </p>
        </div>
        <Button title="Download Cost CSV" variant="secondary" />
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
            <div className={`text-3xl font-bold mb-1 ${stat.color}`}>
              {stat.value}
            </div>
            <div className="text-sm text-(--text-light)">{stat.detail}</div>
          </div>
        ))}
      </div>



      <LineChart
        title="Daily AI Spend (Last 7 Days)"
        labels={chartData.labels}
        datasets={chartData.datasets}
        icon={BarChart3}
        showActions
        onDownload={() => console.log("Download")}
        onMenu={() => console.log("Menu")}
        showGrid={false}
      />


      {/* Workspaces Table */}
      <Table>
        <TableHead>
          <TableRow>
            <TableHeadCell>Workspace</TableHeadCell>
            <TableHeadCell>Model</TableHeadCell>
            <TableHeadCell>Insights</TableHeadCell>
            <TableHeadCell>Tokens</TableHeadCell>
            <TableHeadCell>Cost</TableHeadCell>
            <TableHeadCell>Cap</TableHeadCell>
            <TableHeadCell>Status</TableHeadCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {workspaces.map((ws, idx) => (
            <TableRow key={idx}>
              <TableCell className="font-bold text-(--text)">{ws.name}</TableCell>
              <TableCell>{ws.model}</TableCell>
              <TableCell className="text-(--text) font-bold">{ws.insights}</TableCell>
              <TableCell className="text-(--text-light)">{ws.tokens}</TableCell>
              <TableCell className="font-bold text-(--secondary)">{ws.cost}</TableCell>
              <TableCell>{ws.cap}</TableCell>
              <TableCell>
                <span className={`inline-block px-3 py-1 text-xs font-bold rounded ${ws.status === 'Normal'
                  ? 'bg-green-50 text-green-600'
                  : 'bg-yellow-50 text-yellow-600'
                  }`}>
                  {ws.status}
                </span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default AIUsageAndCosts;
