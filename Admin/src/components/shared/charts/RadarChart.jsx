import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from "chart.js";

import { Radar } from "react-chartjs-2";
import { Download, MoreVertical } from "lucide-react";

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
);

const THEME_COLORS = {
  primary: "#4b7bec",
  secondary: "#fc5c65",
};


export default function RadarChart({
  title,
  labels = [],
  datasets = [],
  showLegend = true,
  showGrid = true,
  icon: IconComponent,
  showActions = false,
  onDownload,
  onMenu,
}) {
  // ✅ DIRECT Chart.js compatible datasets (no artificial mapping needed)
  const processedDatasets = datasets.map((dataset, index) => {
     const colorKey = Object.keys(THEME_COLORS)[index % Object.keys(THEME_COLORS).length];
    const color = THEME_COLORS[colorKey];

    return {
      ...dataset,

      // keep Chart.js native structure
      borderColor: color,
      backgroundColor: color + "33", // 20% opacity,

      pointBackgroundColor:
        dataset.pointBackgroundColor || color,
      pointBorderColor: dataset.pointBorderColor || "#fff",
      pointHoverBackgroundColor:
        dataset.pointHoverBackgroundColor || "#fff",
      pointHoverBorderColor:
        dataset.pointHoverBorderColor || color,

      fill: dataset.fill ?? true,
      borderWidth: 2,
      pointRadius: 4,
      pointHoverRadius: 6,
    };
  });

  const chartData = {
    labels,
    datasets: processedDatasets,
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: true,

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

    scales: {
      r: {
        beginAtZero: true,

        grid: {
          display: showGrid,
          color: "var(--border)",
        },

        angleLines: {
          display: showGrid,
          color: "var(--border)",
        },

        pointLabels: {
          color: "var(--text-light)",
          font: {
            family: "'DM Sans', sans-serif",
            size: 12,
          },
        },

        ticks: {
          display: showGrid, // optional UX improvement
          backdropColor: "transparent",
          color: "var(--text-light)",
        },
      },
    },
  };

  return (
    <div className="admin-card p-5 h-full w-full flex flex-col">
      {/* Header */}
      {(title || showActions) && (
        <div className="mb-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            {IconComponent && (
              <IconComponent size={20} className="text-blue-600" />
            )}

            {title && (
              <h3 className="admin-section-title m-0">
                {title}
              </h3>
            )}
          </div>

          {showActions && (
            <div className="flex gap-2">
              {onDownload && (
                <button
                  onClick={onDownload}
                  className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <Download size={18} />
                </button>
              )}

              {onMenu && (
                <button
                  onClick={onMenu}
                  className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <MoreVertical size={18} />
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Chart */}
      <div className="flex-1 w-full min-h-0 flex items-center justify-center">
        {labels.length > 0 && datasets.length > 0 ? (
            <div className="w-full h-full">
                <Radar data={chartData} options={chartOptions} />
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