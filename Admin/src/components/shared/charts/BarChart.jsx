import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar } from "react-chartjs-2";
import { Download, MoreVertical } from "lucide-react";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);


const THEME_COLORS = {
  primary: "#4b7bec",
  secondary: "#26de81",
  failure: "#fc5c65",
};

/**
 * Reusable Bar Chart Component with Theme Support
 * @param {Object} props - Component props
 * @param {string} props.title - Chart title
 * @param {Array<string>} props.labels - X-axis labels
 * @param {Array<Object>} props.datasets - Chart datasets with label, data, and optional color
 * @param {string} props.height - Container height (default: "100%" - fills parent). Can be "400px", "50vh", etc.
 * @param {boolean} props.showLegend - Show/hide legend (default: true)
 * @param {boolean} props.showGrid - Show/hide grid (default: true)
 * @param {string} props.icon - Lucide icon component for header
 * @param {boolean} props.showActions - Show action buttons (default: false)
 * @param {function} props.onDownload - Callback for download button
 * @param {function} props.onMenu - Callback for menu button
 */
export default function BarChart({
  title,
  labels = [],
  datasets = [],
  height = "100%",
  showLegend = true,
  showGrid = true,
  icon: IconComponent,
  showActions = false,
  onDownload,
  onMenu,
}) {
  // Process datasets
  const processedDatasets = datasets.map((dataset, index) => {
     const colorKey = Object.keys(THEME_COLORS)[index % Object.keys(THEME_COLORS).length];
    const color = THEME_COLORS[colorKey];
    
    return {
      ...dataset,
      backgroundColor: color + "CC", // slight transparency
      borderColor: color,
      borderWidth: 1,
      borderRadius: 8,
      borderSkipped: false,
      barThickness: 28,
      hoverBackgroundColor: color,
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
    <div className="admin-card p-5 h-full flex flex-col" style={{ height }}>
      {/* Header */}
      {(title || showActions) && (
        <div className="mb-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            {IconComponent && (
              <IconComponent size={20} className="text-blue-600" />
            )}

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

      {/* Chart */}
      <div className="flex-1 w-full min-h-0">
        {labels.length > 0 && datasets.length > 0 ? (
          <Bar data={chartData} options={chartOptions} />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            <p>No data available</p>
          </div>
        )}
      </div>
    </div>
  );
}   