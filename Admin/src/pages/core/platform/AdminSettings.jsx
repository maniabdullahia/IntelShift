import Button from '../../../components/ui/Button.jsx';
// import Input from '../../../components/ui/Input.jsx';
// import { AlertCircle } from 'lucide-react';

import AppSetting from '../../../components/features/admin settings/AppSetting.jsx';
import AdminRoles from '../../../components/features/admin settings/AdminRoles.jsx';
import CrawlRules from '../../../components/features/admin settings/CrawlRules.jsx';
import AiThresholds from '../../../components/features/admin settings/AiThresholds.jsx';
import PlanSettings from '../../../components/features/admin settings/PlanSettings.jsx';

import { useState } from 'react'

function AdminSettings() {

  const [activeTab, setActiveTab] = useState('')

  const menuItems = [
    { id: 'roles', label: 'Admin' },
    { id: 'platform', label: 'Platform Limits' },
    { id: 'app', label: 'App Settings' },
    // { id: 'crawl', label: 'Crawl Rules' },
    // { id: 'ai', label: 'AI Thresholds' },
    { id: 'billing', label: 'Billing Plans' },
  ];

  return (
    <div className="p-10 space-y-8">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="font-['DM_Serif_Display'] text-4xl font-bold text-(--primary) mb-2">
            Admin Settings
          </h1>
          <p className="text-(--text-light) text-base max-w-2xl">
            Configure platform-wide limits, crawl policy, AI thresholds, prompt versions, billing rules, and admin access.
          </p>
        </div>
        <Button title="Save Settings" variant="primary" />
      </div>



      {/* Settings Pills (TABS) */}
      <div className="flex flex-wrap gap-3">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)}
            className={`px-4 py-2 rounded-lg font-semibold text-sm transition-colors duration-300 ${activeTab === item.id ? 'bg-(--secondary) text-(--primary)' : 'bg-(--card) text-(--text-light) hover:bg-(--secondary) hover:text-(--primary)'}`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="mt-6">


        {activeTab == 'platform' && <div> Platform Tab </div>}
        {activeTab == 'app' && <AppSetting />}
        {activeTab == 'crawl' && <CrawlRules />}
        {activeTab == 'ai' && <AiThresholds />}
        {activeTab == 'billing' && <PlanSettings />}
        {activeTab == 'roles' && <AdminRoles />}
      </div>
    </div>
  );
}

export default AdminSettings;
