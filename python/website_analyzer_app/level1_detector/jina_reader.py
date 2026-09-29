import re
import requests
from urllib.parse import urlparse


JINA_BASE = "https://r.jina.ai/"


def build_jina_url(url: str) -> str:
    url = (url or "").strip()

    if not url.startswith("http"):
        url = "https://" + url

    return JINA_BASE + url


def clean_text(value):
    if not value:
        return ""

    value = str(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def extract_title_from_markdown(markdown: str):
    text = markdown or ""

    patterns = [
        r"^Title:\s*(.+)$",
        r"^#\s+(.+)$"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.MULTILINE | re.IGNORECASE)
        if match:
            return clean_text(match.group(1))

    first_line = text.strip().split("\n")[0] if text.strip() else ""
    return clean_text(first_line[:120])


def guess_page_type_from_url(url: str):
    url_l = (url or "").lower()

    if any(x in url_l for x in [
        "/products/",
        "/product/",
        "/shop/",
        "/p/"
    ]):
        return "product"

    if any(x in url_l for x in [
        "/collections/",
        "/collection/",
        "/category/",
        "/categories/",
        "/product-category/",
        "/catalog/",
        "/c/",
        "/w/"
    ]):
        return "collection"

    if any(x in url_l for x in [
        "/blogs/",
        "/blog/",
        "/news/",
        "/articles/",
        "/article/"
    ]):
        return "blog"

    if any(x in url_l for x in [
        "/about",
        "/contact",
        "/faq",
        "/privacy",
        "/terms",
        "/shipping",
        "/returns",
        "/refund"
    ]):
        return "general"

    parsed = urlparse(url)
    path = (parsed.path or "").strip("/")

    if not path:
        return "homepage"

    return "general"


def is_jina_content_usable(markdown: str):
    text = (markdown or "").strip()
    lower = text.lower()

    if len(text) < 300:
        return False

    weak_patterns = [
        "title:",
        "just a moment",
        "access denied",
        "enable javascript",
        "captcha",
        "forbidden",
        "not found",
        "page not found",
        "checking your browser"
    ]

    if len(text) < 800 and any(pattern in lower for pattern in weak_patterns):
        return False

    # If it only has a title and almost no body, reject it
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= 3 and len(text) < 800:
        return False

    return True


def fetch_with_jina(url: str, timeout: int = 35):
    # DISABLED (removed as low-value): the Jina markdown reader produced
    # unreliable e-commerce data (heuristically parsed products with no accurate
    # prices/variants/stock). Returning an unusable result makes the fallback
    # chain skip straight to Microlink/Firecrawl.
    return {
        "success": False, "usable": False, "reason": "Jina reader disabled",
        "markdown": "", "finalUrl": url, "title": "", "description": "",
        "statusCode": None, "headers": {},
    }

    jina_url = build_jina_url(url)

    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(
            jina_url,
            headers=headers,
            timeout=timeout
        )

        status_code = response.status_code

        if status_code >= 500:
            return {
                "success": False,
                "usable": False,
                "retryable": True,
                "statusCode": status_code,
                "finalUrl": url,
                "title": "",
                "markdown": "",
                "reason": f"Jina returned server error {status_code}",
                "fetch_method": "jina_reader"
            }

        data = None

        try:
            data = response.json()
        except Exception:
            data = None

        if isinstance(data, dict):
            payload = data.get("data") if isinstance(data.get("data"), dict) else data

            title = clean_text(payload.get("title") or "")
            content = payload.get("content") or payload.get("text") or ""
            description = clean_text(payload.get("description") or "")
            final_url = payload.get("url") or url

            markdown_parts = []

            if title:
                markdown_parts.append(f"# {title}")

            if description:
                markdown_parts.append(description)

            if content:
                markdown_parts.append(content)

            markdown = "\n\n".join(markdown_parts).strip()

        else:
            markdown = response.text or ""
            title = extract_title_from_markdown(markdown)
            description = ""
            final_url = url

        usable = is_jina_content_usable(markdown)

        return {
            "success": True,
            "usable": usable,
            "retryable": not usable,
            "statusCode": status_code,
            "finalUrl": final_url,
            "title": title or extract_title_from_markdown(markdown),
            "description": description,
            "markdown": markdown,
            "html": markdown,
            "headers": dict(response.headers or {}),
            "reason": None if usable else "Jina fallback returned too little usable content.",
            "fetch_method": "jina_reader"
        }

    except Exception as e:
        return {
            "success": False,
            "usable": False,
            "retryable": True,
            "statusCode": None,
            "finalUrl": url,
            "title": "",
            "description": "",
            "markdown": "",
            "html": "",
            "headers": {},
            "reason": f"Jina fetch failed: {str(e)}",
            "fetch_method": "jina_reader"
        }
