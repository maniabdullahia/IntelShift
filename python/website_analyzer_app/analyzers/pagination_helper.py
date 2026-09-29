"""Shared collection pagination helper.

Collection/category pages often span several paginated pages. The analyzers
extract products from the page they were handed (page 1) but need to follow the
pagination to capture the FULL catalog. This module discovers the remaining page
URLs and fetches them, so each analyzer can re-run its own product extraction on
every page and merge the results.

Kept platform-agnostic: it handles the two common URL schemes
  - WooCommerce / WordPress path style:  /shop/page/2/
  - query-param style:                   ?product-page=2 / ?paged=2 / ?page=2
by reusing the actual pagination link hrefs found in the DOM and filling any
gaps with the /page/N/ scheme.
"""

import re
import time
import requests
from urllib.parse import urljoin

# Full browser UA — a bare "Mozilla/5.0" gets 403'd by many stores' bot
# protection, which would silently truncate the catalog to page 1.
_PAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_PAGE_LINK_SELECTOR = (
    ".page-numbers a, a.page-numbers, .woocommerce-pagination a, "
    ".pagination a, [class*='pagination'] a, nav.pagination a, "
    "a[href*='/page/'], a[href*='product-page='], a[href*='paged='], "
    "a[href*='page=']"
)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def collect_page_urls(base_url, soup, max_pages=10):
    """Discover the URLs of collection pages 2..N.

    Returns (urls, within_cap). `within_cap` is False when the collection has
    more pages than `max_pages` (so callers can flag the catalog as partial).
    """
    discovered = {}
    max_n = 1

    for a in soup.select(_PAGE_LINK_SELECTOR):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue

        txt = _clean(a.get_text(" "))
        n = None
        if txt.isdigit():
            n = int(txt)
        if n is None:
            m = re.search(r"/page/(\d+)", href) or re.search(
                r"[?&](?:product-page|paged|page)=(\d+)", href
            )
            if m:
                n = int(m.group(1))

        if n and n >= 2:
            discovered[n] = urljoin(base_url, href)  # keeps query strings
            max_n = max(max_n, n)

    if max_n < 2:
        return [], True

    # Fill gaps (a page-1 pager may show "1 2 3 … 10") with the /page/N/ scheme.
    base = re.sub(r"/page/\d+/?$", "", (base_url or "").rstrip("/"))
    urls = []
    for n in range(2, min(max_n, max_pages) + 1):
        urls.append(discovered.get(n) or f"{base}/page/{n}/")

    return urls, (max_n <= max_pages)


def fetch_extra_pages(base_url, soup, extractor, max_pages=8, timeout=12, total_budget=40):
    """Fetch pages 2..N and run `extractor(html, base_url)` on each.

    `extractor` returns a list of product dicts for one page. Returns
    (extra_products, fetched_all). Stops early on a fetch error, an empty page,
    or when `total_budget` seconds have elapsed — pagination must never make a
    single page's analysis run past the analyzer's own timeout.
    """
    urls, within_cap = collect_page_urls(base_url, soup, max_pages)
    if not urls:
        return [], True

    extra = []
    fetched_all = within_cap
    start = time.monotonic()

    for url in urls:
        # Hard wall-clock budget so a slow/hanging store can't stall analysis.
        if time.monotonic() - start > total_budget:
            fetched_all = False
            break

        try:
            resp = requests.get(url, headers=_PAGE_HEADERS, timeout=timeout)
            resp.raise_for_status()
            html = resp.text
        except Exception:
            fetched_all = False
            break

        try:
            page_products = extractor(html, base_url) or []
        except Exception:
            page_products = []

        if not page_products:
            # Likely reached the end (or the scheme didn't match) — stop.
            fetched_all = False
            break

        extra.extend(page_products)

    return extra, fetched_all
