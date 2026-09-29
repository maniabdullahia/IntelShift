def clean_text(text):
    if not text:
        return None
    return " ".join(text.split()).strip()


def first_text(parent, selectors):
    for selector in selectors:
        el = parent.select_one(selector)
        if el:
            return clean_text(el.get_text())
    return None
