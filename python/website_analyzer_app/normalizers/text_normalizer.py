import re


def collapse_spaces(value):
    if value is None:
        return None
    value = str(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def clean_text(value):
    if not value:
        return None

    value = str(value)
    value = value.replace("\xa0", " ")
    value = value.replace("&nbsp;", " ")
    value = value.replace("Â", "")
    value = value.replace("\x7f", "")
    value = collapse_spaces(value)

    return value or None


def title_case_from_handle(handle):
    if not handle:
        return None

    text = handle.replace("-", " ").replace("_", " ")
    text = collapse_spaces(text)

    return text.title() if text else None


def normalize_vendor(value):
    return clean_text(value)


def normalize_category(value):
    value = clean_text(value)

    if not value:
        return None

    if "-" in value or "_" in value:
        return title_case_from_handle(value)

    return value
