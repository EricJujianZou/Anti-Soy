import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/**
 * Fires a GA4 page_view event on every React Router navigation.
 * Must be called from a component rendered inside <BrowserRouter>.
 */
export const usePageTracking = () => {
  const location = useLocation();

  useEffect(() => {
    if (typeof gtag === "undefined") return;
    gtag("event", "page_view", {
      page_path: location.pathname + location.search,
      page_title: document.title,
    });
  }, [location]);
};
