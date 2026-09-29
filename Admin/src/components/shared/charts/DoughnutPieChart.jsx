import { Chart as ChartJS, ArcElement, Tooltip, Legend } from "chart.js";

import { Doughnut, Pie } from "react-chartjs-2";
import { Download, MoreVertical } from "lucide-react";

ChartJS.register(ArcElement, Tooltip, Legend);

const DEFAULT_COLORS = ["#4b7bec", "#26de81", "#fc5c65"];

export default function CircularChart({
  type = "doughnut",
  title,
  labels = [],
  data = [],
  height = "100%",
  showLegend = true,
  icon: IconComponent,
  showActions = false,
  cutout = "65%",
  width = "100%",
  onDownload,
  onMenu,
}) {
  const ChartComponent = type === "pie" ? Pie : Doughnut;

  const chartData = {
    labels,
    datasets: [
      {
        label: title || "Dataset",
        data,
        backgroundColor: DEFAULT_COLORS.slice(0, data.length),
        borderColor: "#ffffff",
        borderWidth: 2,
        hoverOffset: 6,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false, // 👈 IMPORTANT (like LineChart style)

    plugins: {
      legend: {
        display: showLegend,
        position: "top",
        labels: {
          usePointStyle: true,
          padding: 15,
          font: {
            family: "'DM Sans', sans-serif",
            size: 12,
            weight: "500",
          },
          color: "var(--text-light)",
        },
      },

      tooltip: {
        backgroundColor: "rgba(26, 26, 46, 0.8)",
        titleColor: "#fff",
        bodyColor: "#fff",
        borderColor: "var(--border)",
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8,
      },
    },

    cutout: type === "doughnut" ? cutout : 0,
  };

  return (
    <div
      className="admin-card p-5 h-full flex flex-col"
      style={{ height, width }}
    >
      {/* Header (SAME AS LINE CHART) */}
      {(title || showActions) && (
        <div className="mb-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            {IconComponent && (
              <IconComponent size={20} className="text-blue-600" />
            )}

            {title && <h3 className="admin-section-title m-0">{title}</h3>}
          </div>

          {showActions && (
            <div className="flex gap-2">
              {onDownload && (
                <button
                  onClick={onDownload}
                  className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                  title="Download"
                >
                  <Download size={18} className="text-text-light" />
                </button>
              )}

              {onMenu && (
                <button
                  onClick={onMenu}
                  className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                  title="More options"
                >
                  <MoreVertical size={18} className="text-text-light" />
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Chart Container (MATCH LINE CHART STRUCTURE) */}
      <div className="flex-1 w-full min-h-0">
        {labels.length > 0 && data.length > 0 ? (
          <div className="w-full h-full">
            <ChartComponent data={chartData} options={chartOptions} />
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            <p>No data available</p>
          </div>
        )}
      </div>
    </div>
  );
}
