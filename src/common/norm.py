"""Normalization helpers shared by the scorer and fixture generator."""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation


_SUFFIXES = {
    "ltd", "limited", "llc", "inc", "incorporated", "plc", "gmbh", "ag",
    "sa", "sas", "sarl", "srl", "bv", "nv", "co", "corp", "corporation", "company",
}
_CURRENCIES = {"USD": {"USD", "$"}, "EUR": {"EUR", "€"}, "GBP": {"GBP", "£"}}


def invoice_no_norm(value):
    if value is None:
        return None
    return "".join(unicodedata.normalize("NFKC", str(value)).strip().upper().split())


def vendor_norm(value):
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value)).casefold().replace("&", "and")
    text = " ".join("".join(c if c.isalnum() else " " for c in text).split())
    parts = text.split()
    while parts and parts[-1] in _SUFFIXES:
        parts.pop()
    return " ".join(parts)


def dedupe_key(invoice_no, vendor, currency):
    if invoice_no is None or vendor is None or currency is None:
        return None
    a, b, c = invoice_no_norm(invoice_no), vendor_norm(vendor), parse_currency(currency)
    if not a or not b or not c:
        return None
    return "|".join((a, b, c))


def parse_amount(value):
    """Parse US or EU decimal notation; return None when invalid or ambiguous."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    text = re.sub(r"^[^0-9+\-]+|[^0-9]+$", "", text)
    if not text:
        return None
    if "," in text and "." in text:
        # The rightmost separator is decimal; valid grouping is required.
        decimal_sep = "," if text.rfind(",") > text.rfind(".") else "."
        group_sep = "." if decimal_sep == "," else ","
        integer, fraction = text.rsplit(decimal_sep, 1)
        groups = integer.lstrip("+-").split(group_sep)
        if len(groups) > 1 and (not groups[0].isdigit() or any(len(g) != 3 or not g.isdigit() for g in groups[1:])):
            return None
        normalized = integer.replace(group_sep, "") + "." + fraction
    elif "," in text:
        bits = text.lstrip("+-").split(",")
        if len(bits) > 2:
            if any(len(g) != 3 or not g.isdigit() for g in bits[1:]):
                return None
            normalized = text.replace(",", "")
        elif len(bits) == 2:
            if len(bits[1]) == 3 and bits[0].isdigit():
                return None  # 1,234 could be decimal or grouped.
            normalized = text.replace(",", ".")
        else:
            normalized = text
    elif "." in text:
        bits = text.lstrip("+-").split(".")
        if len(bits) > 2:
            if any(len(g) != 3 or not g.isdigit() for g in bits[1:]):
                return None
            normalized = text.replace(".", "")
        elif len(bits) == 2 and len(bits[1]) == 3 and bits[0].isdigit():
            return None
        else:
            normalized = text
    else:
        normalized = text
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def parse_currency(value):
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value)).strip().upper()
    for code, forms in _CURRENCIES.items():
        if text in forms or text == code:
            return code
    return None


def parse_date(value):
    if value is None:
        return None
    text = str(value).strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%d %b %Y", "%B %d, %Y"):
        try:
            return date.strptime(text, fmt)  # Python 3.9 has no date.strptime
        except (ValueError, AttributeError):
            from datetime import datetime
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                pass
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        day, month, year = map(int, m.groups())
        if day <= 12:
            return None
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def map_legacy_tax(row):
    """Read generic tax or the baseline's documented CGST+SGST tax pair."""
    if "tax" in row:
        return row.get("tax")
    cgst, sgst = row.get("total_cgst"), row.get("total_sgst")
    if cgst in (None, "") and sgst in (None, ""):
        return None
    left = parse_amount(cgst) if cgst not in (None, "") else Decimal("0")
    right = parse_amount(sgst) if sgst not in (None, "") else Decimal("0")
    return left + right if left is not None and right is not None else None
