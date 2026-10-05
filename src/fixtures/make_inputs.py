"""Generate the first 26 deterministic synthetic invoice fixtures."""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
from datetime import date, timedelta

from src.common.norm import dedupe_key
from src.fixtures.pdfwriter import render_pdf


VENDORS = (
    "Harbour & Finch Ltd.", "Northstar Office Supply", "Muller Druck GmbH",
    "Cedar Ridge Components", "Blue Heron Paper Co.", "Westbridge Tools",
    "Silverline Packaging", "Acme Co. Inc.", "Kingswell Stationery",
)
DESCRIPTIONS = (
    "Archive boxes", "Printer paper", "Shipping labels", "Desk organizers",
    "Replacement cartridges", "Workshop gloves", "Packing tape", "File folders",
)
CURRENCIES = ("USD", "EUR", "GBP")
CURRENCY_MARKS = {"USD": "$", "EUR": "EUR", "GBP": "GBP"}
MANIFEST_HEADER = ("input_id", "filename", "label_bucket", "gold_path")
GENERATOR_VERSION = "1.0"


def _money(cents):
    return cents / 100.0


def _format_amount(cents, currency, european=False):
    whole, fraction = divmod(cents, 100)
    if european:
        grouped = "{:,.0f}".format(whole).replace(",", ".")
        return "{} {},{:02d}".format(CURRENCY_MARKS[currency], grouped, fraction)
    return "{} {:,}.{:02d}".format(CURRENCY_MARKS[currency], whole, fraction)


def _make_invoice(index, bucket, rng, seed):
    vendor = VENDORS[(index + rng.randrange(len(VENDORS))) % len(VENDORS)]
    currency = CURRENCIES[(index - 1) % len(CURRENCIES)]
    invoice_no = "INV-2026-{:03d}".format(index)
    invoice_date = date(2026, 3, 1) + timedelta(days=(index * 3) % 27)
    line_count = 1 + rng.randrange(8)
    lines = []
    subtotal_cents = 0
    for line_number in range(line_count):
        quantity = 1 + rng.randrange(5)
        unit_price_cents = 425 + rng.randrange(17500)
        total_cents = quantity * unit_price_cents
        subtotal_cents += total_cents
        lines.append({
            "description": DESCRIPTIONS[(index + line_number + rng.randrange(len(DESCRIPTIONS))) % len(DESCRIPTIONS)],
            "quantity": quantity,
            "unit_price": _money(unit_price_cents),
            "line_total": _money(total_cents),
        })

    is_messy = bucket == "messy"
    doc_foots = not (is_messy and index in (23, 24))
    reported_subtotal = subtotal_cents - (275 if not doc_foots else 0)
    rate_basis_points = 2000 if is_messy and currency in ("EUR", "GBP") else 825
    tax_cents = (reported_subtotal * rate_basis_points + 5000) // 10000
    total_cents = reported_subtotal + tax_cents
    if not doc_foots:
        # The printed line-item sum intentionally differs from the printed subtotal.
        assert sum(round(row["line_total"] * 100) for row in lines) != reported_subtotal

    # Gold is fully constructed before rendering. Layout choices affect only presentation.
    form_currency = currency
    if is_messy and index in (15, 20):
        form_currency = CURRENCIES[(CURRENCIES.index(currency) + 1) % len(CURRENCIES)]
    label_bucket = bucket
    expected = {
        "invoice_no": invoice_no,
        "vendor": vendor,
        "invoice_date": invoice_date.isoformat(),
        "currency": currency,
        "subtotal": _money(reported_subtotal),
        "tax": _money(tax_cents),
        "total": _money(total_cents),
        "line_items": lines,
    }
    gold = {
        "input_id": "t2-{:03d}".format(index),
        "synthetic": True,
        "label_bucket": label_bucket,
        "form": {
            "name": "Synthetic Accounts Payable",
            "email": "ap@example.com",
            "currency": form_currency,
            "notes": "",
        },
        "expected": expected,
        "dedupe_key": dedupe_key(invoice_no, vendor, currency),
        "expect_outcome": "committed",
        "duplicate_of": None,
        "injection": None,
        "fault": None,
        "doc_foots": doc_foots,
        "generator": {"seed": seed, "template": "clean" if not is_messy else "messy", "version": GENERATOR_VERSION},
    }

    return gold


def _render_lines(gold):
    """Create the printed text from saved gold fields and its declared layout."""
    expected = gold["expected"]
    index = int(gold["input_id"].rsplit("-", 1)[1])
    messy = gold["label_bucket"] == "messy"
    currency = expected["currency"]
    subtotal_cents = round(expected["subtotal"] * 100)
    tax_cents = round(expected["tax"] * 100)
    total_cents = round(expected["total"] * 100)
    invoice_date = date.fromisoformat(expected["invoice_date"])
    pdf_lines = ["INVOICE", "Invoice number: {}".format(expected["invoice_no"])]
    if messy:
        # The vendor name appears only in the logo line, as specified for messy layouts.
        pdf_lines.insert(1, "[SUPPLIER LOGO: {}]".format(expected["vendor"]))
        date_format = ("%d %b %Y", "%m/%d/%Y", "%B %d, %Y")[index % 3]
        pdf_lines.append("Invoice date: {}".format(invoice_date.strftime(date_format)))
    else:
        pdf_lines.extend(("Vendor: {}".format(expected["vendor"]), "Invoice date: {}".format(invoice_date.isoformat())))
    pdf_lines.append("Currency: {}".format(currency))
    if messy and currency in ("EUR", "GBP"):
        pdf_lines.append("VAT @ 20%: {}".format(_format_amount(tax_cents, currency, european=True)))
    pdf_lines.append("Description                         Qty x Unit             Line total")
    for row in expected["line_items"]:
        unit_cents = round(row["unit_price"] * 100)
        line_cents = round(row["line_total"] * 100)
        european = messy and currency == "EUR"
        pdf_lines.append("{:<29} {:>2} x {:>12}   {:>12}".format(
            row["description"], row["quantity"], _format_amount(unit_cents, currency, european),
            _format_amount(line_cents, currency, european)))
    european = messy and currency == "EUR"
    pdf_lines.extend((
        "Subtotal: {}".format(_format_amount(subtotal_cents, currency, european)),
        "Tax: {}".format(_format_amount(tax_cents, currency, european)),
        "Total: {}".format(_format_amount(total_cents, currency, european)),
    ))
    return pdf_lines


def generate(out_dir=".", seed=20261005):
    """Write gold JSON first, then matching PDFs and the frozen 26-row manifest."""
    root = os.path.abspath(out_dir)
    inputs_dir = os.path.join(root, "evals", "inputs")
    gold_dir = os.path.join(root, "evals", "gold")
    os.makedirs(inputs_dir, exist_ok=True)
    os.makedirs(gold_dir, exist_ok=True)
    rng = random.Random(seed)
    manifest_rows = []
    for index in range(1, 27):
        bucket = "clean" if index <= 14 else "messy"
        gold = _make_invoice(index, bucket, rng, seed)
        gold_path = os.path.join(gold_dir, gold["input_id"] + ".json")
        with open(gold_path, "w", encoding="utf-8") as f:
            json.dump(gold, f, indent=2, sort_keys=True)
            f.write("\n")
        # Render only from the gold file, preserving I-2 even if construction changes later.
        with open(gold_path, encoding="utf-8") as f:
            saved_gold = json.load(f)
        pdf_path = os.path.join(inputs_dir, gold["input_id"] + ".pdf")
        render_pdf(_render_lines(saved_gold), pdf_path)
        manifest_rows.append((gold["input_id"], gold["input_id"] + ".pdf", bucket,
                              "evals/gold/{}.json".format(gold["input_id"])))

    manifest_path = os.path.join(inputs_dir, "manifest.csv")
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(MANIFEST_HEADER)
        writer.writerows(manifest_rows)
    return manifest_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=".", help="project root for evals/inputs and evals/gold")
    parser.add_argument("--seed", type=int, default=20261005)
    args = parser.parse_args(argv)
    print(generate(args.out_dir, args.seed))


if __name__ == "__main__":
    main()
