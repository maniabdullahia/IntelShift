from urllib.parse import urljoin


def clean_text(text):
    if not text:
        return None
    return " ".join(text.split()).strip()


def extract_navigation(soup, url):
    links = []

    for a in soup.select("nav a, header a"):
        text = clean_text(a.get_text())
        href = a.get("href")

        if text and href:
            links.append({
                "text": text,
                "url": urljoin(url, href)
            })

    return {
        "links": links[:50]
    }
