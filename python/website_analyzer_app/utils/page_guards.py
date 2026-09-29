"""
utils/page_guards.py — fetch quality guards for the Website Analyzer.

Before dispatching fetched HTML to a platform analyzer, call detect_page_block()
to catch pages that will never yield useful data: CAPTCHA challenges, login walls,
Cloudflare bot-checks, error pages, and near-empty responses.

Returning early with a clear block reason avoids:
  - Wasted LLM escalation API calls
  - Extractors returning wrong/partial data from challenge pages
  - Confusing null outputs with no explanation

Public API
----------
detect_page_block(html, url="") -> dict
    Returns:
      {
        "blocked":    bool,          # True → do not dispatch to analyzer
        "reason":     str | None,    # human-readable reason when blocked
        "blockType":  str | None,    # machine tag: "captcha" | "login_wall" |
                                     #  "cloudflare" | "bot_check" | "error_page" |
                                     #  "empty" | "too_thin"
        "confidence": float,         # 0.0–1.0 how certain we are
        "contentLength": int,        # raw HTML byte length
      }

    When blocked=False the caller should proceed normally.
    When blocked=True the caller should short-circuit and write a
    result with source.blockReason set to reason.
"""

import re


# ---------------------------------------------------------------------------
# Minimum useful content thresholds
# ---------------------------------------------------------------------------
_MIN_HTML_BYTES       = 300   # anything shorter is almost certainly an error
_MIN_TEXT_CHARS       = 150   # visible text below this is too thin to analyze
_THIN_PAGE_THRESHOLD  = 800   # below this we flag as potentially blocked/thin


# ---------------------------------------------------------------------------
# Signal patterns
# ---------------------------------------------------------------------------

_CAPTCHA_PATTERNS = [
    re.compile(r'g-recaptcha|recaptcha\.net|recaptcha/api\.js', re.I),
    re.compile(r'hcaptcha\.com|h-captcha', re.I),
    re.compile(r'cf-turnstile|turnstile\.cloudflare\.com', re.I),
    re.compile(r'<title[^>]*>[^<]*captcha[^<]*</title>', re.I),
    re.compile(r'please\s+complete\s+the\s+(security\s+)?check', re.I),
    re.compile(r'verify\s+you\s+are\s+(human|not\s+a\s+robot)', re.I),
    re.compile(r'prove\s+you\'?re\s+(human|not\s+a\s+robot)', re.I),
    re.compile(r'bot\s+check|robot\s+check|human\s+verification', re.I),
]

_CLOUDFLARE_PATTERNS = [
    re.compile(r'<title[^>]*>[^<]*attention\s+required[^<]*</title>', re.I),
    re.compile(r'<title[^>]*>[^<]*just\s+a\s+moment[^<]*</title>', re.I),
    re.compile(r'cloudflare\s+ray\s+id', re.I),
    re.compile(r'checking\s+if\s+the\s+site\s+connection\s+is\s+secure', re.I),
    re.compile(r'enable\s+javascript\s+and\s+cookies\s+to\s+continue', re.I),
    re.compile(r'__cf_bm|cf-browser-verification', re.I),
    re.compile(r'challenge-platform', re.I),
]

_LOGIN_WALL_PATTERNS = [
    re.compile(r'<title[^>]*>[^<]*(log\s*in|sign\s*in|login\s+required)[^<]*</title>', re.I),
    re.compile(r'(you\s+must\s+(be\s+)?log\s*ged?\s*in|please\s+(log|sign)\s*in\s+to)', re.I),
    re.compile(r'(members?\s+only|subscribers?\s+only|login\s+to\s+(view|access|continue))', re.I),
    re.compile(r'<form[^>]*\b(action|id|class)=["\'][^"\']*login[^"\']*["\']', re.I),
    # Page with only a login form and very little else
]

_BOT_DETECTION_PATTERNS = [
    re.compile(r'access\s+denied|403\s+forbidden', re.I),
    re.compile(r'your\s+(ip|request|access)\s+(has\s+been\s+)?blocked', re.I),
    re.compile(r'too\s+many\s+requests|rate\s+limit\s+exceeded', re.I),
    re.compile(r'akamai.*ghost|imperva|incapsula|distil\s+networks', re.I),
    re.compile(r'perimeterx|px-captcha|datadome', re.I),
    re.compile(r'<title[^>]*>[^<]*(403|access\s+denied|blocked)[^<]*</title>', re.I),
]

_ERROR_PAGE_PATTERNS = [
    re.compile(r'<title[^>]*>[^<]*(404|page\s+not\s+found|not\s+found)[^<]*</title>', re.I),
    re.compile(r'<title[^>]*>[^<]*(500|internal\s+server\s+error)[^<]*</title>', re.I),
    re.compile(r'<title[^>]*>[^<]*(503|service\s+unavailable)[^<]*</title>', re.I),
    re.compile(r'<title[^>]*>[^<]*(502|bad\s+gateway)[^<]*</title>', re.I),
    re.compile(r'the\s+page\s+(you|requested)\s+(are\s+looking|does\s+not\s+exist|can\'t\s+be\s+found)', re.I),
    re.compile(r'(oops|sorry)[^<]{0,60}(page|content)\s+(not\s+found|doesn\'t\s+exist)', re.I),
]

_JINA_BLOCK_PATTERNS = [
    # Jina reader returns specific text when it hits a block
    re.compile(r'jina\s+reader.*blocked|content\s+not\s+accessible', re.I),
    re.compile(r'\[CAPTCHA\]|\[LOGIN REQUIRED\]|\[ACCESS DENIED\]', re.I),
]


# ---------------------------------------------------------------------------
# Visible text extractor (lightweight — no BeautifulSoup dependency)
# ---------------------------------------------------------------------------

_TAG_RE    = re.compile(r'<[^>]+>', re.S)
_SPACE_RE  = re.compile(r'\s+')
_SCRIPT_RE = re.compile(r'<(script|style)[^>]*>.*?</\1>', re.S | re.I)


def _visible_text_length(html):
    """Approximate visible text character count without importing BeautifulSoup."""
    h = _SCRIPT_RE.sub(' ', html)
    h = _TAG_RE.sub(' ', h)
    return len(_SPACE_RE.sub(' ', h).strip())


# ---------------------------------------------------------------------------
# Main guard
# ---------------------------------------------------------------------------

def detect_page_block(html, url=""):
    """
    Inspect fetched HTML and decide whether it's safe to dispatch to an analyzer.

    Parameters
    ----------
    html : str | None
        Raw HTML (or Jina markdown) returned by the fetcher.
    url : str
        The requested URL (used for context in future expansions).

    Returns
    -------
    dict with keys: blocked, reason, blockType, confidence, contentLength
    """
    html = html or ""
    content_length = len(html)

    def _result(blocked, reason=None, block_type=None, confidence=1.0):
        return {
            "blocked":       blocked,
            "reason":        reason,
            "blockType":     block_type,
            "confidence":    confidence,
            "contentLength": content_length,
        }

    # 1. Empty / too short
    if content_length < _MIN_HTML_BYTES:
        return _result(True, "Response is empty or too short to analyze", "empty", 1.0)

    visible_len = _visible_text_length(html)
    if visible_len < _MIN_TEXT_CHARS:
        return _result(True, "Page has almost no visible text — likely a bot challenge or redirect shell", "too_thin", 0.9)

    # 2. CAPTCHA
    for pat in _CAPTCHA_PATTERNS:
        if pat.search(html):
            return _result(True, "CAPTCHA challenge detected", "captcha", 0.97)

    # 3. Cloudflare / WAF challenges
    for pat in _CLOUDFLARE_PATTERNS:
        if pat.search(html):
            return _result(True, "Cloudflare or WAF challenge page detected", "cloudflare", 0.97)

    # 4. Bot detection / rate limiting / IP block
    for pat in _BOT_DETECTION_PATTERNS:
        if pat.search(html):
            return _result(True, "Bot detection or access block detected", "bot_check", 0.92)

    # 5. Login wall
    login_hits = sum(1 for pat in _LOGIN_WALL_PATTERNS if pat.search(html))
    if login_hits >= 2:
        return _result(True, "Login wall detected — content requires authentication", "login_wall", 0.88)

    # 6. HTTP error pages
    for pat in _ERROR_PAGE_PATTERNS:
        if pat.search(html):
            return _result(True, "HTTP error page (4xx/5xx) detected", "error_page", 0.93)

    # 7. Jina-specific block markers
    for pat in _JINA_BLOCK_PATTERNS:
        if pat.search(html):
            return _result(True, "Fetch service reported blocked content", "bot_check", 0.85)

    # 8. Thin page — not a hard block but worth flagging
    if visible_len < _THIN_PAGE_THRESHOLD:
        return _result(False, None, None, 1.0)   # not blocked, but caller can check contentLength

    return _result(False)
