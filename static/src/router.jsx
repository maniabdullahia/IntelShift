
import { lazy, Suspense } from 'react'
import { createBrowserRouter } from 'react-router'

import Layout from './components/layout/layout'

// Home is eager — it's the landing page, load immediately
import Home from './pages/home/home'
import About from './pages/about/about'
// import PrivacyPolicy from './pages/privacy policy/privacyPolicy'

// All other pages are lazy — split into separate chunks, loaded only when visited
// const About       = lazy(() => import('./pages/about/about'))
const PrivacyPolicy = lazy(() => import('./pages/privacy policy/privacyPolicy'))
const Terms       = lazy(() => import('./pages/terms/terms'))
const Refund      = lazy(() => import('./pages/refund/refund'))
const PageNotFound = lazy(() => import('./pages/page-not-found/PageNotFound'))
const PageUnderDev = lazy(() => import('./pages/page-under-dev/PageUnderDev'))

// Minimal fallback — no spinner flash on fast connections
const PageFallback = () => (
  <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <div style={{ width: 28, height: 28, border: '3px solid #4ecdc4', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
    <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
  </div>
)

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      {
        index: true,
        element: <Home />,
      },
      {
        path: '/about',
        element: <Suspense fallback={<PageFallback />}><About /></Suspense>,
      },
      {
        path: '/privacy-policy',
        element: <Suspense fallback={<PageFallback />}><PrivacyPolicy /></Suspense>,
      },
      {
        path: '/terms',
        element: <Suspense fallback={<PageFallback />}><Terms /></Suspense>,
      },
      {
        path: '/contact',
        element: <Suspense fallback={<PageFallback />}><PageUnderDev /></Suspense>,
      },
      {
        path: '/refund',
        element: <Suspense fallback={<PageFallback />}><Refund /></Suspense>,
      }
    ],
  },
  {
    path: '*',
    element: <Suspense fallback={<PageFallback />}><PageNotFound /></Suspense>,
  }
])

export default router