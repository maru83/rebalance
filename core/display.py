from __future__ import annotations

from typing import Any


def unit_label(display_unit: str) -> str:
    return {"yen": "円", "man": "万円", "million": "百万円"}.get(display_unit, "円")


def format_amount(value: float | int, display_unit: str = "yen") -> str:
    unit = unit_label(display_unit)
    divisor = {"yen": 1, "man": 10_000, "million": 1_000_000}.get(display_unit, 1)
    amount = float(value) / divisor
    if display_unit == "yen":
        return f"¥{int(round(amount)):,}円"
    return f"¥{amount:,.1f}{unit}"


def get_display_settings(settings: dict[str, Any] | None) -> tuple[str, str]:
    if not settings:
        return "JPY", "yen"
    return str(settings.get("currency", "JPY")), str(settings.get("display_unit", "yen"))
