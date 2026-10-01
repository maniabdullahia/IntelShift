/* eslint-disable react-refresh/only-export-components -- this module exports the router config, not a component; Fast Refresh doesn't apply. */
import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom'

import Layout from './components/layout/Layout';
import ProtectedRoute from './components/Route Guards/ProtectedRoute';
import PublicRoute from './components/Route Guards/PublicRoute';
import SetupRoute from './components/Route Guards/SetupRoute';

import Login from './screens/Authentication/Login';
import Signup from './screens/Authentication/Signup';
import ForgetPassword from './screens/Authentication/ForgetPassword';
import ResetPassword from './screens/Authentication/ResetPassword';
import VerifyEmail from './screens/Authentication/VerifyEmail';
import EmailVerification from './screens/Authentication/EmailVerification';
import ConfirmDeletion from './screens/Authentication/ConfirmDeletion';


const OnBoarding = lazy(() => import('./screens/OnBoarding/OnBoarding'));
const ViewCompetitor = lazy(() => import('./components/features/Competitor/ViewCompetitor'));

// Core Screens
const Competitors = lazy(() => import('./screens/Main/Core/Competitors'));
const Analysis = lazy(() => import('./screens/Main/Core/Analysis'));
const ChangeDetailsScreen = lazy(() => import('./screens/Main/Core/ChangeDetailsScreen'));
const DashboardScreen = lazy(() => import('./screens/Main/Core/DashboardScreen'));
const Reports = lazy(() => import('./screens/Main/Core/Reports'));

// Settings Screen
const AlertSettings = lazy(() => import('./screens/Main/Settings/AlertSettings'));
const BillingAndUsage = lazy(() => import('./screens/Main/Settings/BillingAndUsage'));
const ProfileSettings = lazy(() => import('./screens/Main/Settings/ProfileSettings'));
const WorkspaceSetting = lazy(() => import('./screens/Main/Settings/WorkspaceSetting'));

const Billing = lazy(() => import('./screens/Billing/Billing'));
const Checkout = lazy(() => import('./screens/Checkout/Checkout'));
const BillingSuccess = lazy(() => import('./components/features/Billing/BillingSuccess'));

import Error from './components/ui/Error';

// DATA LOADERS
import packagesLoader from './components/features/DataLoaders/plan.loader';
import UserLoader from './components/features/DataLoaders/user.loader';
import OnboardingLoader from './components/features/DataLoaders/onboarding.loader';

const Intro = lazy(() => import('./screens/Intro/Intro'));


// Route-level code splitting: heavy screens (analysis charts, onboarding,
// billing) load on demand instead of in one 1 MB+ bundle. Auth screens stay
// eager so the login page paints immediately.
const RouteFallback = () => (
    <div style={{ minHeight: '40vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-light)', fontSize: 14 }}>
        Loading…
    </div>
);
const Lazy = ({ children }) => <Suspense fallback={<RouteFallback />}>{children}</Suspense>;

const router = createBrowserRouter([
    {
        path: "/",
        loader: UserLoader,
        element: 
            <ProtectedRoute>
                <SetupRoute>
                    <Layout />
                </SetupRoute>
            </ProtectedRoute>,
        children: [
            { index: true, element: <Navigate to="/dashboard" replace /> },
            { path: "/dashboard", element: <Lazy><DashboardScreen /></Lazy> },
            {
                path: "/competitors",
                element: <Lazy><Competitors /></Lazy>,
            },
            {
                path: "/competitors/:competitorId",
                element: <Lazy><ViewCompetitor /></Lazy>,
            },
            {
                path: "/change_detail",
                element: <Lazy><ChangeDetailsScreen /></Lazy>,
            },
            {
                path: "/change_detail/:domain",
                element: <Lazy><ChangeDetailsScreen /></Lazy>,
            },
            {
                path: "/reports",
                element: <Lazy><Reports /></Lazy>,
            },
            {
                path: "/analysis/:analysisId",
                element: <Lazy><Analysis /></Lazy>,
            },
            {
                path: "/settings/profile",
                element: <Lazy><ProfileSettings /></Lazy>,
            },
            {
                path: "/settings/billing",
                loader: packagesLoader,
                errorElement: <Error />,
                element: <Lazy><BillingAndUsage /></Lazy>,
            },
            {
                path: "/settings/workspace",
                element: <Lazy><WorkspaceSetting /></Lazy>,
            },
            {
                path: "/settings/alerts",
                element: <Lazy><AlertSettings /></Lazy>,
            },

        ]
    },
    {
        path: "/intro",
        element: <ProtectedRoute><Lazy><Intro /></Lazy></ProtectedRoute>,
    },
    {
        path: '/onboarding',
        loader: OnboardingLoader,
        element: <ProtectedRoute><SetupRoute><Lazy><OnBoarding /></Lazy></SetupRoute></ProtectedRoute>,
    },
    {
        path: '/billing',
        loader: packagesLoader,
        element: <ProtectedRoute><SetupRoute><Lazy><Billing /></Lazy></SetupRoute></ProtectedRoute>,
    },
    {
        path: '/checkout',
        loader: packagesLoader,
        element: <ProtectedRoute><SetupRoute><Lazy><Checkout /></Lazy></SetupRoute></ProtectedRoute>,
    },
    {
        path: '/billing-success',
        element: <ProtectedRoute><SetupRoute><Lazy><BillingSuccess /></Lazy></SetupRoute></ProtectedRoute>,
    },
    {
        path: "/login",
        element: <PublicRoute><Login /></PublicRoute>,
    },
    {
        path: "/register",
        element: <PublicRoute><Signup /></PublicRoute>,
    },
    {
        path: "/forgot-password",
        element: <PublicRoute><ForgetPassword /></PublicRoute>,
    },
    {
        path: "/reset-password/:token",
        element: <PublicRoute><ResetPassword /></PublicRoute>,
    },
    {
        path: "/verify-email/:token",
        element: <VerifyEmail />,
    },
    {
        path: "/account/confirm-deletion/:token",
        element: <ConfirmDeletion />,
    },
    {
        path: "/email-verification",
        element: <ProtectedRoute><EmailVerification /></ProtectedRoute>,
    },
    {
        path: "*",
        element: <Error />,
    },
])

export default router