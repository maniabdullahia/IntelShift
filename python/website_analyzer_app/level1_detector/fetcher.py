import re
import sys as _sys
import asyncio as _asyncio
import requests
import cloudscraper

from .net_guard import is_public_url, blocked_result, browser_slot


def _ensure_subprocess_capable_loop_policy():
    """Playwright launches the browser as a subprocess. On Windows, uvicorn
    installs the WindowsSelectorEventLoopPolicy, whose event loop raises
    NotImplementedError on subprocess creation — so every sync_playwright()
    call here was crashing before it hit the network. Switching to the Proactor
    policy makes NEW loops (the ones Playwright creates in the threadpool
    worker) subprocess-capable, without disturbing uvicorn's already-running
    loop. No-op on non-Windows platforms."""
    if _sys.platform != "win32":
        return
    try:
        ProactorPolicy = getattr(_asyncio, "WindowsProactorEventLoopPolicy", None)
        if ProactorPolicy is None:
            return
        if not isinstance(_asyncio.get_event_loop_policy(), ProactorPolicy):
            _asyncio.set_event_loop_policy(ProactorPolicy())
    except Exception:
        pass


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


BLOCKED_STATUS_CODES = {401, 403, 418, 429, 451, 503}


BLOCKED_TEXT_MARKERS = [
    "access denied",
    "forbidden",
    "verify you are human",
    "checking your browser",
    "just a moment",
    "captcha",
    "cf-chl",
    "cloudflare",
    "akamai",
    "perimeterx",
    "datadome",
    "bot protection",
    "request blocked",
]


def is_html_blocked_or_empty(html, status_code=None):
    if status_code in BLOCKED_STATUS_CODES:
        return True

    if not html:
        return True

    html_l = html.lower()

    body_indicators = [
        "<body",
        "__next_data__",
        "__nuxt__",
        "root",
        "app",
        "react",
        "hydration",
    ]

    has_body_signal = any(x in html_l for x in body_indicators)

    if len(html_l.strip()) < 1500 and not has_body_signal:
        return True

    # Scan for challenge markers in VISIBLE content only. JS-heavy platforms
    # (Wix especially) legitimately ship words like "captcha", "cloudflare",
    # "forbidden" inside their script bundles — counting raw HTML classified
    # EVERY Wix page as blocked, nulling requests/cloudscraper/Playwright and
    # forcing the whole platform through Jina/OpenAI fallbacks.
    _visible = re.sub(r"<script\b.*?</script>", " ", html_l, flags=re.S)
    _visible = re.sub(r"<style\b.*?</style>", " ", _visible, flags=re.S)
    _visible_text = re.sub(r"<[^>]+>", " ", _visible)
    _visible_text = re.sub(r"\s+", " ", _visible_text).strip()

    blocked_hits = sum(
        1 for marker in BLOCKED_TEXT_MARKERS
        if marker in _visible
    )

    # Genuine challenge pages ("Just a moment…", "Verify you are human") have
    # tiny visible text. A content-rich page mentioning these words is fine.
    if blocked_hits >= 2 and len(_visible_text) < 3000:
        return True

    if "<body" not in html_l:
        return True

    return False


def should_force_playwright(url, html, response_headers=None):
    url_l = (url or "").lower()
    html_l = (html or "").lower()

    # Homepages are the most JS-heavy page (carousels, chat/WhatsApp widgets,
    # banners, lazy sections) and are fetched only ONCE per competitor — always
    # render them in a real browser so client-side content is captured, not just
    # the server-rendered shell. This is what makes CTAs/widgets appear.
    try:
        from urllib.parse import urlparse as _urlparse
        _home_path = (_urlparse(url_l).path or "").strip("/")
    except Exception:
        _home_path = "?"
    if _home_path in ("", "home", "index", "index.html"):
        return True

    pricing_url = (
        "/pricing" in url_l
        or "/plans" in url_l
        or "pricing" in url_l
        or "plans" in url_l
    )

    if pricing_url:
        return True

    # If the server advertises Next.js, always use Playwright so we can
    # extract __NEXT_DATA__ from the JS runtime (requests won't execute JS).
    if response_headers:
        powered_by = str(
            response_headers.get("X-Powered-By", "")
            or response_headers.get("x-powered-by", "")
            or ""
        ).lower()
        if "next.js" in powered_by:
            return True

    js_heavy_signals = [
        "__next_data__",
        "__nuxt__",
        "window.__",
        "id=\"root\"",
        "id=\"app\"",
        "data-reactroot",
    ]

    if any(x in html_l for x in js_heavy_signals):
        visible_text_len = len(
            html_l.replace("<script", " ")
                  .replace("</script>", " ")
                  .replace("<style", " ")
                  .replace("</style>", " ")
        )

        if visible_text_len < 8000:
            return True

    # Framework-agnostic hydration-shell heuristic. Magento PWA (Louboutin),
    # custom SPAs (chipotle.com, claude.ai) don't carry the Next/React markers
    # above, but their requests-level HTML is a large JS payload with almost
    # no visible text. Analyzing that shell misclassifies everything as
    # "general" (homepage score 0, collection score 2). Render it properly.
    # Thresholds widened (10KB / 1800 chars) to catch PARTIAL renders too —
    # cases where requests got some markup but the real content is client-side.
    if len(html_l) > 10000:
        _vis = re.sub(r"<script\b.*?</script>", " ", html_l, flags=re.S)
        _vis = re.sub(r"<style\b.*?</style>", " ", _vis, flags=re.S)
        _vis = re.sub(r"<noscript\b.*?</noscript>", " ", _vis, flags=re.S)
        _vis_text = re.sub(r"<[^>]+>", " ", _vis)
        _vis_text = re.sub(r"\s+", " ", _vis_text).strip()
        if len(_vis_text) < 1800:
            return True

    return False


def build_headers(response, fetch_method):
    headers = dict(response.headers or {})
    headers["status_code"] = response.status_code
    headers["fetch_method"] = fetch_method
    return headers


def safe_response(response, fetch_method):
    if not response:
        return None, None, {
            "status_code": None,
            "blocked": True,
            "fetch_method": fetch_method,
        }

    headers = build_headers(response, fetch_method)

    # A public URL that redirected somewhere internal — discard the body.
    if response.url and not is_public_url(response.url):
        return blocked_result(response.url, fetch_method)

    html = response.text or ""
    blocked = is_html_blocked_or_empty(
        html=html,
        status_code=response.status_code,
    )

    headers["blocked"] = blocked

    if blocked:
        return None, response.url, headers

    return html, response.url, headers


def fetch_with_requests(url):
    if not is_public_url(url):
        return blocked_result(url, "requests")
    response = requests.get(
        url,
        headers=BROWSER_HEADERS,
        timeout=30,
        allow_redirects=True,
    )

    return safe_response(response, "requests")


def fetch_with_cloudscraper(url):
    if not is_public_url(url):
        return blocked_result(url, "cloudscraper")
    scraper = cloudscraper.create_scraper(
        browser={
            "browser": "chrome",
            "platform": "windows",
            "mobile": False,
        }
    )

    response = scraper.get(
        url,
        headers=BROWSER_HEADERS,
        timeout=30,
        allow_redirects=True,
    )

    return safe_response(response, "cloudscraper")


def fetch_with_playwright(url):
    if not is_public_url(url):
        return blocked_result(url, "playwright")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return (
            None,
            url,
            {
                "status_code": None,
                "blocked": True,
                "fetch_method": "playwright",
                "fetch_error": (
                    "Playwright is not installed. Run: "
                    "pip install playwright && playwright install"
                ),
                "details": str(e),
            },
        )

    # Optional stealth mode — patches headless fingerprint signals
    # (navigator.webdriver, chrome.runtime, etc.) that bot detectors like
    # Akamai check. Install with: pip install playwright-stealth
    try:
        from playwright_stealth import stealth_sync as _stealth_sync
        _STEALTH_AVAILABLE = True
    except ImportError:
        _STEALTH_AVAILABLE = False

    _ensure_subprocess_capable_loop_policy()
    try:
        with browser_slot(), sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            # IMPORTANT: we deliberately do NOT spoof a location. This context
            # previously forced a US timezone + New York geolocation (and the
            # block below auto-clicked "United States" on country gates), which
            # made geo-aware stores — Shopify Markets, multi-region sites —
            # serve their US storefront even when the user entered a different
            # regional URL from another country (e.g. a Pakistan user landing on
            # the .us store). Region/currency must be an explicit, user-pinned
            # choice per competitor, never inferred here. We only keep English
            # as the language so text extraction stays consistent.
            context = browser.new_context(
                user_agent=BROWSER_HEADERS["User-Agent"],
                locale="en-US",
                viewport={"width": 1366, "height": 900},
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )

            page = context.new_page()

            # Apply stealth patches before any navigation
            if _STEALTH_AVAILABLE:
                _stealth_sync(page)

            # ── Intercept Shopify Storefront API token ──────────────────────
            # Headless Shopify stores (SKIMS, etc.) make GraphQL calls to
            # *.myshopify.com/api/*/graphql.json with a public Storefront
            # access token in the request headers.  Capture it so the
            # collection/product analyzers can use it directly.
            _sf_token = [None]
            _sf_domain = [None]
            _sf_api_url = [None]   # full GraphQL endpoint URL

            def _on_request(req):
                url_lower = req.url.lower()
                if "graphql.json" in url_lower or "storefront" in url_lower:
                    t = (
                        req.headers.get("x-shopify-storefront-access-token")
                        or req.headers.get("X-Shopify-Storefront-Access-Token")
                    )
                    if t and not _sf_token[0]:
                        _sf_token[0] = t
                        _sf_api_url[0] = req.url  # capture exact endpoint
                        try:
                            from urllib.parse import urlparse as _up
                            _p = _up(req.url)
                            # Store domain regardless of whether it's myshopify.com
                            _sf_domain[0] = f"{_p.scheme}://{_p.netloc}"
                        except Exception:
                            pass

            page.on("request", _on_request)
            # ───────────────────────────────────────────────────────────────

            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass

            try:
                page.wait_for_timeout(3000)
            except Exception:
                pass

            # NOTE: we intentionally do NOT auto-dismiss country/region gates by
            # clicking "United States"/"Stay" anymore. Auto-selecting a country
            # here silently forced the wrong regional store. When the store/region
            # picker lands, the user's explicitly chosen country will be selected
            # instead — until then we analyze the page exactly as the site serves
            # it, without picking a region on the user's behalf.

            # Wait a moment for async-loaded components (size pickers, variant
            # pickers) to appear in the DOM after the main page is interactive.
            try:
                page.wait_for_selector(
                    '[role="radiogroup"], [data-testid*="size"], fieldset[aria-label*="size" i]',
                    timeout=5000,
                )
            except Exception:
                pass

            # Lazy-loaded sections (homepage carousels, "Shop All" CTAs, featured
            # collections, chat/WhatsApp widgets) render only when scrolled into
            # view (IntersectionObserver) or after a delay. Scroll through the
            # page to trigger them, then return to top, BEFORE capturing HTML —
            # otherwise the captured DOM is missing collections/CTAs/widgets.
            try:
                _prev_h = 0
                for _ in range(12):
                    page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                    page.wait_for_timeout(600)
                    _h = page.evaluate("document.body.scrollHeight")
                    if _h == _prev_h:
                        break
                    _prev_h = _h
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(800)
            except Exception:
                pass

            html = page.content()
            final_url = page.url
            status_code = response.status if response else None
            if not is_public_url(final_url):
                browser.close()
                return blocked_result(final_url, "playwright")

            # Extract __NEXT_DATA__ directly from the JS runtime.
            # This is available after JS executes but may not appear in
            # page.content() if the framework inlines it dynamically.
            next_data_json = None
            try:
                next_data_json = page.evaluate(
                    "() => { "
                    "  try { "
                    "    var d = window.__NEXT_DATA__; "
                    "    return d ? JSON.stringify(d) : null; "
                    "  } catch(e) { return null; } "
                    "}"
                )
            except Exception:
                pass

            # If we got runtime __NEXT_DATA__ but it's not in the HTML,
            # inject it so our Python extractor can find it.
            if next_data_json and '__NEXT_DATA__' not in html:
                inject = (
                    f'<script id="__NEXT_DATA__" type="application/json">'
                    f'{next_data_json}</script>'
                )
                if '</body>' in html:
                    html = html.replace('</body>', f'{inject}</body>', 1)
                else:
                    html = html + inject

            # ── DOM-level variant extraction ────────────────────────────────
            # For sites like Nike where variants load via async API calls and
            # never appear in __NEXT_DATA__, extract size/color options from
            # the rendered DOM and inject as __DOM_VARIANTS__ for the parser.
            dom_variants_json = None
            try:
                dom_variants_json = page.evaluate(r"""
() => {
    try {
        var variants = [];
        var options = {};

        // --- Size pickers ---
        var sizeSels = [
            '[role="radiogroup"][aria-label*="size" i] [role="radio"]',
            '[role="radiogroup"][aria-label*="size" i] button',
            '[data-testid*="size"] button',
            '[data-testid*="size"][role="radio"]',
            '[aria-label*="size" i][role="radiogroup"] button',
            'fieldset[aria-label*="size" i] button',
            'fieldset[aria-label*="size" i] [role="radio"]',
            '[class*="size-grid"] button',
            '[class*="sizePicker"] button',
            '[class*="size_"] button',
            '[class*="swatch"] button',
            '[class*="variant"] button',
            '[class*="option-item"]',
            '[class*="pdp-size"] button',
        ];
        var sizeSet = new Set();
        var bestValues = [];
        for (var sel of sizeSels) {
            try {
                var els = document.querySelectorAll(sel);
                if (els.length < 2) continue;
                var vals = [];
                for (var el of els) {
                    var txt = (el.textContent || el.getAttribute('aria-label') || '').trim();
                    txt = txt.replace(/\s+/g, ' ').trim();
                    if (!txt || txt.length > 25 || sizeSet.has(txt)) continue;
                    sizeSet.add(txt);
                    var avail = !el.disabled
                        && el.getAttribute('aria-disabled') !== 'true'
                        && !el.classList.contains('disabled')
                        && !el.classList.contains('unavailable');
                    vals.push({value: txt, available: avail});
                    variants.push({title: txt, option1: txt, available: avail});
                }
                if (vals.length > bestValues.length) bestValues = vals;
                if (bestValues.length >= 3) break;
            } catch(e) {}
        }
        if (bestValues.length > 0) options['Size'] = bestValues;

        // Fallback: any role="radio" buttons with size-like text content
        // (catches Nike and other sites that use custom component class names)
        if (bestValues.length === 0) {
            var radioEls = document.querySelectorAll('[role="radio"], input[type="radio"]');
            var sizeRe = /^\d{1,2}(\.5)?$|^(X{0,3}S|X{0,3}L|XXL|XS|SM?|ML?|LG?|XL|XXL|XXXL|OS|ONE SIZE)$/i;
            var fallbackVals = [];
            var fallbackSet = new Set();
            for (var el of radioEls) {
                var txt = (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g,' ');
                if (!txt || txt.length > 10 || fallbackSet.has(txt)) continue;
                if (!sizeRe.test(txt)) continue;
                fallbackSet.add(txt);
                var avail = !el.disabled && el.getAttribute('aria-disabled') !== 'true'
                            && !el.classList.contains('disabled');
                fallbackVals.push({value: txt, available: avail});
                variants.push({title: txt, option1: txt, available: avail});
            }
            if (fallbackVals.length >= 2) options['Size'] = fallbackVals;
        }

        // --- Color swatches ---
        var colorSels = [
            '[data-testid*="color"]',
            '[aria-label*="color" i]',
            '[class*="colorway"] button',
            '[class*="color-swatch"]',
            '[class*="colorSwatch"]',
        ];
        var colorSet = new Set();
        for (var sel of colorSels) {
            try {
                var els = document.querySelectorAll(sel);
                if (els.length < 1) continue;
                var colorVals = [];
                for (var el of els) {
                    var txt = (el.getAttribute('aria-label') || el.textContent || '').trim();
                    if (!txt || txt.length > 60 || colorSet.has(txt)) continue;
                    // Skip Nike-style description fragments and navigation labels
                    if (/^Shown\s*:/i.test(txt) || /^Style\s*:\s*[A-Z0-9]{4}/i.test(txt)) continue;
                    if (/^shop\s+by\b/i.test(txt) || /^select\s+(a\s+)?/i.test(txt) || /^choose\s+/i.test(txt)) continue;
                    colorSet.add(txt);
                    colorVals.push({value: txt, available: true});
                }
                if (colorVals.length > 0) { options['Color'] = colorVals; break; }
            } catch(e) {}
        }

        if (Object.keys(options).length === 0 && variants.length === 0) return null;
        return JSON.stringify({variants: variants, options: options});
    } catch(e) { return null; }
}
""")
            except Exception:
                pass

            if dom_variants_json:
                inject_dv = (
                    f'<script id="__DOM_VARIANTS__" type="application/json">'
                    f'{dom_variants_json}</script>'
                )
                if '</body>' in html:
                    html = html.replace('</body>', f'{inject_dv}</body>', 1)
                else:
                    html = html + inject_dv
                print(f"DOM VARIANTS INJECTED: {dom_variants_json[:120]}...")

            headers = {
                "status_code": status_code,
                "blocked": is_html_blocked_or_empty(
                    html=html,
                    status_code=status_code,
                ),
                "fetch_method": "playwright",
                "next_data_injected": bool(next_data_json and '__NEXT_DATA__' in html),
            }

            # Attach captured Storefront API credentials if found
            if _sf_token[0]:
                headers["shopify_storefront_token"] = _sf_token[0]
                print(f"STOREFRONT TOKEN CAPTURED: {_sf_token[0][:12]}...")
            if _sf_domain[0]:
                headers["shopify_domain"] = _sf_domain[0]
                print(f"SHOPIFY DOMAIN CAPTURED: {_sf_domain[0]}")
            if _sf_api_url[0]:
                headers["shopify_storefront_api_url"] = _sf_api_url[0]
                print(f"STOREFRONT API URL: {_sf_api_url[0]}")

            # Capture the session cookies (incl. Cloudflare cf_clearance) this
            # browser earned, so a follow-up API fetch — e.g. products.json —
            # can reuse the clearance instead of facing the challenge fresh.
            try:
                headers["cookies"] = {c["name"]: c["value"] for c in context.cookies()}
            except Exception:
                pass

            browser.close()

            if headers["blocked"]:
                return None, final_url, headers

            return html, final_url, headers

    except Exception as e:
        return (
            None,
            url,
            {
                "status_code": None,
                "blocked": True,
                "fetch_method": "playwright",
                "fetch_error": str(e),
            },
        )


def fetch_json_with_playwright(url: str, timeout: int = 45000):
    """Fetch a JSON endpoint (e.g. Shopify /products.json) with a real browser.

    Stores behind Cloudflare/bot protection often 403 both `requests` and
    `cloudscraper` (TLS fingerprinting), but a real browser solves the challenge
    and returns the JSON — the same reason web_fetch works where a plain GET
    fails. Returns the raw JSON text (str) or None.
    """
    if not is_public_url(url):
        return None
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None

    _ensure_subprocess_capable_loop_policy()
    try:
        with browser_slot(), sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                user_agent=BROWSER_HEADERS["User-Agent"],
                locale="en-US",
                extra_http_headers={"Accept": "application/json, text/plain, */*"},
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            except Exception:
                browser.close()
                return None

            # A Cloudflare interstitial ("Just a moment…") resolves itself and
            # redirects to the JSON — poll a few times for real JSON to appear.
            result = None
            for _ in range(4):
                try:
                    txt = page.evaluate(
                        "() => document.body ? document.body.innerText : ''"
                    ) or ""
                except Exception:
                    txt = ""
                t = txt.strip()
                if t.startswith("{") or t.startswith("["):
                    result = t
                    break
                try:
                    page.wait_for_timeout(3000)
                except Exception:
                    break

            browser.close()
            return result
    except Exception:
        return None


def fetch_same_origin_json(base_url: str, paths, timeout: int = 45000):
    """Render the homepage (which clears Cloudflare + sets cookies), then fetch
    same-origin JSON/text endpoints FROM INSIDE the page. A cold GET of
    /collections.json is often challenged, but an in-page fetch after the homepage
    has passed the challenge succeeds — the browser reuses its cleared session.

    Returns { path: text_or_None } for each requested path (raw response text)."""
    if not is_public_url(base_url):
        return {}
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return {}

    _ensure_subprocess_capable_loop_policy()
    out = {}
    try:
        with browser_slot(), sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                user_agent=BROWSER_HEADERS["User-Agent"],
                locale="en-US",
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            page = context.new_page()
            try:
                page.goto(base_url, wait_until="domcontentloaded", timeout=timeout)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
            except Exception:
                browser.close()
                return {}
            for path in paths:
                try:
                    txt = page.evaluate(
                        """async (u) => {
                            try {
                                const r = await fetch(u, { headers: { 'Accept': 'application/json,application/xml,text/plain,*/*' }, credentials: 'include' });
                                if (!r.ok) return null;
                                return await r.text();
                            } catch (e) { return null; }
                        }""",
                        path,
                    )
                    out[path] = txt
                except Exception:
                    out[path] = None
            browser.close()
            return out
    except Exception:
        return {}


def fetch_with_expanded_menu(base_url: str, timeout: int = 45000):
    """Render the homepage and FORCE the navigation dropdowns/mega-menus open, so
    level-2 submenu category links enter the DOM before we capture it.

    Many storefronts build dropdown panels only on hover (CSS :hover or JS), so a
    static render sees just the top-level items. We (1) really hover each top-level
    nav item — needed for CSS :hover menus — and (2) dispatch mouseover/pointerover/
    focus on all nav-ish elements — needed for JS-built menus. Returns the full HTML
    (or None)."""
    if not is_public_url(base_url):
        return None
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None

    _ensure_subprocess_capable_loop_policy()
    try:
        with browser_slot(), sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                user_agent=BROWSER_HEADERS["User-Agent"], locale="en-US",
                viewport={"width": 1440, "height": 900},
            )
            page = context.new_page()
            try:
                page.goto(base_url, wait_until="domcontentloaded", timeout=timeout)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
            except Exception:
                browser.close()
                return None

            # (0) Force-show hidden submenu/dropdown containers via CSS. Reveals
            #     level-2 links on CSS-hidden mega-menus without needing to hover the
            #     exact right element. We only read <a href> afterwards, so breaking
            #     the visual layout is fine; the DOM tree (nesting) is preserved.
            try:
                page.evaluate(
                    """() => {
                        const css = `[class*="submenu"],[class*="sub-menu"],[class*="subnav"],
                          [class*="dropdown"],[class*="drop-down"],[class*="mega"],[class*="flyout"],
                          [class*="fly-out"],[class*="panel"],[class*="children"],[class*="child-menu"],
                          nav ul ul, nav li ul, header ul ul, [role="menu"], [aria-label*="menu" i] ul {
                            display:block !important; visibility:visible !important; opacity:1 !important;
                            height:auto !important; max-height:none !important; overflow:visible !important;
                            pointer-events:auto !important; position:static !important; transform:none !important;
                            clip:auto !important; clip-path:none !important;
                          }`;
                        const s = document.createElement('style');
                        s.textContent = css;
                        document.head.appendChild(s);
                        // Open accordion-style menus without clicking links (no nav).
                        document.querySelectorAll('details').forEach(d => { try { d.open = true; } catch(e){} });
                        document.querySelectorAll('[aria-expanded="false"]').forEach(el => {
                            if (el.tagName !== 'A') { try { el.setAttribute('aria-expanded','true'); } catch(e){} }
                        });
                    }"""
                )
                page.wait_for_timeout(300)
            except Exception:
                pass

            # (1) Hover each dropdown trigger and PERSIST its panel. SPA menus (React,
            #     Vue, …) render a dropdown only WHILE its trigger is hovered and remove
            #     it on mouse-leave — so a single final snapshot holds just the last one
            #     opened. For each trigger we hover, wait for the panel to render, then
            #     clone it into the trigger's container so every submenu survives in the
            #     captured DOM simultaneously. (Confirmed against stdbeauty's React nav.)
            try:
                triggers = page.query_selector_all(
                    '[aria-haspopup="true"], [aria-haspopup="menu"], nav a[aria-expanded], '
                    "header nav a, nav li > a, [class*='menu'] > li > a, [class*='has-'] > a"
                )
                for t in (triggers or [])[:30]:
                    try:
                        t.hover(timeout=800)
                        page.wait_for_timeout(380)
                        t.evaluate(
                            """el => {
                                const box = el.closest('li, [class*="relative"], [class*="has-"], [class*="menu-item"]') || el.parentElement;
                                if (!box) return;
                                // The just-rendered panel: a nearby list/absolute/dropdown
                                // container scoped to THIS item (not the top-level nav ul).
                                const panel = box.querySelector(
                                    ':scope > ul, :scope [class*="absolute"] ul, :scope ul ul, '
                                    + ':scope [class*="dropdown"], :scope [class*="submenu"], '
                                    + ':scope [class*="mega"], :scope [class*="flyout"], :scope [class*="panel"]'
                                );
                                if (panel && !panel.getAttribute('data-persisted')) {
                                    const clone = panel.cloneNode(true);
                                    clone.setAttribute('data-persisted', '1');
                                    clone.style.cssText = 'display:block !important;visibility:visible !important;position:static !important;';
                                    box.appendChild(clone);
                                }
                            }"""
                        )
                    except Exception:
                        continue
            except Exception:
                pass

            # (2) Dispatch hover/focus events broadly (JS-built dropdowns that don't
            #     rely on CSS :hover). Cheap and covers most menu frameworks.
            try:
                page.evaluate(
                    """() => {
                        const sel = "nav a, nav li, header a, header li, [class*='menu'] a, [class*='menu'] li, [class*='nav'] a, [class*='dropdown'], [aria-haspopup]";
                        document.querySelectorAll(sel).forEach(el => {
                            ['pointerover','mouseover','mouseenter','focus'].forEach(t => {
                                try { el.dispatchEvent(new Event(t, { bubbles: true })); } catch (e) {}
                            });
                        });
                    }"""
                )
                page.wait_for_timeout(1000)
            except Exception:
                pass

            html = page.content()
            browser.close()
            return html
    except Exception:
        return None


def fetch_shopify_graphql_catalog(base_url: str, timeout: int = 45000):
    """Read the catalog of a HEADLESS / custom Shopify storefront (Hydrogen, Next,
    custom SPA) via the Storefront GraphQL API.

    These stores serve the JS app shell for /collections.json & /products.json, so
    REST reads fail. But the SPA loads its data through the public Storefront API,
    exposing a `X-Shopify-Storefront-Access-Token` and the GraphQL endpoint on its
    own requests. We render the homepage, capture that token+endpoint from ANY
    request header, then replay collection/product GraphQL queries IN-PAGE (so the
    POST reuses the Cloudflare-cleared session).

    Returns { collections:[{handle,title}], products:[{handle,title,productType,tags,vendor}] } or {}.
    """
    if not is_public_url(base_url):
        return None
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return {}

    _ensure_subprocess_capable_loop_policy()
    captured = {"token": None, "endpoint": None}
    try:
        with browser_slot(), sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(user_agent=BROWSER_HEADERS["User-Agent"], locale="en-US")
            page = context.new_page()

            def _on_request(req):
                try:
                    tok = req.headers.get("x-shopify-storefront-access-token")
                    if tok and not captured["token"]:
                        captured["token"] = tok
                        captured["endpoint"] = req.url
                    elif ("graphql" in req.url.lower()) and not captured["endpoint"]:
                        captured["endpoint"] = req.url
                except Exception:
                    pass

            page.on("request", _on_request)

            try:
                page.goto(base_url, wait_until="domcontentloaded", timeout=timeout)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                # Scroll to trigger lazy product-grid GraphQL calls (which carry the token).
                try:
                    for _ in range(5):
                        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                        page.wait_for_timeout(700)
                        if captured["token"]:
                            break
                except Exception:
                    pass
            except Exception:
                browser.close()
                return {}

            token, endpoint = captured["token"], captured["endpoint"]
            # If the token appeared but not on the GraphQL URL, or vice-versa, fall
            # back to the conventional Storefront endpoint on the same host.
            if token and (not endpoint or "graphql" not in (endpoint or "").lower()):
                from urllib.parse import urlparse as _up
                _pp = _up(base_url)
                endpoint = f"{_pp.scheme}://{_pp.netloc}/api/2024-10/graphql.json"
            if not token or not endpoint:
                browser.close()
                return {}

            def _gql(query):
                try:
                    return page.evaluate(
                        """async ({endpoint, token, query}) => {
                            try {
                                const r = await fetch(endpoint, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json', 'X-Shopify-Storefront-Access-Token': token },
                                    body: JSON.stringify({ query }),
                                    credentials: 'include'
                                });
                                if (!r.ok) return null;
                                return await r.text();
                            } catch (e) { return null; }
                        }""",
                        {"endpoint": endpoint, "token": token, "query": query},
                    )
                except Exception:
                    return None

            import json as _j
            out = {"collections": [], "products": []}
            _ct = _gql("{ collections(first: 250) { edges { node { handle title } } } }")
            if _ct:
                try:
                    d = _j.loads(_ct)
                    for e in (((d.get("data") or {}).get("collections") or {}).get("edges") or []):
                        n = (e or {}).get("node") or {}
                        if n.get("handle"):
                            out["collections"].append({"handle": n["handle"], "title": n.get("title")})
                except Exception:
                    pass
            _pt = _gql("{ products(first: 250) { edges { node { handle title productType tags vendor } } } }")
            if _pt:
                try:
                    d = _j.loads(_pt)
                    for e in (((d.get("data") or {}).get("products") or {}).get("edges") or []):
                        n = (e or {}).get("node") or {}
                        if n.get("handle"):
                            out["products"].append({
                                "handle": n["handle"], "title": n.get("title"),
                                "productType": n.get("productType"), "tags": n.get("tags") or [],
                                "vendor": n.get("vendor"),
                            })
                except Exception:
                    pass
            browser.close()
            return out
    except Exception:
        return {}


def fetch_with_firecrawl(url: str) -> dict:
    """
    Tier 3 fetch fallback via Firecrawl API.
    Handles sites blocked by Cloudflare, Akamai, etc. where both Playwright
    and Jina fail.  Uses Firecrawl's anti-bot proxy network (auto-escalates
    from basic to enhanced proxies as needed).

    Returns:
        {"success": True, "html": str, "finalUrl": str, "statusCode": int, ...}
        {"success": False, "reason": str}
    """
    import os
    api_key = os.getenv("FIRECRAWL_API_KEY", "")
    if not api_key:
        return {"success": False, "reason": "FIRECRAWL_API_KEY not set in .env"}

    try:
        resp = requests.post(
            "https://api.firecrawl.dev/v2/scrape",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "url": url,
                "formats": ["rawHtml"],
                "onlyMainContent": False,
                "proxy": "auto",        # auto-escalates to enhanced if basic fails
                "blockAds": True,
                "timeout": 60000,
            },
            timeout=90,
        )
        data = resp.json()

        if not data.get("success"):
            err = data.get("error") or f"HTTP {resp.status_code}"
            return {"success": False, "reason": f"Firecrawl API error: {err}"}

        inner    = data.get("data") or {}
        html     = inner.get("rawHtml") or ""
        metadata = inner.get("metadata") or {}

        if not html or len(html.strip()) < 500:
            return {"success": False, "reason": "Firecrawl returned empty/minimal HTML"}

        return {
            "success":     True,
            "html":        html,
            "finalUrl":    metadata.get("url") or url,
            "statusCode":  metadata.get("statusCode") or 200,
            "title":       metadata.get("title") or "",
            "description": metadata.get("description") or "",
        }

    except Exception as exc:
        return {"success": False, "reason": f"Firecrawl exception: {exc}"}


def fetch_with_microlink(url: str) -> dict:
    """
    Tier 2.5 fetch — Microlink (https://microlink.io).
    Free tier: no API key required, ~50 req/day.
    Uses headless Puppeteer with stealth so it bypasses many bot detectors
    that block Jina.  Returns markdown, processed the same way as Jina output.
    """
    import json, urllib.request, urllib.parse

    api_url = (
        "https://api.microlink.io?url="
        + urllib.parse.quote(url, safe="")
        + "&markdown=true"
    )
    try:
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "Mozilla/5.0 WebAnalyzer/1.0",
                "Accept":     "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        status = payload.get("status", "")
        if status != "success":
            err = (payload.get("data") or {}).get("message") or f"status={status}"
            return {"success": False, "reason": f"Microlink API error: {err}"}

        data        = payload.get("data") or {}
        markdown    = data.get("markdown") or ""
        final_url   = data.get("url") or url
        title       = data.get("title") or ""
        description = data.get("description") or ""

        if not markdown or len(markdown.strip()) < 200:
            return {"success": False, "reason": "Microlink returned empty/minimal markdown"}

        return {
            "success":     True,
            "markdown":    markdown,
            "finalUrl":    final_url,
            "title":       title,
            "description": description,
        }

    except Exception as exc:
        return {"success": False, "reason": f"Microlink exception: {exc}"}


def fetch_with_openai_browse(url: str, page_type: str = "general") -> dict:
    """
    Tier 4 fetch fallback via OpenAI's web browsing capability.
    Uses GPT-4o with web_search_preview tool to retrieve page content
    when all other fetchers have been blocked or returned unusable content.

    Returns:
        {"success": True, "markdown": str, "finalUrl": str, "title": str, "description": str}
        {"success": False, "reason": str}
    """
    # DISABLED (removed as low-value): OpenAI-browse returned unstructured LLM
    # prose with no reliable prices/variants/stock and spent tokens per call.
    # Returning a failure makes the fallback chain skip this tier entirely.
    return {"success": False, "reason": "OpenAI browse fetcher disabled"}

    import os
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return {"success": False, "reason": "OPENAI_API_KEY not set in .env"}

    _page_hints = {
        "product":    "Focus on: product name, price, variants/options, description, availability.",
        "collection": "Focus on: product listing (names, prices, URLs), filters, pagination.",
        "homepage":   "Focus on: hero, navigation, featured products/collections, CTAs.",
        "pricing":    "Focus on: pricing tiers, plan names, features per plan, CTAs.",
        "general":    "Extract all visible text content in a clean, structured format.",
    }
    hint = _page_hints.get(page_type, _page_hints["general"])

    prompt = (
        f"Please visit this URL and return its full visible text content in Markdown format.\n"
        f"URL: {url}\n\n"
        f"{hint}\n\n"
        f"Return ONLY the page content as Markdown. Do not summarise or editorialize. "
        f"Include all product names, prices, links, headings, and structured data visible on the page."
    )

    try:
        resp = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model": "gpt-4o",
                "tools": [{"type": "web_search_preview"}],
                "input": prompt,
            },
            timeout=120,
        )
        data = resp.json()

        if resp.status_code != 200:
            err = (data.get("error") or {}).get("message") or f"HTTP {resp.status_code}"
            return {"success": False, "reason": f"OpenAI API error: {err}"}

        output_text = ""
        for item in data.get("output") or []:
            if item.get("type") == "message":
                for part in item.get("content") or []:
                    if part.get("type") == "output_text":
                        output_text += part.get("text", "")

        if not output_text or len(output_text.strip()) < 100:
            return {"success": False, "reason": "OpenAI returned empty or minimal content"}

        # Detect OpenAI refusal / access-denied responses — these look like
        # success (non-empty text) but contain no real page content.
        _refusal_phrases = (
            "i'm unable to access",
            "i am unable to access",
            "i cannot access",
            "i can't access",
            "unable to retrieve",
            "i'm not able to access",
            "i don't have the ability to browse",
            "i cannot browse",
            "the page may be restricted",
            "please check the url",
        )
        _text_lower = output_text.lower()
        if any(phrase in _text_lower for phrase in _refusal_phrases):
            return {
                "success": False,
                "reason": f"OpenAI refused to access the page: {output_text[:120].strip()}",
            }

        return {
            "success":     True,
            "markdown":    output_text,
            "finalUrl":    url,
            "title":       "",
            "description": "",
        }

    except Exception as exc:
        return {"success": False, "reason": f"OpenAI browse exception: {exc}"}


def fetch_html(url: str):
    """Primary fetch dispatcher.

    Tries requests -> cloudscraper -> Playwright in order.
    For each HTTP-level fetch, checks should_force_playwright() and
    upgrades to Playwright when the page is JS-heavy.
    Always returns (html, final_url, headers).
    """
    print("USING UPDATED FETCHER")

    # -- Tier 1: requests ----------------------------------------------------
    try:
        html, final_url, headers = fetch_with_requests(url)
        if html:
            force_pw = should_force_playwright(final_url or url, html, response_headers=headers)
            print("REQUESTS FETCHED:", final_url or url)
            print("FORCE PLAYWRIGHT:", force_pw)
            if force_pw:
                pw_html, pw_final_url, pw_headers = fetch_with_playwright(final_url or url)
                print("PLAYWRIGHT HTML RETURNED:", bool(pw_html))
                print("PLAYWRIGHT HEADERS:", pw_headers)
                if pw_html:
                    pw_headers["forced_playwright"] = True
                    pw_headers["forced_playwright_reason"] = "pricing_or_js_heavy_page"
                    pw_headers["original_fetch_method"] = "requests"
                    return pw_html, pw_final_url, pw_headers
                headers["playwright_attempted"] = True
                headers["playwright_failed"] = True
                headers["playwright_error"] = pw_headers.get("fetch_error")
                headers["playwright_details"] = pw_headers
            return html, final_url, headers
    except Exception as e:
        headers = {
            "status_code": None,
            "blocked": True,
            "fetch_method": "requests",
            "fetch_error": str(e),
        }

    # -- Tier 2: cloudscraper ------------------------------------------------
    try:
        html, final_url, headers = fetch_with_cloudscraper(url)
        if html:
            force_pw = should_force_playwright(final_url or url, html, response_headers=headers)
            print("CLOUDSCRAPER FETCHED:", final_url or url)
            print("FORCE PLAYWRIGHT:", force_pw)
            if force_pw:
                pw_html, pw_final_url, pw_headers = fetch_with_playwright(final_url or url)
                print("PLAYWRIGHT HTML RETURNED:", bool(pw_html))
                print("PLAYWRIGHT HEADERS:", pw_headers)
                if pw_html:
                    pw_headers["forced_playwright"] = True
                    pw_headers["forced_playwright_reason"] = "pricing_or_js_heavy_page"
                    pw_headers["original_fetch_method"] = "cloudscraper"
                    return pw_html, pw_final_url, pw_headers
                headers["playwright_attempted"] = True
                headers["playwright_failed"] = True
                headers["playwright_error"] = pw_headers.get("fetch_error")
                headers["playwright_details"] = pw_headers
            return html, final_url, headers
    except Exception as e:
        headers = {
            "status_code": None,
            "blocked": True,
            "fetch_method": "cloudscraper",
            "fetch_error": str(e),
        }

    # -- Tier 3: Playwright directly -----------------------------------------
    html, final_url, headers = fetch_with_playwright(url)
    return html, final_url, headers
