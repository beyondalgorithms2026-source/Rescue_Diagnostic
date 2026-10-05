import unittest
from decimal import Decimal

from src.common.norm import (dedupe_key, invoice_no_norm, vendor_norm, parse_amount,
                             parse_currency, parse_date, map_legacy_tax)


class NormalizerTests(unittest.TestCase):
    def test_architecture_vectors(self):
        self.assertEqual(invoice_no_norm(" inv-00042 "), "INV-00042")
        self.assertEqual(invoice_no_norm("INV 00042"), "INV00042")
        vectors = {
            "Harbour & Finch Ltd.": "harbour and finch",
            "HARBOUR AND FINCH LIMITED": "harbour and finch",
            "Müller Druck GmbH": "müller druck",
            "Acme Co. Inc.": "acme",
            "Co-Op Supplies LLC": "co op supplies",
            "Blue Heron S.A.S.": "blue heron s a s",
        }
        for actual, expected in vectors.items():
            self.assertEqual(vendor_norm(actual), expected)

    def test_dedupe_key_and_missing_parts(self):
        self.assertEqual(dedupe_key("inv-42", "Harbour & Finch Ltd.", "$"), "INV-42|harbour and finch|USD")
        self.assertIsNone(dedupe_key(None, "Vendor", "USD"))

    def test_amount_date_currency_and_tax_mapping(self):
        self.assertEqual(parse_amount("1,234.56"), Decimal("1234.56"))
        self.assertEqual(parse_amount("1.234,56"), Decimal("1234.56"))
        self.assertIsNone(parse_amount("1,234"))
        self.assertEqual(parse_date("2026-03-12").isoformat(), "2026-03-12")
        self.assertEqual(parse_date("12 Mar 2026").isoformat(), "2026-03-12")
        self.assertEqual(parse_date("March 12, 2026").isoformat(), "2026-03-12")
        self.assertIsNone(parse_date("03/12/2026"))
        self.assertEqual(parse_date("13/03/2026").isoformat(), "2026-03-13")
        self.assertEqual(parse_currency("£"), "GBP")
        self.assertEqual(map_legacy_tax({"total_cgst": "4.00", "total_sgst": "4.00"}), Decimal("8.00"))
        self.assertIsNone(map_legacy_tax({"total_cgst": "", "total_sgst": ""}))


if __name__ == "__main__":
    unittest.main()
