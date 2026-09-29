import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";

import Button from "../../../components/ui/Button.jsx";
import {
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeadCell,
} from "../../../components/ui/Table.jsx";
import Input from "../../../components/ui/Input.jsx";
import Select from "../../../components/ui/Select.jsx";
import { ChevronDown } from "lucide-react";

import { formatTimeAgo } from "../../../utils/time.js";

import useWorkspaceStore from "../../../store/workspace.store.js";

function Workspaces() {
  const [searchTerm, setSearchTerm] = useState("");
  const [planFilter, setPlanFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const workspaces = useWorkspaceStore((state) => state.workspaces);

  const navigate = useNavigate();

  const getPlanBadgeClass = (plan) => {
    switch (plan) {
      case "Starter":
        return "badge-default";
      case "Growth":
        return "badge-blue";
      case "Pro":
        return "badge-purple";
      default:
        return "badge-default";
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case "active":
        return "badge-success";
      case "trial ending":
        return "badge-warning";
      case "past due":
        return "badge-danger";
      default:
        return "badge-default";
    }
  };

  const formattedWorkspaces = useMemo(() => {
    return workspaces.map((ws) => {
      const plan = ws.ownerId?.plan || "N/A";
      const status = ws.ownerId?.subscription?.status || "N/A";
      return {
        id: ws._id,
        name: ws.name,
        owner: ws.ownerId?.email || "N/A",
        industry: ws.industry || "N/A",
        plan: ws?.ownerId?.subscription?.planId?.displayName,
        planClass: getPlanBadgeClass(plan),
        competitors:
          ws?.competitors?.filter((c) => c.role == "Competitor")?.length || 0,
        competitorsTotal:
          ws?.ownerId?.subscription?.planId?.limits?.competitors, //
        insights: 34, // Placeholder - replace with actual insights count if available
        mrr: `$${ws?.ownerId?.subscription?.planId?.price}`, // Placeholder - replace with actual MRR if available
        status: status,
        statusClass: getStatusBadgeClass(status),
        lastActivity: formatTimeAgo(ws.updatedAt), // Placeholder - replace with actual last activity data if available
      };
    });
  }, [workspaces]);

  // const allWorkspaces = [
  //   {
  //     name: 'Acme Corp Intelligence',
  //     owner: 'jane@acme.com',
  //     industry: 'SaaS • US',
  //     plan: 'Growth',
  //     planClass: 'badge-blue',
  //     competitors: 8,
  //     competitorsTotal: 10,
  //     insights: 34,
  //     mrr: '$99',
  //     status: 'Active',
  //     statusClass: 'badge-success',
  //     lastActivity: '12 minutes ago',
  //   },
  //   {
  //     name: 'ScaleOps Market Watch',
  //     owner: 'mark@scaleops.io',
  //     industry: 'Agency • UK',
  //     plan: 'Pro',
  //     planClass: 'badge-purple',
  //     competitors: 48,
  //     competitorsTotal: 50,
  //     insights: 188,
  //     mrr: '$199',
  //     status: 'Active',
  //     statusClass: 'badge-success',
  //     lastActivity: '35 minutes ago',
  //   },
  //   {
  //     name: 'LaunchPilot',
  //     owner: 'tara@launchpilot.com',
  //     industry: 'SaaS • US',
  //     plan: 'Starter',
  //     planClass: 'badge-default',
  //     competitors: 3,
  //     competitorsTotal: 3,
  //     insights: 12,
  //     mrr: '$39',
  //     status: 'Trial Ending',
  //     statusClass: 'badge-warning',
  //     lastActivity: '2 hours ago',
  //   },
  //   {
  //     name: 'BrightCart',
  //     owner: 'ops@brightcart.com',
  //     industry: 'E-commerce • CA',
  //     plan: 'Growth',
  //     planClass: 'badge-blue',
  //     competitors: 5,
  //     competitorsTotal: 10,
  //     insights: 21,
  //     mrr: '$99',
  //     status: 'Past Due',
  //     statusClass: 'badge-danger',
  //     lastActivity: '1 day ago',
  //   },
  // ];

  const getPlanBadgeStyles = (badgeClass) => {
    const badgeMap = {
      "badge-blue": {
        background: "rgba(75, 123, 236, 0.12)",
        color: "var(--blue)",
      },
      "badge-purple": {
        background: "rgba(136, 84, 208, 0.12)",
        color: "var(--purple)",
      },
      "badge-default": { background: "var(--bg)", color: "var(--text-light)" },
    };
    return badgeMap[badgeClass] || {};
  };

  const getStatusBadgeStyles = (badgeClass) => {
    const badgeMap = {
      "badge-success": {
        background: "rgba(38, 222, 129, 0.14)",
        color: "#16a65c",
      },
      "badge-warning": {
        background: "rgba(254, 211, 48, 0.18)",
        color: "#b88b00",
      },
      "badge-danger": {
        background: "rgba(252, 92, 101, 0.14)",
        color: "var(--danger)",
      },
    };
    return badgeMap[badgeClass] || {};
  };

  // Filter logic
  const filteredWorkspaces = useMemo(() => {
    return formattedWorkspaces.filter((ws) => {
      // Search filter: company name, owner email, or industry
      const searchLower = searchTerm.toLowerCase();
      const matchesSearch =
        ws.name.toLowerCase().includes(searchLower) ||
        ws.owner.toLowerCase().includes(searchLower) ||
        ws.industry.toLowerCase().includes(searchLower);

      // Plan filter
      const matchesPlan =
        planFilter === "all" ||
        (planFilter === "starter" && ws.plan === "Starter") ||
        (planFilter === "growth" && ws.plan === "Growth") ||
        (planFilter === "pro" && ws.plan === "Pro");

      "".toLowerCase;
      // Status filter
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" && ws?.status?.toLowerCase() === "active") ||
        (statusFilter === "trial" &&
          ws?.status?.toLowerCase() === "trial ending") ||
        (statusFilter === "past-due" &&
          ws?.status?.toLowerCase() === "past due");

      return matchesSearch && matchesPlan && matchesStatus;
    });
  }, [formattedWorkspaces, searchTerm, planFilter, statusFilter]);

  function handleRowClick(workspaceId) {
    navigate(`/workspace/${workspaceId}`);
  }

  return (
    <div className="page-container px-10 max-w-375 mx-auto">
      {/* Page Header */}
      <div className="page-header flex items-start justify-between gap-6 mb-8">
        <div>
          <h1 className="page-title text-[36px] mb-2 font-bold font-['DM_Serif_Display',serif] text-(--primary)">
            Workspaces
          </h1>
          <p className="text-base max-w-195 text-(--text-light)">
            Manage customer accounts, plans, limits, onboarding state, and
            workspace-level usage.
          </p>
        </div>
        <div className="flex items-center">
          <Button title="+ Create Workspace" variant="primary" />
        </div>
      </div>

      {/* Filter Bar */}
      <div className="filter-bar bg-white border border-(--border) rounded-lg p-4.5 flex gap-3 items-center mb-5.5">
        <Input
          placeholder="Search by company, domain, or owner email"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="flex-2 min-w-200 rounded-lg border border-(--border) bg-(--bg) px-3.5 py-2.75 font-['DM_Sans',sans-serif]"
        />
        <div className="relative">
          <Select
            value={planFilter}
            onChange={(e) => setPlanFilter(e.target.value)}
            options={[
              { value: "all", label: "All Plans" },
              { value: "starter", label: "Starter" },
              { value: "growth", label: "Growth" },
              { value: "pro", label: "Pro" },
            ]}
            className="min-w-42.5 rounded-lg border border-(--border) bg-(--bg) px-3.5 py-2.75 font-['DM_Sans',sans-serif]"
          />
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-(--text-light)">
            <ChevronDown size={16} />
          </span>
        </div>
        <div className="relative">
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            options={[
              { value: "all", label: "All Statuses" },
              { value: "active", label: "Active" },
              { value: "trial", label: "Trial" },
              { value: "past-due", label: "Past Due" },
            ]}
          className="min-w-42.5 rounded-lg border border-(--border) bg-(--bg) px-3.5 py-2.75 font-['DM_Sans',sans-serif]"
          />
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-(--text-light)">
            <ChevronDown size={16} />
          </span>
        </div>
        <Button title="Filter" variant="ghost" />
      </div>

      {/* Workspaces Table */}
      <div
        className="table-container bg-white rounded-lg overflow-hidden mb-8 border border-(--border)"
      >
        <Table>
          <TableHead>
            <TableRow>
              <TableHeadCell>Workspace</TableHeadCell>
              <TableHeadCell>Owner</TableHeadCell>
              <TableHeadCell>Plan</TableHeadCell>
              <TableHeadCell>Usage</TableHeadCell>
              <TableHeadCell>MRR</TableHeadCell>
              <TableHeadCell>Status</TableHeadCell>
              <TableHeadCell>Last Activity</TableHeadCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredWorkspaces.map((ws, idx) => (
              <TableRow
                key={idx}
                onClick={() => handleRowClick(ws.id)}
                className="cursor-pointer"
              >
                <TableCell className="py-4.5 px-5">
                  <div className="font-bold text-(--text)">
                    {ws.name}
                  </div>
                  <div
                    className="text-sm mt-1 text-(--text-light)"
                  >
                    {ws.industry}
                  </div>
                </TableCell>
                <TableCell
                  className="text-[14px] text-(--text) py-4.5 px-5"
                  
                >
                  {ws.owner}
                </TableCell>
                <TableCell className="py-4.5 px-5">
                  <span
                    className="inline-block px-2 py-1 rounded-sm text-xs font-semibold"
                    style={{ ...getPlanBadgeStyles(ws.planClass) }}
                  >
                    {ws.plan}
                  </span>
                </TableCell>
                <TableCell className="py-4.5 px-5">
                  <div
                    className="text-[14px] font-bold text-(--text)"
                  >
                    {ws.competitors}/{ws.competitorsTotal} competitors
                  </div>
                  <div
                    className="text-sm mt-1 text-(--text-light)"
                  >
                    {ws.insights} AI insights
                  </div>
                </TableCell>
                <TableCell
                  className="font-bold py-4.5 px-5 text-(--secondary)"
                >
                  {ws.mrr}
                </TableCell>
                <TableCell className="py-4.5 px-5">
                  <span
                    className="inline-block px-2 py-1 rounded-sm text-xs font-semibold"
                    style={{ ...getStatusBadgeStyles(ws.statusClass) }}
                  >
                    {ws.status}
                  </span>
                </TableCell>
                <TableCell
                  className="text-[14px] text-(--text-light) py-4.5 px-5"
                >
                  {ws.lastActivity}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {filteredWorkspaces.length === 0 && (
          <div
            className="p-10 text-center text-(--text-light)"
          >
            <p className="text-[14px]">
              No workspaces found matching your filters.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default Workspaces;
