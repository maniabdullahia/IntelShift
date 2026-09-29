
import { NavLink } from "react-router-dom"
import {
    Activity,
    Bot,
    Building2,
    CheckCircle2,
    CreditCard,
    FileText,
    LayoutDashboard,
    ShieldCheck,
    Users,
    Webhook,
    Settings
} from "lucide-react";

const Sidebar = () => {

    const navLinks = [
        {
            group: "Operations",
            links: [
                { icon: LayoutDashboard, name: "Admin Overview", path: "/" },
                { icon: Building2, name: "Workspaces", path: "/workspaces" },
                { icon: Users, name: "Users", path: "/users" },
            ]
        },
        {
            group: "Monitoring System",
            links: [
                { icon: Activity, name: "Competitor Monitor", path: "/competitors" },
                { icon: Webhook, name: "Crawl Queue", path: "/crawl-queue" },
                { icon: CheckCircle2, name: "Change Review", path: "/change-review" },
                { icon: Bot, name: "AI Usage & Costs", path: "/ai-usage" },
            ]
        },
        {
            group: "Revenue & Delivery",
            links: [
                { icon: CreditCard, name: "Billing Admin", path: "/billing" },
                { icon: FileText, name: "Reports & Alerts", path: "/reports" },
            ]
        },
        {
            group: "Platform",
            links: [
                { icon: Activity, name: "System Health", path: "/system-health" },
                { icon: ShieldCheck, name: "Audit Log", path: "/audit-log" },
                { icon: Settings, name: "Admin Settings", path: "/settings" },
            ]
        },
    ]

    return (
        <aside className="flex w-72.5 shrink-0 flex-col overflow-y-auto bg-(--primary) px-6 py-8 text-white">
            <div className="mb-11">
                <div className="font-serif text-2xl italic text-(--card)">Intelshift AI</div>
                <div className="mt-2 inline-flex w-fit items-center gap-2 rounded-full bg-white/10 px-2.5 py-1.5 text-xs text-white/75">
                    Admin Console
                </div>
            </div>

            <nav className="flex w-full flex-1 flex-col gap-6">
                {navLinks.map((navGroup, index) => (
                    <section key={index} className="mb-2">
                        <h3 className="mb-3 px-1 text-xs font-bold uppercase tracking-[1.8px] text-(--text-light)!">
                            {navGroup.group}
                        </h3>
                        <ul className="space-y-1">
                            {navGroup.links.map((link, linkIndex) => (
                                <li key={linkIndex}>
                                    <NavLink
                                        to={link.path}
                                        className={({ isActive }) =>
                                            [
                                                "flex items-center gap-3 rounded-lg px-4 py-3 text-sm transition",
                                                isActive
                                                    ? "bg-(--secondary) font-bold text-(--primary)"
                                                    : "text-white/85 hover:bg-white/10",
                                            ].join(" ")
                                        }
                                    >
                                        <span className="flex w-5 items-center justify-center">
                                            <link.icon size={16} className="shrink-0" aria-hidden="true" />
                                        </span>
                                        <span>{link.name}</span>
                                    </NavLink>
                                </li>
                            ))}
                        </ul>
                    </section>
                ))}
            </nav>
        </aside>
    )
}

export default Sidebar;