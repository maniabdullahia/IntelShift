import re as _re

# Domains / URL patterns that are tracking pixels or ad-network beacons, not
# real product images.  Applied in normalize_image_url() so every code path
# (img tags, og:image, JSON-LD, API responses) is filtered uniformly.
_TRACKING_IMAGE_RE = _re.compile(
    r't\.teads\.tv'
    r'|photorankmedia\.com'
    r'|doubleclick\.net'
    r'|googlesyndication\.com'
    r'|google-analytics\.com'
    r'|facebook\.com/tr'
    r'|pixel\.facebook\.com'
    r'|analytics\.twitter\.com'
    r'|bat\.bing\.com'
    r'|tealiumiq\.com'
    r'|tags\.tiqcdn\.com'
    r'|trustarc\.com'
    r'|quantserve\.com'
    r'|scorecard(?:research)?\.com'
    r'|1x1\.gif'
    r'|/pixel/'
    r'|/beacon/'
    r'|/track(?:er)?[?/]',
    _re.I,
)


def normalize_image_url(url):
    if not url:
        return None

    url = str(url).strip()

    if url.startswith("//"):
        url = "https:" + url

    url = url.split(" ")[0].strip()

    if not url:
        return None

    # Reject tracking pixels / ad-network beacons regardless of source
    if _TRACKING_IMAGE_RE.search(url):
        return None

    return url


def dedupe_images(images):
    seen = set()
    cleaned = []

    for image in images or []:
        image = normalize_image_url(image)

        if not image:
            continue

        if image in seen:
            continue

        seen.add(image)
        cleaned.append(image)

    return cleaned
