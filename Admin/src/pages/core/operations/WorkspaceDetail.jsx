import Button from "../../../components/ui/Button.jsx";

import { useParams } from "react-router-dom";
import { useState, useEffect } from "react";

import { getWorkspaceDetails } from "../../../api/workspace.api.js";

import { capitalizeFirstLetter } from "../../../utils/string.js";

function WorkspaceDetail() {
  const { workspaceId } = useParams();

  const [workspace, setWorkspace] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const workspaceData = workspace?.workspace || {};
  const competitorsData = workspaceData?.competitors?.filter(comp => comp.role === 'Competitor') || [];
  const plan = workspaceData.ownerId?.subscription?.planId || 'N/A';

  console.log("Plans: ", plan)



  useEffect(() => {
    const fetchWorkspaceDetails = async () => {
      try {
        setLoading(true);
        const data = await getWorkspaceDetails(workspaceId);
        setWorkspace(data);
      } catch (err) {
        setError(err.message || "Failed to load workspace details");
      } finally {
        setLoading(false);
      }
    };

    fetchWorkspaceDetails();
  }, [workspaceId]);

  if (loading) {
    return <div className="p-10 text-center">Loading workspace details...</div>;
  }

  if (error) {
    return <div style={{ color: 'crimson' }} className="p-10 text-center">{error}</div>;
  }

  const competitors = competitorsData.map((comp) => ({
    name: comp.name,
    pages: "Homepage, pricing, product", // Placeholder - replace with actual data if available
    frequency: "Daily", // Placeholder - replace with actual data if available
    status: "Healthy", // Placeholder - replace with actual data if available
  }));

  // const competitors = [
  //   {
  //     name: 'notion.so',
  //     pages: 'Homepage, pricing, product',
  //     frequency: 'Daily',
  //     status: 'Healthy',
  //   },
  //   {
  //     name: 'airtable.com',
  //     pages: 'Homepage, pricing, blog',
  //     frequency: 'Daily',
  //     status: '1 page slow',
  //   },
  //   {
  //     name: 'monday.com',
  //     pages: 'Homepage, pricing, product, careers',
  //     frequency: 'Weekly',
  //     status: 'Healthy',
  //   },
  // ];

  const activity = [
    { action: "Added competitor", time: "2 days ago" },
    { action: "Generated weekly report", time: "May 6" },
    { action: "High-impact alert sent", time: "May 5" },
    { action: "Plan upgraded", time: "Apr 28" },
  ];

  const getStatusBadgeStyles = (status) => {
    if (status === 'Healthy') {
      return { background: 'rgba(38, 222, 129, 0.14)', color: '#16a65c' };
    } else if (status === '1 page slow') {
      return { background: 'rgba(254, 211, 48, 0.18)', color: '#b88b00' };
    }
    return '';
  };

  return (
    <div className="p-10 max-w-375 mx-auto">
      {/* Page Header */}
      <div className="mb-8 flex items-start justify-between gap-6">
        <div>
          <h1 className="text-[36px] mb-2 text-(--primary) font-bold font-[DM Serif Display]">
            {workspaceData.name || 'Workspace Details'}
          </h1>
          <p className="text-[16px] text-(--text-light) max-w-195">
            Admin view of {workspaceData.name || 'a workspace'}: plan, competitors, monitored pages, alerts, reports, and recent activity.
          </p>
        </div>
        <div className="flex gap-3 items-center">
          <Button title="Open as User" variant="ghost" />
          <Button title="Suspend" variant="danger" />
        </div>
      </div>

      {/* Admin Note */}
      <div className="mb-6 rounded-lg border-l-4 border-l-(--secondary) bg-[rgba(78,205,196,0.10)] p-4">
        <strong className="text-(--primary)">{workspaceData.name || 'Workspace'}</strong> is on Growth plan. Competitor usage is 8/10, page usage is 23/40, and AI insights are 72% of monthly cap.
      </div>

      {/* Stats Grid - 3 columns */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        {/* Plan Card */}
        <div className="bg-white border border-(--border) rounded-lg p-6">
          <div className="text-[12px] font-bold uppercase letter-spacing-[0.6px] text-(--text-light) mb-2">
            Plan
          </div>
          <div className="text-[34px] font-bold color-(--blue) mb-1">
            {capitalizeFirstLetter(workspaceData.ownerId?.plan || 'N/A')}
          </div>
          <div className="text-[13px] text-(--text-light)">
            Renews Jun 1, 2026
          </div>
        </div>

        {/* Competitors Card */}
        <div className="bg-white border border-(--border) rounded-lg p-6">
          <div className="text-[12px] font-bold uppercase letter-spacing-[0.6px] text-(--text-light) mb-2">
            Competitors
          </div>
          <div className="text-[34px] font-bold color-(--primary) mb-1">
            8/10
          </div>
          <div className="h-2 bg-(--border) rounded-full overflow-hidden">
            <div className="h-full bg-(--secondary) rounded-full width-[80%]"></div>
          </div>
        </div>

        {/* AI Insights Card */}
        <div className="bg-white border border-(--border) rounded-lg p-6">
          <div className="text-[12px] font-bold uppercase letter-spacing-[0.6px] text-(--text-light) mb-2">
            AI Insights
          </div>
          <div className="text-[34px] font-bold text-[#d4a500] mb-1">
            144/200
          </div>
          <div className="h-2 bg-(--border) rounded-full overflow-hidden">
            <div className="h-full bg-[#d4a500] rounded-full width-[72%]"></div>
          </div>
        </div>
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1.2fr_0.8fr gap-6 mb-8">
        {/* Monitored Competitors */}
        <div className="bg-white border border-(--border) rounded-lg p-6">
          <h2 className="text-[18px] font-bold text-(--primary) mb-4">
            Monitored Competitors
          </h2>
          <div className="flex flex-col gap-2.5">
            {competitors.map((comp, idx) => (
              <div
                key={idx}
                className="flex items-start justify-between gap-4 p-4 rounded-lg bg-(--bg)"
              >
                <div>
                  <strong className="text-(--text)">{comp.name}</strong>
                  <div className="text-[13px] text-(--text-light) mt-1">
                    {comp.pages} • {comp.frequency}
                  </div>
                </div>
                <span
                className="ml-3 inline-block shrink-0 whitespace-nowrap rounded-[5px] px-2 py-1 text-[12px] font-semibold"
                  style={{
                    ...getStatusBadgeStyles(comp.status),
                  }}
                >
                  {comp.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white border border-(--border) rounded-lg p-6">
          <h2 className="text-[18px] font-bold text-(--primary) mb-4">
            Recent Activity
          </h2>
          <div className="flex flex-col gap-3">
            {activity.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between pb-3 border-b border-(--border)"
                style={{
                  paddingBottom: idx < activity.length - 1 ? '12px' : '0',
                  borderBottom: idx < activity.length - 1 ? '1px solid var(--border)' : 'none',
                }}
              >
                <span className="text-(--text) text-[14px]" >{item.action}</span>
                <strong className="text-(--text-light) text-[14px]" >{item.time}</strong>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default WorkspaceDetail;