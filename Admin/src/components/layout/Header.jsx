import Input from "../ui/Input.jsx";
import Button from "../ui/Button";
import { useLocation } from "react-router-dom";

const breadcrumbByPath = {
    "/": "Admin Overview",
    "/workspaces": "Workspaces",
    "/users": "Users",
    "/workspace/": "Workspace Detail",
    "/competitors": "Competitor Monitor",
    "/crawl-queue": "Crawl Queue",
    "/change-review": "Change Review",
    "/ai-usage": "AI Usage & Costs",
    "/billing": "Billing Admin",
    "/reports": "Reports & Alerts",
    "/system-health": "System Health",
    "/audit-log": "Audit Log",
    "/settings": "Admin Settings",
};

const Header = () => {
    const location = useLocation();
    let breadcrumbTitle = breadcrumbByPath[location.pathname];
    
    if (!breadcrumbTitle && location.pathname.startsWith("/workspace/")) {
        breadcrumbTitle = "Workspace Detail";
    }
    
    breadcrumbTitle = breadcrumbTitle ?? "Admin Overview";

    return (
        <header className="sticky top-0 z-20 border-b border-(--border) bg-white px-4 py-4 sm:px-6 lg:min-h-18 lg:px-10">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <p className="text-sm text-(--text-light)">
                    Admin Console / <strong className="text-(--text)">{breadcrumbTitle}</strong>
                </p>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                    <Input
                        placeholder="Search workspace, user, domain, job ID..."
                        className="sm:w-70 lg:w-96"
                    />
                    <Button title="Export" variant="outline" className="px-5" onClick={() => {}} />
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[linear-gradient(135deg,var(--secondary),var(--accent))] text-sm font-bold text-white">
                        IA
                    </div>
                </div>
            </div>
        </header>
    )
}

export default Header;