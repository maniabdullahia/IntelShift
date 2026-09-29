import json


def extract_json_ld(soup):
    blocks = []

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.get_text(strip=True)

        try:
            parsed = json.loads(raw)
            blocks.append(parsed)
        except Exception:
            continue

    return blocks
