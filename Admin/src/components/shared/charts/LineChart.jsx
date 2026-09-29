import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";
import { Download, MoreVertical } from "lucide-react";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const THEME_COLORS = {
  primary: "#1a1a2e",
  accent: "#ff6b6b",
  secondary: "#4ecdc4",
  blue: "#4b7bec",
  purple: "#8854d0",
  orange: "#fa8231",
  success: "#26de81",
  warning: "#fed330",
  danger: "#fc5c65",
};

/**
 * Reusable Line Chart Component with Theme Support
 * @param {Object} props - Component props
 * @param {string} props.title - Chart title
 * @param {Array<string>} props.labels - X-axis labels
 * @param {Array<Object>} props.datasets - Chart datasets with label, data, and optional color
 * @param {string} props.height - Container height (default: "100%" - fills parent). Can be "400px", "50vh", etc.
 * @param {boolean} props.showLegend - Show/hide legend (default: true)
 * @param {boolean} props.showGrid - Show/hide grid (default: true)
 * @param {boolean} props.showFill - Show/hide area fill under line (default: true)
 * @param {string} props.icon - Lucide icon name for header
 * @param {boolean} props.showActions - Show action buttons (default: false)
 * @param {function} props.onDownload - Callback for download button
 * @param {function} props.onMenu - Callback for menu button
 */
export default function LineChart({
  title,
  labels = [],
  datasets = [],
  height = "100%",
  showLegend = true,
  showGrid = true,
  showFill = true,
  icon: IconComponent,
  showActions = false,
  onDownload,
  onMenu,
}) {
  // Map dataset colors to theme colors
  const processedDatasets = datasets.map((dataset) => ({
    ...dataset,
    borderColor:
      dataset.borderColor || THEME_COLORS[dataset.color] || THEME_COLORS.blue,
    backgroundColor: showFill
      ? (dataset.borderColor || THEME_COLORS[dataset.color] || THEME_COLORS.blue) +
        "20" // 20% opacity
      : "transparent",
    borderWidth: 2.5,
    fill: showFill,
    tension: 0.4,
    pointRadius: 4,
    pointBackgroundColor: dataset.borderColor || THEME_COLORS[dataset.color] || THEME_COLORS.blue,
    pointBorderColor: "#fff",
    pointBorderWidth: 2,
    pointHoverRadius: 6,
  }));

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
        titleFont: {
          family: "'DM Sans', sans-serif",
          size: 13,
          weight: "600",
        },
        bodyFont: {
          family: "'DM Sans', sans-serif",
          size: 12,
        },
        cornerRadius: 8,
        displayColors: true,
        callbacks: {
          labelColor: function (context) {
            return {
              borderColor: context.dataset.borderColor,
              backgroundColor: context.dataset.borderColor,
            };
          },
        },
      },
    },
    scales: {
      x: {
        display: true,
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
        display: true,
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

  const chartData = {
    labels,
    datasets: processedDatasets,
  };

  return (
    <div className="admin-card p-5 h-full flex flex-col" style={{ height }}>
      {/* Header */}
      {(title || showActions) && (
        <div className="mb-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            {IconComponent && <IconComponent size={20} className="text-blue-600" />}
            {title && (
              <h3 className="admin-section-title m-0">{title}</h3>
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

      {/* Chart Container */}
      <div className="flex-1 w-full min-h-0">
        {labels.length > 0 && datasets.length > 0 ? (
          <Line data={chartData} options={chartOptions} />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            <p>No data available</p>
          </div>
        )}
      </div>
    </div>
  );
}