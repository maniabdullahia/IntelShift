def clean_text(text):
    if not text:
        return None
    return " ".join(text.split()).strip()


def extract_meta(soup):
    title = clean_text(soup.title.get_text()) if soup.title else None

    meta_desc = soup.find("meta", attrs={"name": "description"})
    canonical = soup.find("link", attrs={"rel": "canonical"})

    h1 = soup.find("h1")

    return {
        "title": title,
        "metaDescription": clean_text(meta_desc.get("content")) if meta_desc else None,
        "canonical": canonical.get("href") if canonical else None,
        "h1": clean_text(h1.get_text()) if h1 else None
    }
