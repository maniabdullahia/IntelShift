import plan from "../models/plan.js";

// Paddle price IDs are env-driven so switching live↔sandbox is a pure .env change
// (no code edit, no live IDs committed to source). Fallbacks are the sandbox prices,
// so nothing breaks when the env vars are unset.
const PRICE = {
    starter: process.env.PADDLE_PRICE_STARTER || "pri_01ks01s3cjcg2je8fberncvaq0",
    growth: process.env.PADDLE_PRICE_GROWTH || "pri_01ks01x2k5p0jzrhn1as3mcc15",
    pro: process.env.PADDLE_PRICE_PRO || "pri_01ks01zc9vdv0w46d9d6zp2qd1",
};

const seedPlans = async () => {
    const plansToSeed = [
        {
            name: "trial",
            displayName: "Free Trial",
            description: "Track 1 competitor across up to 5 pages for 14 days, no credit card required. Test the monitoring flow, AI insights, and alerts before choosing a plan.",
            price: 0,
            priceId: "pri_free_trial",
            planReportingFrequency: "weekly",
            features: [
                "1 competitor monitored",
                "Up to 5 pages per competitor",
                "Homepage included",
                "14-day trial with 2 re-monitoring runs",
                "Auto-paired collections + add pages by URL",
                "Full AI insights",
            ],
            limits: {
                competitors: 1,
                pagesPerCompetitor: 5,
                reportFrequency: "weekly",
                pairingScope: "collections",
                allowUrlPages: true,
                completeSite: false,
                maxPageCap: 0,
                historicalTimeline: false,
            },
            isActive: true,
        },
        {
            name: "starter",
            displayName: "Starter",
            description: "For solo founders and early-stage teams monitoring a focused competitor set.",
            price: 39,
            priceId: PRICE.starter,
            planReportingFrequency: "5D",
            features: [
                "Up to 3 competitors monitored",
                "Up to 10 pages per competitor",
                "Homepage included for every competitor",
                "Checked every 5 days",
                "Auto-paired collections + add pages by URL",
                "Change alerts on detection",
                "Full AI insights",
            ],
            limits: {
                competitors: 3,
                pagesPerCompetitor: 10,
                reportFrequency: "5D",
                pairingScope: "collections",
                allowUrlPages: true,
                completeSite: false,
                maxPageCap: 0,
                historicalTimeline: false,
            },
            isActive: true,
        },
        {
            name: "growth",
            displayName: "Growth",
            description: "For growing teams that need broader competitor coverage, faster monitoring, and historical visibility.",
            price: 99,
            priceId: PRICE.growth,
            planReportingFrequency: "3D",
            features: [
                "Up to 5 competitors monitored",
                "Up to 20 pages per competitor",
                "Homepage included for every competitor",
                "Checked every 3 days",
                "Auto-paired collections & products + add pages by URL",
                "Change alerts on detection",
                "Full AI insights",
                "Historical competitor timeline",
                "Priority support",
            ],
            limits: {
                competitors: 5,
                pagesPerCompetitor: 20,
                reportFrequency: "3D",
                pairingScope: "collections_products",
                allowUrlPages: true,
                completeSite: false,
                maxPageCap: 0,
                historicalTimeline: true,
            },
            isActive: true,
        },
        {
            name: "pro",
            displayName: "Pro",
            description: "Full-site competitive intelligence — you pick the competitors, we track their entire store automatically.",
            price: 349,
            priceId: PRICE.pro,
            planReportingFrequency: "daily",
            features: [
                "Up to 10 competitors monitored",
                "Complete-site tracking — no page selection needed",
                "Homepage included for every competitor",
                "Checked daily — fastest detection",
                "Automatic collection & product pairing",
                "Change alerts on detection",
                "Full AI insights",
                "Advanced historical tracking — price & catalog trends + export",
                "Priority support",
            ],
            limits: {
                competitors: 10,
                pagesPerCompetitor: 100,
                reportFrequency: "daily",
                pairingScope: "complete_site",
                allowUrlPages: true,
                completeSite: true,
                maxPageCap: 100,
                historicalTimeline: true,
            },
            isActive: true,
        },
        {
            name: "enterprise",
            displayName: "Enterprise",
            description: "For marketplaces, mega-catalogs, and teams needing custom scale, SLAs, and support. Custom pricing — talk to us.",
            price: 0,
            priceId: "pri_enterprise_contact",
            contactSales: true,
            planReportingFrequency: "daily",
            features: [
                "Custom competitor count",
                "Full-site tracking at any scale",
                "Marketplace & mega-catalog support",
                "Custom monitoring cadence",
                "Automatic collection & product pairing",
                "Dedicated support & SLAs",
                "Custom integrations & export",
            ],
            limits: {
                competitors: 50,
                pagesPerCompetitor: 500,
                reportFrequency: "daily",
                pairingScope: "full",
                allowUrlPages: true,
                completeSite: true,
                maxPageCap: 500,
                historicalTimeline: true,
            },
            isActive: true,
        }
    ];

    // Upsert by plan name so config corrections (cadence, limits, features,
    // pricing) propagate to already-seeded databases without wiping the plan
    // documents — existing subscriptions reference these by _id, which is kept.
    for (const p of plansToSeed) {
        const before = await plan.findOne({ name: p.name }).select("planReportingFrequency");
        await plan.findOneAndUpdate(
            { name: p.name },
            { $set: p },
            { upsert: true, new: true, setDefaultsOnInsert: true }
        );
        if (before && before.planReportingFrequency !== p.planReportingFrequency) {
            console.log(`↻ Plan "${p.name}" cadence corrected: ${before.planReportingFrequency} → ${p.planReportingFrequency}`);
        }
    }
    console.log("Plans seeded/updated successfully.");
};

export default seedPlans;