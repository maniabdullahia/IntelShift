def normalize_number(value):
    if value is None:
        return None

    try:
        value_str = str(value).strip()

        if value_str == "":
            return None

        number = float(value_str)

        return int(number) if number.is_integer() else number

    except Exception:
        return None


def normalize_price(price_obj=None, default_currency="PKR"):
    # Handle raw price strings like "32.00 €" or "Rs. 1,890"
    if isinstance(price_obj, str) and price_obj.strip():
        try:
            from extractors.price_parser import parse_price, detect_currency
            _amount = parse_price(price_obj)
            _currency = detect_currency(price_obj) or default_currency
            price_obj = {
                "current": _amount,
                "currency": _currency,
                "priceTextRaw": price_obj,
            }
        except Exception:
            price_obj = {"priceTextRaw": price_obj}
    elif not isinstance(price_obj, dict):
        price_obj = {}

    price_obj = price_obj or {}

    # "amount" is used by WordPress priceNormalized — treat as alias for "current"
    if not price_obj.get("current") and price_obj.get("amount") is not None:
        price_obj = {**price_obj, "current": price_obj["amount"]}

    current = normalize_number(price_obj.get("current"))
    compare_at = normalize_number(price_obj.get("compareAt"))

    is_on_sale = False
    if current is not None and compare_at is not None and compare_at > current:
        is_on_sale = True

    return {
        "currency": price_obj.get("currency") or default_currency,
        "current": current,
        "compareAt": compare_at,
        "isOnSale": is_on_sale,
        "priceTextRaw": price_obj.get("priceTextRaw")
    }
