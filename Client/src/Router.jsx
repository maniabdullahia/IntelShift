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


import OnBoarding from './screens/OnBoarding/OnBoarding';
import ViewCompetitor from './components/features/Competitor/ViewCompetitor';

// Core Screens
import Competitors from './screens/Main/Core/Competitors';
import Analysis from './screens/Main/Core/Analysis';
import ChangeDetailsScreen from './screens/Main/Core/ChangeDetailsScreen';
import DashboardScreen from './screens/Main/Core/DashboardScreen';
import Reports from './screens/Main/Core/Reports';

// Settings Screen
import AlertSettings from './screens/Main/Settings/AlertSettings';
import BillingAndUsage from './screens/Main/Settings/BillingAndUsage';
import ProfileSettings from './screens/Main/Settings/ProfileSettings';
import WorkspaceSetting from './screens/Main/Settings/WorkspaceSetting';

import Billing from './screens/Billing/Billing';
import Checkout from './screens/Checkout/Checkout';
import BillingSuccess from './components/features/Billing/BillingSuccess';

import Error from './components/ui/Error';

// DATA LOADERS
import packagesLoader from './components/features/DataLoaders/plan.loader';
import UserLoader from './components/features/DataLoaders/user.loader';
import OnboardingLoader from './components/features/DataLoaders/onboarding.loader';

import Intro from './screens/Intro/Intro';


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
            { path: "/dashboard", element: <DashboardScreen /> },
            {
                path: "/competitors",
                element: <Competitors />,
            },
            {
                path: "/competitors/:competitorId",
                element: <ViewCompetitor />,
            },
            {
                path: "/change_detail",
                element: <ChangeDetailsScreen />,
            },
            {
                path: "/change_detail/:domain",
                element: <ChangeDetailsScreen />,
            },
            {
                path: "/reports",
                element: <Reports />,
            },
            {
                path: "/analysis/:analysisId",
                element: <Analysis />,
            },
            {
                path: "/settings/profile",
                element: <ProfileSettings />,
            },
            {
                path: "/settings/billing",
                loader: packagesLoader,
                errorElement: <Error />,
                element: <BillingAndUsage />,
            },
            {
                path: "/settings/workspace",
                element: <WorkspaceSetting />,
            },
            {
                path: "/settings/alerts",
                element: <AlertSettings />,
            },

        ]
    },
    {
        path: "/intro",
        element: <ProtectedRoute><Intro /></ProtectedRoute>,
    },
    {
        path: '/onboarding',
        loader: OnboardingLoader,
        element: <ProtectedRoute><SetupRoute><OnBoarding /></SetupRoute></ProtectedRoute>,
    },
    {
        path: '/billing',
        loader: packagesLoader,
        element: <ProtectedRoute><SetupRoute><Billing /></SetupRoute></ProtectedRoute>,
    },
    {
        path: '/checkout',
        loader: packagesLoader,
        element: <ProtectedRoute><SetupRoute><Checkout /></SetupRoute></ProtectedRoute>,
    },
    {
        path: '/billing-success',
        element: <ProtectedRoute><SetupRoute><BillingSuccess /></SetupRoute></ProtectedRoute>,
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