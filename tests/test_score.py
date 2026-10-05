import csv
import os
import tempfile
import unittest

from src.score.score import HEADER, score


FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "stub_run")


class ScorerTests(unittest.TestCase):
    def test_stub_scorecard_contract_and_findings(self):
        with tempfile.TemporaryDirectory() as temp:
            out = os.path.join(temp, "scorecard.csv")
            rows = score("STUB-baseline", "STUB-hardened", out,
                         runs_dir=FIXTURE, manifest=os.path.join(FIXTURE, "manifest.csv"))
            with open(out, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                self.assertEqual(next(reader), HEADER)
                self.assertEqual(len(list(reader)), 6)
            baseline = {r["input_id"]: r for r in rows if r["run_phase"] == "baseline"}
            hardened = {r["input_id"]: r for r in rows if r["run_phase"] == "hardened"}
            self.assertGreater(baseline["stub-002"]["write_count"], 1)
            codes = {c for r in baseline.values() for c in r["failure_codes"].split("|") if c}
            self.assertTrue({"duplicate_write", "validate_skip", "silent_drop", "audit_gap"}.issubset(codes))
            self.assertTrue(all(not r["failure_codes"] for r in hardened.values()))
            self.assertEqual(baseline["stub-003"]["invoice_date_ok"], 1)
            self.assertEqual(baseline["stub-003"]["invoice_no_hat"], "")
            self.assertEqual(baseline["stub-001"]["tax_ok"], 1)


if __name__ == "__main__":
    unittest.main()
