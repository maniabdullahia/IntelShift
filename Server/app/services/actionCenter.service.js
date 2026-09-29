import Competitor from "../models/competitor.js";
import Page from "../models/page.js";

import { getWorkspacePlan } from "./page.service.js";
import { getSubscriptionByUserId } from "./subscription.service.js";
import { isHomepagePath } from "../../utils/pageMatch.js";

const normUrl = (raw) => {
  let u = String(raw || "").trim();
  if (!u) return "";
  if (!/^https?:\/\//i.test(u)) u = `https://${u}`;
  return u.replace(/\/+$/, "").toLowerCase();
};

/*
|--------------------------------------------------------------------------
| ACTION CENTER
|--------------------------------------------------------------------------
| Computes the outstanding "to-dos" for a workspace from real state — unused
| plan capacity, unmapped competitor pages, staged page changes, unused plan
| features, and any scheduled downgrade. Each item links to where it's fixed.
*/
export const getActionCenter = async (workspace) => {
  const items = [];
  const { plan } = await getWorkspacePlan(workspace);
  const planName = String(plan?.name || "").toLowerCase();

  const competitors = await Competitor.find({
    workspaceId: workspace._id,
    role: "Competitor",
  }).select("_id name domain");

  const competitorLimit = plan?.limits?.competitors ?? null;

  // 1) Unused competitor capacity
  if (competitorLimit != null && competitors.length < competitorLimit) {
    const free = competitorLimit - competitors.length;
    items.push({
      id: "add-competitors",
      type: "capacity",
      severity: "info",
      title: `Add ${free} more competitor${free === 1 ? "" : "s"}`,
      body: "You have unused competitor slots on your plan.",
      link: "/competitors",
      cta: "Add competitor",
    });
  }

  // 2) Mapping gaps — competitors with unmapped (non-homepage) pages
  for (const c of competitors) {
    const pages = await Page.find({ competitorId: c._id }).select("url mapStatus mappedOwnerUrl");
    const unmapped = pages.filter(
      (p) => !isHomepagePath(p.url) && (p.mapStatus !== "matched" || !p.mappedOwnerUrl)
    );
    if (unmapped.length) {
      items.push({
        id: `map-${c._id}`,
        type: "mapping",
        severity: "medium",
        title: `${c.name || c.domain}: ${unmapped.length} unmapped page${unmapped.length === 1 ? "" : "s"}`,
        body: "Pair these with your pages so comparisons stay like-for-like.",
        link: `/competitors/${c._id}`,
        cta: "Map pages",
      });
    }
  }

  // 2b) Owner-side gaps — YOUR pages that aren't matched on some competitor.
  // (e.g. you added a page but haven't paired it on a competitor yet.)
  const owner = await Competitor.findOne({
    workspaceId: workspace._id,
    role: "Owner",
  }).select("_id");
  if (owner && competitors.length) {
    const ownerPages = await Page.find({ competitorId: owner._id }).select("url");
    const ownerUrls = ownerPages.map((p) => p.url).filter((u) => !isHomepagePath(u));

    // Which owner URLs each competitor is mapped to.
    const compPages = await Page.find({
      competitorId: { $in: competitors.map((c) => c._id) },
      mapStatus: "matched",
    }).select("competitorId mappedOwnerUrl");

    const mappedByCompetitor = new Map(); // competitorId -> Set(ownerUrl)
    for (const p of compPages) {
      const key = String(p.competitorId);
      if (!mappedByCompetitor.has(key)) mappedByCompetitor.set(key, new Set());
      if (p.mappedOwnerUrl) mappedByCompetitor.get(key).add(normUrl(p.mappedOwnerUrl));
    }

    // An owner page needs attention if any competitor has no page mapped to it.
    const needsAttention = ownerUrls.filter((u) =>
      competitors.some((c) => !(mappedByCompetitor.get(String(c._id)) || new Set()).has(normUrl(u)))
    );

    if (needsAttention.length) {
      items.push({
        id: "owner-unmapped",
        type: "mapping",
        severity: "medium",
        title: `Your site: ${needsAttention.length} page${needsAttention.length === 1 ? "" : "s"} not matched on every competitor`,
        body: "Add or pair the matching page on each competitor so comparisons are complete.",
        link: "/settings/workspace",
        cta: "Review pages",
      });
    }
  }

  // 3) Staged page changes waiting for the next monitoring run
  if (workspace.pendingPageChanges) {
    items.push({
      id: "staged-pages",
      type: "pages",
      severity: "medium",
      title: "You have staged page changes",
      body: "They apply on your next monitoring run. Align matching pages before then.",
      link: "/settings/workspace",
      cta: "Review",
    });
  }

  // 4) Plan features worth using
  if (["growth", "pro"].includes(planName)) {
    items.push({
      id: "history-available",
      type: "feature",
      severity: "info",
      title: "Historical timeline is included on your plan",
      body: "Track price and catalog trends over time.",
      link: "/change_detail",
      cta: "View history",
    });
  }

  // 5) Scheduled downgrade
  const subscription = await getSubscriptionByUserId(workspace.ownerId);
  if (subscription?.pendingDowngrade?.planId) {
    items.push({
      id: "scheduled-downgrade",
      type: "billing",
      severity: "info",
      title: "A downgrade is scheduled",
      body: subscription.pendingDowngrade.effectiveAt
        ? `It takes effect on ${new Date(subscription.pendingDowngrade.effectiveAt).toLocaleDateString()}. Cancel anytime before then.`
        : "It takes effect at your next renewal.",
      link: "/settings/billing",
      cta: "Manage",
    });
  }

  return { items, count: items.length };
};
