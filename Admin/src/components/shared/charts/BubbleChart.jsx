import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  Tooltip,
  Legend,
  Title,
} from "chart.js";
import { Bubble } from "react-chartjs-2";
import { Download, MoreVertical } from "lucide-react";

ChartJS.register(
  LinearScale,
  PointElement,
  Tooltip,
  Legend,
  Title
);

const THEME_COLORS = {
  primary: "#4b7bec",
  accent: "#fc5c65",
};

/**
 * Reusable Bubble Chart Component with Theme Support
 * @param {Object} props - Component props
 * @param {string} props.title - Chart title
 * @param {Array<Object>} props.datasets - Bubble datasets
 * @param {string} props.height - Container height
 * @param {boolean} props.showLegend - Show/hide legend
 * @param {boolean} props.showGrid - Show/hide grid
 * @param {React.Component} props.icon - Lucide icon component
 * @param {boolean} props.showActions - Show action buttons
 * @param {function} props.onDownload - Download callback
 * @param {function} props.onMenu - Menu callback
 *
 * Bubble Data Format:
 * datasets={[
 *   {
 *     label: "Users",
 *     color: "blue",
 *     data: [
 *       { x: 10, y: 20, r: 12 },
 *       { x: 15, y: 10, r: 8 },
 *     ]
 *   }
 * ]}
 */

export default function BubbleChart({
  title,
  datasets = [],
  height = "100%",
  showLegend = true,
  showGrid = true,
  icon: IconComponent,
  showActions = false,
  onDownload,
  onMenu,
}) {
  // Process datasets with theme colors
  const processedDatasets = datasets.map((dataset, index) => {
    const colorKey = Object.keys(THEME_COLORS)[index % Object.keys(THEME_COLORS).length];
    const color = THEME_COLORS[colorKey];
    
    return {
      ...dataset,
      backgroundColor: color + "CC",
      borderColor: color,
      borderWidth: 2,
      hoverBackgroundColor: color,
      hoverBorderColor: color,
    };
  });

  const chartData = {
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
        displayColors: true,

        callbacks: {
          label: function (context) {
            const point = context.raw;

            return `X: ${point.x}, Y: ${point.y}, Size: ${point.r}`;
          },
        },
      },
    },

    scales: {
      x: {
        grid: {
          display: showGrid,
          drawBorder: false,
          color: "var(--border)",
        },

        ticks: {
          color: "var(--text-light)",
          font: {
            family: "'DM Sans', sans-serif",
            size: 11,
          },
        },
      },

      y: {
        beginAtZero: true,

        grid: {
          display: showGrid,
          drawBorder: false,
          color: "var(--border)",
        },

        ticks: {
          color: "var(--text-light)",
          font: {
            family: "'DM Sans', sans-serif",
            size: 11,
          },
        },
      },
    },
  };

  return (
    <div
      className="admin-card p-5 h-full flex flex-col"
      style={{ height }}
    >
      {/* Header */}
      {(title || showActions) && (
        <div className="mb-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            {IconComponent && (
              <IconComponent
                size={20}
                className="text-blue-600"
              />
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
                  title="Download"
                >
                  <Download
                    size={18}
                    className="text-text-light"
                  />
                </button>
              )}

              {onMenu && (
                <button
                  onClick={onMenu}
                  className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                  title="More options"
                >
                  <MoreVertical
                    size={18}
                    className="text-text-light"
                  />
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Chart */}
      <div className="flex-1 w-full min-h-0">
        {datasets.length > 0 ? (
          <Bubble
            data={chartData}
            options={chartOptions}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            <p>No data available</p>
          </div>
        )}
      </div>
    </div>
  );
}