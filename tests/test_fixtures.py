import csv
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from src.fixtures.make_inputs import generate
from src.fixtures.pdfwriter import FOOTER, render_pdf


class FixtureGeneratorTests(unittest.TestCase):
    def test_pdf_14_writer_pages_and_footer(self):
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "multi.pdf")
            render_pdf(["line {}".format(i) for i in range(7)], path, lines_per_page=3)
            pdf = Path(path).read_bytes()
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"/Count 3", pdf)
        self.assertEqual(pdf.count(b"/Type /Page "), 3)
        self.assertEqual(pdf.count(FOOTER.encode("cp1252")), 1)
        startxref = int(re.search(rb"startxref\n(\d+)", pdf).group(1))
        self.assertEqual(pdf[startxref:startxref + 4], b"xref")

    def test_generates_exact_clean_messy_mix_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest_path = generate(temp, seed=71)
            with open(manifest_path, newline="", encoding="utf-8") as f:
                manifest = list(csv.DictReader(f))
            self.assertEqual(list(manifest[0]), ["input_id", "filename", "label_bucket", "gold_path"])
            self.assertEqual(len(manifest), 26)
            self.assertEqual(sum(r["label_bucket"] == "clean" for r in manifest), 14)
            self.assertEqual(sum(r["label_bucket"] == "messy" for r in manifest), 12)
            mismatched_forms = 0
            unfooted = 0
            for row in manifest:
                with open(os.path.join(temp, row["gold_path"]), encoding="utf-8") as f:
                    gold_text = f.read()
                gold = json.loads(gold_text)
                pdf_path = os.path.join(temp, "evals", "inputs", row["filename"])
                pdf = Path(pdf_path).read_bytes()
                self.assertEqual(set(gold), {
                    "input_id", "synthetic", "label_bucket", "form", "expected", "dedupe_key",
                    "expect_outcome", "duplicate_of", "injection", "fault", "doc_foots", "generator",
                })
                self.assertEqual(set(gold["form"]), {"name", "email", "currency", "notes"})
                self.assertEqual(set(gold["expected"]), {
                    "invoice_no", "vendor", "invoice_date", "currency", "subtotal", "tax", "total", "line_items",
                })
                self.assertTrue(gold["synthetic"])
                self.assertEqual(gold["input_id"], row["input_id"])
                self.assertEqual(gold["label_bucket"], row["label_bucket"])
                self.assertIsNotNone(gold["dedupe_key"])
                self.assertIn(FOOTER.encode("cp1252"), pdf)
                self.assertGreaterEqual(len(gold["expected"]["line_items"]), 1)
                self.assertLessEqual(len(gold["expected"]["line_items"]), 8)
                if row["label_bucket"] == "clean":
                    self.assertIn(b"/Count 1", pdf)
                if gold["form"]["currency"] != gold["expected"]["currency"]:
                    mismatched_forms += 1
                if not gold["doc_foots"]:
                    unfooted += 1
            self.assertEqual(mismatched_forms, 2)
            self.assertEqual(unfooted, 2)

    def test_repeated_seed_produces_byte_identical_output(self):
        with tempfile.TemporaryDirectory() as temp:
            left, right = os.path.join(temp, "left"), os.path.join(temp, "right")
            generate(left, seed=111)
            generate(right, seed=111)
            for relative in (
                "evals/inputs/manifest.csv",
                "evals/inputs/t2-001.pdf",
                "evals/inputs/t2-026.pdf",
                "evals/gold/t2-001.json",
                "evals/gold/t2-026.json",
            ):
                first = Path(left, relative).read_bytes()
                second = Path(right, relative).read_bytes()
                self.assertEqual(first, second, relative)


if __name__ == "__main__":
    unittest.main()
