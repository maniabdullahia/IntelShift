import RadarChart from "../../../components/shared/charts/RadarChart.jsx";
import Button from "../../../components/ui/Button.jsx";
import {
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeadCell,
} from "../../../components/ui/Table.jsx";
import { FileText } from "lucide-react";

function ReportsAlerts() {
  const stats = [
    {
      label: "Reports Sent",
      value: "212",
      detail: "This week",
      color: "text-green-600",
    },
    {
      label: "High Impact Alerts",
      value: "86",
      detail: "Last 7 days",
      color: "text-red-600",
    },
    {
      label: "Email Delivery",
      value: "99.2%",
      detail: "Postmark / SendGrid",
      color: "text-green-600",
    },
  ];

  const deliveries = [
    {
      id: "rep_2019",
      workspace: "Acme Corp",
      type: "Weekly Report",
      recipient: "jane@acme.com",
      status: "Delivered",
      sentAt: "Today 9:00 AM",
      action: "View",
    },
    {
      id: "alert_7712",
      workspace: "ScaleOps",
      type: "Pricing Alert",
      recipient: "team@scaleops.io",
      status: "Delivered",
      sentAt: "Today 8:14 AM",
      action: "Open",
    },
    {
      id: "rep_2001",
      workspace: "BrightCart",
      type: "Weekly Report",
      recipient: "ops@brightcart.com",
      status: "Deferred",
      sentAt: "Yesterday",
      action: "Retry",
    },
  ];

  return (
    <div className="p-10 space-y-8">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="font-['DM_Serif_Display'] text-4xl font-bold text-(--primary) mb-2">
            Reports & Alerts
          </h1>
          <p className="text-(--text-light) text-base max-w-2xl">
            Admin delivery console for weekly reports, instant alerts, email
            logs, and generated report QA.
          </p>
        </div>
        <div className="flex gap-3">
          <Button title="Preview Template" variant="secondary" />
          <Button title="Generate Test Report" variant="secondary" />
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-6">
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

      {/* <BubbleChart
      title='Delivery Performance'
      // height={300}
      showGrid={true}
      datasets={[
        {
          label: 'This Week',
          data: [
            { x: 1, y: 95, r: 10 },
            { x: 2, y: 97, r: 12 },
            { x: 3, y: 92, r: 8 },
            { x: 4, y: 99, r: 15 },
            { x: 5, y: 94, r: 9 },
          ],
        },
        {
          label: 'Last Week',
          data: [
            { x: 1, y: 90, r: 8 },
            { x: 2, y: 93, r: 10 },
            { x: 3, y: 88, r: 6 },
            { x: 4, y: 95, r: 12 },
            { x: 5, y: 91, r: 7 },
          ],
        },
      ]}
      icon={MessageCircleWarning}
      
      /> */}

      {/* <CircularChart
        type="pie"
        title="Sales Distribution"
        labels={["Red", "Blue", "Yellow"]}
        data={[300, 50, 100]}
        height={300}
        showActions
        width={300}
        onDownload={() => alert("Download CSV")}
        onMenu={() => alert("Open menu")}
      /> */}

      <RadarChart
        title="Activity Overview"
        labels={[
          "Eating",
          "Drinking",
          "Sleeping",
          "Designing",
          "Coding",
          "Cycling",
          "Running",
        ]}
        datasets={[
          {
            label: "User A",
            data: [65, 59, 90, 81, 56, 55, 40],
          },  
          {
            label: "User B",
            data: [28, 48, 40, 19, 96, 27, 100],
          },
        ]}
        height={600}
        width={600}
        showActions
        onDownload={() => alert("Download CSV")}
        onMenu={() => alert("Open menu")}
        showGrid={false}
      />

      {/* Deliveries Table */}
      <Table>
        <TableHead>
          <TableRow>
            <TableHeadCell>Delivery</TableHeadCell>
            <TableHeadCell>Workspace</TableHeadCell>
            <TableHeadCell>Type</TableHeadCell>
            <TableHeadCell>Recipient</TableHeadCell>
            <TableHeadCell>Status</TableHeadCell>
            <TableHeadCell>Sent At</TableHeadCell>
            <TableHeadCell>Action</TableHeadCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {deliveries.map((delivery, idx) => (
            <TableRow key={idx}>
              <TableCell className="font-bold text-(--primary)">
                {delivery.id}
              </TableCell>
              <TableCell>{delivery.workspace}</TableCell>
              <TableCell>
                <span className="inline-flex items-center gap-1">
                  <FileText size={14} className="text-(--secondary)" />
                  {delivery.type}
                </span>
              </TableCell>
              <TableCell className="text-sm text-(--text-light)">
                {delivery.recipient}
              </TableCell>
              <TableCell>
                <span
                  className={`inline-block px-3 py-1 text-xs font-bold rounded ${
                    delivery.status === "Delivered"
                      ? "bg-green-50 text-green-600"
                      : "bg-yellow-50 text-yellow-600"
                  }`}
                >
                  {delivery.status}
                </span>
              </TableCell>
              <TableCell className="text-sm text-(--text-light)">
                {delivery.sentAt}
              </TableCell>
              <TableCell>
                <Button title={delivery.action} variant="ghost" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default ReportsAlerts;
