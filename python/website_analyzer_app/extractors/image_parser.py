from urllib.parse import urljoin


def normalize_image_url(src, base_url):
    if not src:
        return None

    src = src.strip()

    if src.startswith("//"):
        return "https:" + src

    return urljoin(base_url, src)
