import { createBrowserRouter } from 'react-router-dom';

import useAuthStore from './store/auth.store.js';

// Layout
import MainLayout from './components/layout/MainLayout.jsx';

// Authentication
import Login from './pages/auth/login.jsx'
import RequestAccess from './pages/auth/RequestAccess.jsx';

// Core - Monitoring
import CompetitorMonitoring from './pages/core/monitoring/CompetitorMonitoring.jsx'
import CrawlQueue from './pages/core/monitoring/CrawlQueue.jsx';
import ChangeReview from './pages/core/monitoring/ChangeReview.jsx';
import AIUsageAndCosts from './pages/core/monitoring/AIUsageCosts.jsx';

// Core - Operations
import AdminOverview from './pages/core/operations/AdminOverview.jsx';
import Workspaces from './pages/core/operations/Workspaces.jsx';
import WorkspaceDetail from './pages/core/operations/WorkspaceDetail.jsx';
import Users from './pages/core/operations/Users.jsx';

// Core - Platform
import SystemHealth from './pages/core/platform/SystemHealth.jsx';
import AuditLog from './pages/core/platform/AuditLog.jsx';
import AdminSettings from './pages/core/platform/AdminSettings.jsx';

// Core - Revenue
import BillingAdmin from './pages/core/revenue/BillingAdmin.jsx';
import ReportsAlerts from './pages/core/revenue/ReportsAlerts.jsx';

// No Access
import NoAccess from './components/features/Access/NoAccess.jsx';


// User Management routes
import ManageUser from './components/features/user/ManageUser.jsx';

// Protected Route Component
// eslint-disable-next-line react-refresh/only-export-components
const ProtectedRoute = ({ children }) => {
    const isAuthenticated = useAuthStore(
        (state) => state.isAuthenticated
    );

    console.log('ProtectedRoute - isAuthenticated:', isAuthenticated);

    return isAuthenticated ? children : <NoAccess />;
};

const router = createBrowserRouter([
    {
        path: '/',
        element: <MainLayout />,
        children: [
            {
                index: true,
                element: (
                    <ProtectedRoute>
                        <AdminOverview />
                    </ProtectedRoute>
                ),
            },

            // Operations
            {
                path: '/workspaces',
                element: (
                    <ProtectedRoute>
                        <Workspaces />
                    </ProtectedRoute>
                ),
            },
            {
                path: '/workspace/:workspaceId',
                element: (
                    <ProtectedRoute>
                        <WorkspaceDetail />
                    </ProtectedRoute>
                ),
            },

            {
                path: '/users',
                element: (
                    <ProtectedRoute>
                        <Users />
                    </ProtectedRoute>
                ),
            },
            {
                path: '/users/:userId',
                element: (
                    <ProtectedRoute>
                        <ManageUser />
                    </ProtectedRoute>
                ),  
            },

            // Monitoring
            {
                path: '/competitors',
                element: (
                    <ProtectedRoute>
                        <CompetitorMonitoring />
                    </ProtectedRoute>
                ),
            },
            {
                path: '/crawl-queue',
                element: (
                    <ProtectedRoute>
                        <CrawlQueue />
                    </ProtectedRoute>
                ),
            },
            {
                path: '/change-review',
                element: (
                    <ProtectedRoute>
                        <ChangeReview />
                    </ProtectedRoute>
                ),
            },
            {
                path: '/ai-usage',
                element: (
                    <ProtectedRoute>
                        <AIUsageAndCosts />
                    </ProtectedRoute>
                ),
            },

            // Revenue
            {
                path: '/billing',
                element: (
                    <ProtectedRoute>
                        <BillingAdmin />
                    </ProtectedRoute>
                ),
            },
            {
                path: '/reports',
                element: (
                    <ProtectedRoute>
                        <ReportsAlerts />
                    </ProtectedRoute>
                ),
            },

            // Platform
            {
                path: '/system-health',
                element: (
                    <ProtectedRoute>
                        <SystemHealth />
                    </ProtectedRoute>
                ),
            },
            {
                path: '/audit-log',
                element: (
                    <ProtectedRoute>
                        <AuditLog />
                    </ProtectedRoute>
                ),
            },
            {
                path: '/settings',
                element: (
                    <ProtectedRoute>
                        <AdminSettings />
                    </ProtectedRoute>
                ),
            },
        ],
    },

    // Auth Routes
    {
        path: '/login',
        element: <Login />,
    },
    {
        path: '/request-access',
        element: <RequestAccess />,
    },
]);

export default router;