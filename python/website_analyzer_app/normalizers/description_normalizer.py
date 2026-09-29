import re
from bs4 import BeautifulSoup

from normalizers.text_normalizer import clean_text


def clean_html_description(html):
    if not html:
        return {
            "html": None,
            "text": None,
            "bullets": [],
            "headings": []
        }

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "meta", "link", "noscript"]):
        tag.decompose()

    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            del tag.attrs[attr]

    for tag in soup.find_all():
        if not tag.get_text(strip=True) and tag.name not in ["br"]:
            tag.decompose()

    cleaned_html = str(soup)
    cleaned_html = re.sub(r"\s+", " ", cleaned_html).strip()

    text = soup.get_text(" ", strip=True)
    text = clean_text(text)

    bullets = []
    for li in soup.find_all("li"):
        item = clean_text(li.get_text(" ", strip=True))
        if item:
            bullets.append(item)

    headings = []
    for h in soup.find_all(["h1", "h2", "h3", "h4"]):
        item = clean_text(h.get_text(" ", strip=True))
        if item:
            headings.append(item)

    return {
        "html": cleaned_html or None,
        "text": text,
        "bullets": bullets,
        "headings": headings
    }


def extract_description_sections(description_text):
    if not description_text:
        return {
            "features": [],
            "benefits": [],
            "usage": [],
            "specifications": []
        }

    sections = {
        "features": [],
        "benefits": [],
        "usage": [],
        "specifications": []
    }

    feature_keywords = ["feature", "key feature", "why it performs"]
    benefit_keywords = ["benefit", "result", "helps", "improves", "reduces"]
    usage_keywords = ["how to use", "directions", "application", "apply"]
    spec_keywords = ["specification", "product details", "size", "weight", "capacity", "sku"]

    sentences = re.split(r"(?<=[.!?])\s+", description_text)

    for sentence in sentences:
        s = clean_text(sentence)
        if not s:
            continue

        s_lower = s.lower()

        if any(k in s_lower for k in usage_keywords):
            sections["usage"].append(s)
        elif any(k in s_lower for k in spec_keywords):
            sections["specifications"].append(s)
        elif any(k in s_lower for k in feature_keywords):
            sections["features"].append(s)
        elif any(k in s_lower for k in benefit_keywords):
            sections["benefits"].append(s)

    return sections
