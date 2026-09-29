
import { useEffect } from 'react';
import { Outlet, useLocation } from 'react-router';

import Header from './header';
import Footer from './footer';
import CookieBanner from '../sections/CookieBanner';

const ScrollToTop = () => {
    const { pathname } = useLocation();
    useEffect(() => {
        window.scrollTo(0, 0);
    }, [pathname]);
    return null;
};

const Layout = () => {
    return (
        <div className="flex flex-col min-h-screen">
            <ScrollToTop />
            <Header />
            <main className="flex-grow">
                <Outlet />
            </main>
            <Footer />
            <CookieBanner />
        </div>
    );
}

export default Layout;