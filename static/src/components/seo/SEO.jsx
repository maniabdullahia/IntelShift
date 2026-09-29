import { useEffect } from 'react';

const BASE_URL   = 'https://intelshift.ai';
const SITE_NAME  = 'IntelShift';
const OG_IMAGE   = `${BASE_URL}/og-image.png`;

/**
 * SEO component — updates <head> meta tags on every route change.
 *
 * Props:
 *  title         – page-level title (appended with "— IntelShift")
 *  description   – meta description (150-160 chars ideal)
 *  canonical     – path string, e.g. "/about"  (BASE_URL prepended)
 *  keywords      – comma-separated keyword string
 *  ogImage       – full URL to a custom OG image (falls back to OG_IMAGE)
 *  ogType        – "website" | "article" (default "website")
 *  structuredData – plain JS object — serialised to JSON-LD <script>
 *  noIndex       – true → adds <meta name="robots" content="noindex,nofollow">
 */
function SEO({
  title,
  description,
  canonical = '/',
  keywords,
  ogImage,
  ogType = 'website',
  structuredData,
  noIndex = false,
}) {
  const fullTitle = title
    ? `${title} — ${SITE_NAME}`
    : `${SITE_NAME} — AI-Powered Competitor Intelligence`;
  const canonicalUrl = `${BASE_URL}${canonical}`;
  const image = ogImage || OG_IMAGE;

  useEffect(() => {
    /* ── helpers ─────────────────────────────────────────── */
    const setMeta = (attr, val, content) => {
      let el = document.querySelector(`meta[${attr}="${val}"]`);
      if (!el) {
        el = document.createElement('meta');
        el.setAttribute(attr, val);
        document.head.appendChild(el);
      }
      el.setAttribute('content', content);
    };

    const setLink = (rel, href) => {
      let el = document.querySelector(`link[rel="${rel}"]`);
      if (!el) {
        el = document.createElement('link');
        el.rel = rel;
        document.head.appendChild(el);
      }
      el.href = href;
    };

    /* ── title ───────────────────────────────────────────── */
    document.title = fullTitle;

    /* ── standard meta ───────────────────────────────────── */
    if (description) setMeta('name', 'description', description);
    if (keywords)    setMeta('name', 'keywords', keywords);
    setMeta('name', 'robots', noIndex ? 'noindex,nofollow' : 'index,follow');

    /* ── Open Graph ───────────────────────────────────────── */
    setMeta('property', 'og:title',       fullTitle);
    setMeta('property', 'og:description', description || '');
    setMeta('property', 'og:type',        ogType);
    setMeta('property', 'og:url',         canonicalUrl);
    setMeta('property', 'og:image',       image);
    setMeta('property', 'og:image:width',  '1200');
    setMeta('property', 'og:image:height', '630');
    setMeta('property', 'og:site_name',   SITE_NAME);
    setMeta('property', 'og:locale',      'en_US');

    /* ── Twitter Card ─────────────────────────────────────── */
    setMeta('name', 'twitter:card',        'summary_large_image');
    setMeta('name', 'twitter:title',       fullTitle);
    setMeta('name', 'twitter:description', description || '');
    setMeta('name', 'twitter:image',       image);

    /* ── Canonical ────────────────────────────────────────── */
    setLink('canonical', canonicalUrl);

    /* ── JSON-LD structured data ──────────────────────────── */
    const SCRIPT_ID = 'ld-json-page';
    let ldEl = document.getElementById(SCRIPT_ID);
    if (structuredData) {
      if (!ldEl) {
        ldEl = document.createElement('script');
        ldEl.type = 'application/ld+json';
        ldEl.id   = SCRIPT_ID;
        document.head.appendChild(ldEl);
      }
      ldEl.textContent = JSON.stringify(structuredData, null, 0);
    } else if (ldEl) {
      ldEl.remove();
    }
  }, [fullTitle, description, canonicalUrl, keywords, image, ogType, structuredData, noIndex]);

  return null;
}

export default SEO;
