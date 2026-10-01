// storeProfile.service.js — turns a readiness result into the stored store
// profile, and remembers it briefly so the onboarding flow (validate → create
// workspace/competitors) doesn't have to re-run minutes of browser checks.
//
// The cache is in-process memory keyed by domain. If the API restarted between
// validation and creation, the recon worker re-profiles the site in the
// background (see workers/recon.worker.js).

import Competitor from "../models/competitor.js";

const TTL_MS = 6 * 60 * 60 * 1000;
const MAX_ENTRIES = 2000;
const cache = new Map(); // domain -> { at, profile }

export const domainKey = (url) => {
    try {
        const s = String(url || "").trim();
        return new URL(/^https?:\/\//i.test(s) ? s : `https://${s}`).hostname.toLowerCase().replace(/^www\./, "");
    } catch {
        return "";
    }
};

const stageSummary = (st) => (st ? { ok: st.ok ?? null, status: st.status || (st.ok ? "ok" : st.ok === false ? "failed" : null), url: st.url || null } : null);

/** Build the persisted profile from a checkSiteReadiness() result. */
export const profileFromReadiness = (r) => {
    if (!r) return null;
    const s = r.stages || {};
    return {
        schemaVersion: "store_profile_v1",
        accessStatus: r.ok ? (r.accessStatus === "incomplete" ? "incomplete" : "complete") : "unable",
        accessIssues: r.accessIssues || [],
        journey: {
            homepage: stageSummary(s.homepage),
            collection: stageSummary(s.collection),
            product: stageSummary(s.product),
            search: stageSummary(s.search),
            cart: stageSummary(s.cart),
            checkout: stageSummary(s.checkout),
        },
        businessType: r.scale?.businessType ?? null,
        businessTypeLabel: r.scale?.businessTypeLabel ?? null,
        businessTypeConfidence: r.scale?.confidence ?? null,
        businessTypeReason: r.scale?.reason ?? null,
        scaleTier: r.scale?.scaleTier ?? null,
        market: r.market || null,
        language: r.language ? { htmlLang: r.language.htmlLang, isEnglish: r.language.isEnglish } : null,
        taxonomy: r.taxonomy || null,
        currency: r.currency || null,
        profiledAt: new Date().toISOString(),
    };
};

export const rememberProfile = (url, profile) => {
    const k = domainKey(url);
    if (!k || !profile) return;
    if (cache.size >= MAX_ENTRIES) cache.delete(cache.keys().next().value);
    cache.set(k, { at: Date.now(), profile });
};

export const getCachedProfile = (url) => {
    const hit = cache.get(domainKey(url));
    if (!hit) return null;
    if (Date.now() - hit.at > TTL_MS) {
        cache.delete(domainKey(url));
        return null;
    }
    return hit.profile;
};

/** Persist a profile on a competitor (owner or competitor). Best-effort. */
export const saveProfile = async (competitorId, profile) => {
    if (!competitorId || !profile) return;
    try {
        await Competitor.findByIdAndUpdate(competitorId, {
            $set: {
                storeProfile: profile,
                accessStatus: profile.accessStatus === "unable" ? null : profile.accessStatus,
            },
        });
    } catch (err) {
        console.warn("saveProfile failed:", err?.message || err);
    }
};

/** Attach the cached profile (if any) when creating a competitor document. */
export const profileFieldsFor = (url) => {
    const p = getCachedProfile(url);
    return p ? { storeProfile: p, accessStatus: p.accessStatus === "unable" ? null : p.accessStatus } : {};
};

export default { profileFromReadiness, rememberProfile, getCachedProfile, saveProfile, profileFieldsFor, domainKey };
