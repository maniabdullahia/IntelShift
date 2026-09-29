import React, { useState } from "react";
import { LogOut, LoaderCircle } from "lucide-react";
import { logout } from "../../../api/user.api";
import Brand from "../Brand";

const LogoutHeader = () => {
  const [loading, setLoading] = useState(false);

  const handleLogout = async () => {
    if (loading) return;

    setLoading(true);

    try {
      await logout();
    } catch (error) {
      console.error("❌ Logout failed:", error);
      setLoading(false);
    }
  };

  return (
    <div className="flex justify-between items-center px-4 py-2 bg-(--background) border-b border-(--border)">
      <Brand tone="dark" />
      <button
        type="button"
        onClick={handleLogout}
        disabled={loading}
        className="group inline-flex items-center justify-center gap-2 rounded-lg border border-(--border) bg-linear-to-r from-(--primary) to-[rgba(26,26,46,0.95)] px-4 py-2.5 text-sm font-semibold text-white shadow-(--shadow-sm) transition-all duration-200 hover:-translate-y-0.5 hover:shadow-(--shadow-md) focus:outline-none focus:ring-2 focus:ring-(--secondary)/40 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? (
          <>
            <LoaderCircle size={16} className="animate-spin" />
            <span>Logging out...</span>
          </>
        ) : (
          <>
            <LogOut
              size={16}
              className="transition-transform duration-200 group-hover:translate-x-0.5"
            />
            <span>Logout</span>
          </>
        )}
      </button>
    </div>
  );
};

export default LogoutHeader;
