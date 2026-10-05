import csv
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from src.common.norm import dedupe_key
from src.fixtures.make_inputs import MAX_INPUT_CHARS, generate
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

    def test_generates_full_mix_and_valid_gold_pdf_pairs(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest_path = generate(temp, seed=71)
            with open(manifest_path, newline="", encoding="utf-8") as f:
                manifest = list(csv.DictReader(f))
            self.assertEqual(list(manifest[0]), ["input_id", "filename", "label_bucket", "gold_path"])
            self.assertEqual(len(manifest), 50)
            self.assertEqual([r["input_id"] for r in manifest], ["t2-{:03d}".format(i) for i in range(1, 51)])
            self.assertEqual({bucket: sum(r["label_bucket"] == bucket for r in manifest) for bucket in
                              ("clean", "messy", "duplicate", "missing_field", "injection", "oversized")},
                             {"clean": 14, "messy": 12, "duplicate": 8, "missing_field": 6,
                              "injection": 6, "oversized": 4})
            mismatched_forms = 0
            unfooted = 0
            gold_by_id = {}
            pdf_by_id = {}
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
                self.assertEqual(gold["generator"]["seed"], 71)
                self.assertEqual(gold["generator"]["version"], "1.0")
                self.assertEqual(gold["input_id"], row["input_id"])
                self.assertEqual(gold["label_bucket"], row["label_bucket"])
                self.assertEqual(gold["dedupe_key"], dedupe_key(
                    gold["expected"]["invoice_no"], gold["expected"]["vendor"], gold["expected"]["currency"]))
                self.assertIn(FOOTER.encode("cp1252"), pdf)
                self.assertEqual(pdf.count(FOOTER.encode("cp1252")), 1)
                self.assertEqual(pdf.count(b"/Type /Page "), int(re.search(rb"/Count (\d+)", pdf).group(1)))
                self.assertIn(gold["expect_outcome"], ("committed", "review", "duplicate_skip", "rejected"))
                self.assertIn(gold["expected"]["currency"], ("USD", "EUR", "GBP", None))
                self.assertEqual(gold["form"]["email"], "ap@example.com")
                gold_by_id[row["input_id"]] = gold
                pdf_by_id[row["input_id"]] = pdf
                if row["label_bucket"] == "clean":
                    self.assertIn(b"/Count 1", pdf)
                if row["label_bucket"] == "messy" and gold["form"]["currency"] != gold["expected"]["currency"]:
                    mismatched_forms += 1
                if not gold["doc_foots"]:
                    unfooted += 1
            self.assertEqual(mismatched_forms, 2)
            self.assertEqual(unfooted, 2)
            self.assertEqual([i for i in range(1, 51) if gold_by_id["t2-{:03d}".format(i)]["fault"]],
                             [3, 9, 17, 22])
            for index in (27, 28):
                key = "t2-{:03d}".format(index)
                self.assertEqual(pdf_by_id[key], pdf_by_id[gold_by_id[key]["duplicate_of"]])
            for index in range(27, 33):
                gold = gold_by_id["t2-{:03d}".format(index)]
                self.assertEqual(gold["expect_outcome"], "duplicate_skip")
                self.assertEqual(gold["dedupe_key"], gold_by_id[gold["duplicate_of"]]["dedupe_key"])
            for index in (33, 34):
                gold = gold_by_id["t2-{:03d}".format(index)]
                source = gold_by_id[gold["duplicate_of"]]
                self.assertEqual(gold["expected"]["invoice_no"], source["expected"]["invoice_no"])
                self.assertNotEqual(gold["dedupe_key"], source["dedupe_key"])
            self.assertEqual([gold_by_id["t2-{:03d}".format(i)]["expect_outcome"] for i in range(35, 41)],
                             ["rejected", "rejected", "review", "review", "rejected", "review"])
            for index in range(41, 47):
                gold = gold_by_id["t2-{:03d}".format(index)]
                payload = next(iter(gold["injection"]["target"].values())).encode("ascii")
                location = gold["injection"]["location"]
                self.assertIn(payload, pdf_by_id[gold["input_id"]] if location == "pdf" else
                              gold["form"]["notes"].encode("ascii"))
            self.assertEqual([gold_by_id["t2-{:03d}".format(i)]["injection"]["location"]
                              for i in range(41, 47)], ["notes"] * 3 + ["pdf"] * 3)
            for index in range(47, 51):
                key = "t2-{:03d}".format(index)
                # PDF content streams preserve each rendered text line in this writer.
                text_length = sum(len(line) for line in re.findall(rb"\((.*?)\) Tj", pdf_by_id[key]))
                self.assertEqual(text_length > MAX_INPUT_CHARS, index <= 48)

    def test_repeated_seed_produces_byte_identical_output(self):
        with tempfile.TemporaryDirectory() as temp:
            left, right = os.path.join(temp, "left"), os.path.join(temp, "right")
            generate(left, seed=111)
            generate(right, seed=111)
            for relative in (
                "evals/inputs/manifest.csv",
                "evals/inputs/t2-001.pdf",
                "evals/inputs/t2-026.pdf",
                "evals/inputs/t2-050.pdf",
                "evals/gold/t2-001.json",
                "evals/gold/t2-026.json",
                "evals/gold/t2-050.json",
            ):
                first = Path(left, relative).read_bytes()
                second = Path(right, relative).read_bytes()
                self.assertEqual(first, second, relative)


if __name__ == "__main__":
    unittest.main()
