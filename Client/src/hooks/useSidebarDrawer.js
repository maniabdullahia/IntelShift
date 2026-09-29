import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

const MENU_TOGGLE_SELECTOR = 'button[aria-label="Toggle sidebar"]';
const DESKTOP_QUERY = "(min-width: 1024px)";

const useSidebarDrawer = ({ showSidebar, setShowSidebar }) => {
  const location = useLocation();
  const drawerRef = useRef(null);
  const previousBodyOverflowRef = useRef("");
  const wasOpenRef = useRef(false);

  useEffect(() => {
    const wasOpen = wasOpenRef.current;
    wasOpenRef.current = showSidebar;

    if (!showSidebar) {
      if (wasOpen) {
        const menuToggleButton = document.querySelector(MENU_TOGGLE_SELECTOR);
        menuToggleButton?.focus();
      }

      return;
    }

    const handleEscape = (event) => {
      if (event.key === "Escape") {
        setShowSidebar(false);
      }
    };

    const handleFocusTrap = (event) => {
      if (!showSidebar || event.key !== "Tab" || !drawerRef.current) {
        return;
      }

      const focusable = drawerRef.current.querySelectorAll(FOCUSABLE_SELECTOR);

      if (!focusable.length) {
        event.preventDefault();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
        return;
      }

      if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    previousBodyOverflowRef.current = document.body.style.overflow;

    document.addEventListener("keydown", handleEscape);
    document.addEventListener("keydown", handleFocusTrap);

    document.body.style.overflow = "hidden";

    const focusable = drawerRef.current?.querySelector(FOCUSABLE_SELECTOR);
    focusable?.focus();

    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.removeEventListener("keydown", handleFocusTrap);
      document.body.style.overflow = previousBodyOverflowRef.current;
    };
  }, [showSidebar, setShowSidebar]);

  useEffect(() => {
    const mediaQuery = window.matchMedia(DESKTOP_QUERY);

    const handleDesktopChange = (event) => {
      if (event.matches) {
        setShowSidebar(false);
      }
    };

    mediaQuery.addEventListener("change", handleDesktopChange);

    return () => {
      mediaQuery.removeEventListener("change", handleDesktopChange);
    };
  }, [setShowSidebar]);

  useEffect(() => {
    setShowSidebar(false);
  }, [location.pathname, setShowSidebar]);

  return drawerRef;
};

export default useSidebarDrawer;