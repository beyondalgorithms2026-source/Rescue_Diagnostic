import csv
import json
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

    def test_replay_input_id_joins_scorecard_without_silent_drop(self):
        with tempfile.TemporaryDirectory() as temp:
            run_id = "REPLAY-ID"
            run_dir = os.path.join(temp, run_id)
            sink_dir = os.path.join(run_dir, "sink")
            os.makedirs(sink_dir)
            gold_path = os.path.join(temp, "gold.json")
            manifest_path = os.path.join(temp, "manifest.csv")
            with open(gold_path, "w", encoding="utf-8") as f:
                json.dump({"input_id": "t2-001", "label_bucket": "clean", "dedupe_key": "INV-1|acme|USD",
                           "expected": {"invoice_no": "INV-1", "vendor": "Acme", "invoice_date": "2026-01-01",
                                        "currency": "USD", "subtotal": 10, "tax": 1, "total": 11,
                                        "line_items": []}}, f)
            with open(manifest_path, "w", newline="", encoding="utf-8") as f:
                f.write("input_id,filename,label_bucket,gold_path\n")
                f.write("t2-001,t2-001.pdf,clean,{}\n".format(gold_path))
            with open(os.path.join(sink_dir, "invoices.csv"), "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=("sink_seq", "sink_ts", "replay_input_id", "replay_pass",
                                                        "run_id", "dedupe_key", "invoice_no", "vendor", "invoice_date",
                                                        "currency", "subtotal", "tax", "total"))
                writer.writeheader()
                writer.writerow({"sink_seq": "1", "sink_ts": "2026-01-01T00:00:00Z", "replay_input_id": "t2-001",
                                 "replay_pass": "A", "run_id": run_id, "dedupe_key": "INV-1|acme|USD",
                                 "invoice_no": "INV-1", "vendor": "Acme", "invoice_date": "2026-01-01",
                                 "currency": "USD", "subtotal": "10", "tax": "1", "total": "11"})
            with open(os.path.join(run_dir, "summary.json"), "w", encoding="utf-8") as f:
                json.dump({}, f)
            open(os.path.join(run_dir, "trace.jsonl"), "w", encoding="utf-8").close()
            rows = score(run_id, out=os.path.join(temp, "scorecard.csv"), runs_dir=temp,
                         manifest=manifest_path)
            self.assertEqual(rows[0]["invoice_no_hat"], "INV-1")
            self.assertNotIn("silent_drop", rows[0]["failure_codes"])


if __name__ == "__main__":
    unittest.main()
