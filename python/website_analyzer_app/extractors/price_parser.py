import re


def parse_price(text):
    if not text:
        return None

    cleaned = text.replace(",", "")
    match = re.search(r"(\d+(\.\d+)?)", cleaned)

    if not match:
        return None

    value = float(match.group(1))
    return int(value) if value.is_integer() else value


def detect_currency(text):
    if not text:
        return None

    lower = text.lower()

    if "rs" in lower or "pkr" in lower:
        return "PKR"

    if "$" in text:
        return "USD"

    if "£" in text:
        return "GBP"

    if "€" in text:
        return "EUR"

    return None
