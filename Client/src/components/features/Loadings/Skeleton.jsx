import React from "react";

const Skeleton = ({ lines = 3, height = "12px", gap = "10px" }) => {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap }}>
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          style={{
            height,
            width: "100%",
            borderRadius: "6px",
            background: "linear-gradient(90deg, #eee, #ddd, #eee)",
            backgroundSize: "200% 100%",
            animation: "skeleton-loading 1.2s infinite",
          }}
        />
      ))}

      <style>
        {`
          @keyframes skeleton-loading {
            0% {
              background-position: 200% 0;
            }
            100% {
              background-position: -200% 0;
            }
          }
        `}
      </style>
    </div>
  );
};

export default Skeleton;