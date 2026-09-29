import React from 'react'

import Dashboard from './Core/Dashboard';
import ChangeDetails from './Core/ChangeDetails';
import Competitors from './Core/Competitors';
import Reports from './Core/Reports';
import AlertSettings from './Settings/AlertSettings';
import BillingAndUsage from './Settings/BillingAndUsage';
import WorkspaceSetting from './Settings/WorkspaceSetting';
import ProfileSettings from './Settings/ProfileSettings';
import Analysis from './Core/Analysis';

import useWindowController from '../../store/window.store';

function MainWindow() {

  const currentScreen = useWindowController((state) => state.currentScreen);

  return (
    <>
      {currentScreen === "dashboard" && <Dashboard />}
      {currentScreen === "change_detail" && <ChangeDetails />}
      {currentScreen === "competitors" && <Competitors />}
      {currentScreen === "reports" && <Reports />}
      {currentScreen === "alert_Settings" && <AlertSettings />}
      {currentScreen === "billing_usage" && <BillingAndUsage />}
      {currentScreen === "workspace_settings" && <WorkspaceSetting />}
      {currentScreen === "profile_Settings" && <ProfileSettings />}
      {currentScreen === "analysis_Screen" && <Analysis />}
    </>
  )
}

export default MainWindow
