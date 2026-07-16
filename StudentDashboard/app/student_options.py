"""Fixed student religion and reservation category options."""

RELIGION_OPTIONS = [
    "Hindu",
    "Muslim",
    "Christan",
    "Other",
]

CATEGORY_OPTIONS = [
    ("GM", "General Merit"),
    ("SC", "Scheduled Caste"),
    ("ST", "Scheduled Tribe"),
    ("CAT-1", "Category 1 (Backward Classes)"),
    ("2A", "Category 2A"),
    ("2B", "Category 2B"),
    ("3A", "Category 3A"),
    ("3B", "Category 3B"),
]

_CATEGORY_LOOKUP = {code.upper(): code for code, _label in CATEGORY_OPTIONS}
_CATEGORY_LABELS = {code: label for code, label in CATEGORY_OPTIONS}


def normalize_religion(value: str | None) -> str | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    for option in RELIGION_OPTIONS:
        if cleaned.lower() == option.lower():
            return option
    return cleaned


def normalize_category(value: str | None) -> str | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    upper = cleaned.upper()
    if upper in _CATEGORY_LOOKUP:
        return _CATEGORY_LOOKUP[upper]
    for code, label in CATEGORY_OPTIONS:
        if cleaned.lower() == label.lower():
            return code
    return cleaned


def category_label(value: str | None) -> str:
    code = normalize_category(value)
    if not code:
        return "-"
    label = _CATEGORY_LABELS.get(code)
    return f"{code} — {label}" if label else code


def category_display(value: str | None) -> str:
    code = normalize_category(value)
    if not code:
        return "-"
    return _CATEGORY_LABELS.get(code, code)
