export const navigationScreens = [
  {
    id: "dashboard",
    name: "Dashboard",
  },
  {
    id: "change_detail",
    name: "Change Detail",
  },
  {
    id: "competitors",
    name: "Competitors List",
  },
  {
    id: "reports",
    name: "Weekly Report",
  },
  {
    id: "alert_Settings",
    name: "Alert Settings",
  },
  {
    id: "billing_usage",
    name: "Billing & Usage",
  },
  {
    id: "workspace_settings",
    name: "Workspace Settings",
  },
  {
    id: "profile_Settings",
  },
  {
    id: "analysis_Screen",
  },
  {
    id: "view_competitor",
    data: null,
  },
  {
    id: "competitor_analysis",
    name: "Competitor Analysis"
  }
];

export const isValidScreen = (screenId) =>
  navigationScreens.some((screen) => screen.id === screenId);