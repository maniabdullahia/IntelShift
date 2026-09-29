import { Outlet, useLocation } from "react-router-dom";

import Sidebar from "./Sidebar";
import Header from "./Header";
import TrialBanner from "../shared/TrialBanner";
import LegalLinks from "../shared/LegalLinks";

import FreshDataSync from "../features/Loadings/FreshDataSync";
import Intro from "../../screens/Intro/Intro";
import SelectionModal from "../features/Workspace/SelectionModal";

import useWindowController from "../../store/window.store";
import useModelStore from "../../store/model.store";

import useSidebarDrawer from "../../hooks/useSidebarDrawer";

import Model from "../ui/Model";


const Layout = () => {
  const location = useLocation();
  const isIntroPage = location.pathname === "/intro";
  
  const modelData = useModelStore((state) => state.modelData);

  const showSidebar = useWindowController(
    (state) => state.showSidebar
  );

  const setShowSidebar = useWindowController(
    (state) => state.setShowSidebar
  );
  const drawerRef = useSidebarDrawer({
    showSidebar,
    setShowSidebar,
  });





  // =========================
  // UI
  // =========================

  // Intro page layout (no header, sidebar, footer)
  if (isIntroPage) {
    return (
      <div className="flex h-screen relative overflow-hidden">
        <main className="flex-1 overflow-y-auto w-full">
          <Outlet />
        </main>
        {modelData && <Model />}
      </div>
    );
  }

  // Regular layout with header and sidebar
  return (
    <div className="flex h-screen relative overflow-hidden">

        <>
          {/* Desktop Sidebar */}
          <div className="hidden lg:block">
            <Sidebar />
          </div>


          {/* Main Content */}
          <main className="flex-1 overflow-y-auto">
            <TrialBanner />
            <Header />
            <Outlet />
            <footer className="mt-auto border-t border-(--border) px-4 py-5">
              <LegalLinks showCopyright />
            </footer>
          </main>


          {/* Mobile Drawer */}
          <div
            className={`fixed inset-0 z-50 lg:hidden ${showSidebar
                ? ""
                : "pointer-events-none"
              }`}
          >

            {/* Backdrop */}
            <button
              type="button"
              className={`absolute inset-0 bg-black/40 transition-opacity duration-300 ${showSidebar
                  ? "opacity-100"
                  : "opacity-0"
                }`}
              onClick={() => setShowSidebar(false)}
              aria-label="Close sidebar drawer"
              tabIndex={showSidebar ? 0 : -1}
            />


            {/* Drawer */}
            <div
              ref={drawerRef}
              role="dialog"
              aria-modal="true"
              aria-label="Sidebar menu"
              className={`absolute top-0 right-0 h-full transition-transform duration-300 ${showSidebar
                  ? "translate-x-0"
                  : "translate-x-full"
                }`}
            >

              <Sidebar
                onNavigate={() => setShowSidebar(false)}
                onClose={() => setShowSidebar(false)}
                isMobileDrawer
              />

            </div>
          </div>
          {modelData && <Model />}

          {/* Capture-first: page-selection panel — self-gates on setupStage="selecting" */}
          <SelectionModal />
        </>
    </div>
  );
};

export default Layout;