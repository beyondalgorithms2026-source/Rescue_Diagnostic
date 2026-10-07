"""T7 replay runner tests use an in-process fake n8n and no network."""
import argparse
import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.replay import run


class FakeN8n:
    def __init__(self):
        self.calls = []
        self.next_id = 0

    def import_workflow(self, workflow):
        self.calls.append(("import", workflow["id"]))

    def publish(self, workflow_id):
        self.calls.append(("publish", workflow_id))

    def unpublish(self, workflow_id):
        self.calls.append(("unpublish", workflow_id))

    def credential_ids(self, names):
        return {name: "id-" + name for name in names}

    def latest_id(self, workflow_id):
        return self.next_id

    def wait_execution(self, workflow_id, after_id):
        self.next_id += 1
        return {"id": self.next_id, "started": "2026-10-06T00:00:00Z", "status": "success",
                "data": {"resultData": {"runData": {
                    run.equivalent.LLM: [{"startTime": "2026-10-06T00:00:00Z",
                                          "data": {"usage": {"prompt_tokens": 1000000,
                                                              "completion_tokens": 166667}}}]}}}}


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        workflow = {"id": "t2BaselineEquiv1", "nodes": [], "connections": {},
                    "sink": "__SINK_BASE_URL__", "path": "__WEBHOOK_PATH__"}
        self.workflow = self.root / "workflow.json"
        self.workflow.write_text(json.dumps(workflow), encoding="utf-8")
        self.manifest = self.root / "manifest.csv"
        with self.manifest.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=("input_id", "filename", "label_bucket", "gold_path"))
            writer.writeheader()
            for number in (1, 2):
                pdf = self.inputs / "t2-{:03d}.pdf".format(number)
                pdf.write_bytes(b"%PDF fake")
                gold = self.root / "gold-{}.json".format(number)
                gold.write_text(json.dumps({"input_id": "t2-{:03d}".format(number),
                                            "form": {"name": "A", "email": "a@example.com",
                                                     "currency": "USD", "notes": ""}, "fault": None}),
                                encoding="utf-8")
                writer.writerow({"input_id": "t2-{:03d}".format(number), "filename": pdf.name,
                                 "label_bucket": "clean", "gold_path": gold})

    def tearDown(self):
        self.temp.cleanup()

    def test_run_is_sequential_caps_and_unpublishes(self):
        args = argparse.Namespace(target="local", phase="baseline", baseline_mode="as-published", passes="AB",
                                  workflow=str(self.workflow), sqlite="unused", manifest=str(self.manifest),
                                  inputs_dir=str(self.inputs), runs_dir=str(self.root / "runs"),
                                  cost_ledger=str(self.root / "cost_ledger.csv"),
                                  repaired_workflow=str(self.root / "repaired.json"), start_sink=False)
        fake = FakeN8n()
        env = {"SINK_TOKEN": "sink", "T2_WEBHOOK_TOKEN": "webhook", "T2_WEBHOOK_PATH_BASELINE": "path",
               "SINK_BASE_URL": "http://sink.invalid", "N8N_BASE_URL": "http://n8n.invalid",
               "LLM_PRICE_IN_PER_MTOK": "0.15", "LLM_PRICE_OUT_PER_MTOK": "0.60", "RUN_USD_CAP": "0.25"}
        seen = []
        sink_urls = []
        with patch.dict(os.environ, env, clear=True), patch.object(run, "request_json", side_effect=lambda method, url, *_args, **_kwargs: sink_urls.append(url) or (200, {"ok": True})), \
                patch.object(run, "submit", side_effect=lambda *values: seen.append(values[3]["input_id"]) or 200):
            run_dir = run.run_replay(args, fake)
        self.assertEqual(seen, ["t2-001"])
        self.assertTrue(all(url.startswith("http://127.0.0.1:8787/") for url in sink_urls))
        self.assertEqual(fake.calls, [("import", "t2BaselineEquiv1"), ("publish", "t2BaselineEquiv1"),
                                      ("unpublish", "t2BaselineEquiv1")])
        events = [json.loads(line) for line in (run_dir / "trace.jsonl").read_text().splitlines()]
        self.assertEqual(sum(event.get("capped", False) for event in events), 3)
        self.assertEqual(json.loads((run_dir / "summary.json").read_text())["capped"], 3)
        with (self.root / "cost_ledger.csv").open(newline="", encoding="utf-8") as f:
            ledger = list(csv.DictReader(f))
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["run_usd_cap"], "0.25")

    def test_local_cli_uses_stdin_restarts_and_sqlite_is_read_only(self):
        calls = []
        class Result:
            returncode = 0
        def command(args, **kwargs):
            calls.append((args, kwargs.get("input")))
            return Result()
        database = self.root / "n8n.sqlite"
        import sqlite3
        with sqlite3.connect(database) as db:
            db.execute("CREATE TABLE execution_entity (id integer, workflowId text, status text, startedAt text, stoppedAt text)")
            db.execute("CREATE TABLE execution_data (executionId integer, data text)")
            db.execute("INSERT INTO execution_entity VALUES (1, 'wf', 'success', 's', 'e')")
            db.execute("INSERT INTO execution_data VALUES (1, ?)", (json.dumps({"resultData": {"runData": {}}}),))
        local = run.LocalN8n(database, command=command, sleeper=lambda _: None)
        local.import_workflow({"id": "wf"})
        local.publish("wf")
        local.unpublish("wf")
        self.assertEqual(local.latest_id("wf"), 1)
        self.assertEqual(local.wait_execution("wf", 0)["id"], 1)
        self.assertIn("--input=/dev/stdin", calls[0][0])
        self.assertEqual([call[0][0:2] for call in calls].count(["docker", "restart"]), 2)

    def test_submit_uses_the_equivalence_shim_binary_key(self):
        data, _ = run.multipart({}, run.equivalent.FILE_BINARY_KEY, "invoice.pdf", b"pdf", {})
        self.assertIn(b'name="Invoice_PDF"', data)

    def test_usage_reads_http_response_body(self):
        value = {"main": [[{"json": {"usage": {"prompt_tokens": 7, "completion_tokens": 3}}}]]}
        self.assertEqual(run._usage(value), (7, 3))

    def test_repairs_are_only_r1_and_r2(self):
        workflow = {"nodes": [{"name": "2. Extract From File — PDF to Text", "parameters": {}},
                              {"name": run.equivalent.LLM, "parameters": {"jsonBody":
                               "={\"content\": {{ JSON.stringify(\"p\") + $('2. Extract From File — PDF to Text').first().json.text }}\"}"}}]}
        repaired = run.repaired_to_run(workflow)
        self.assertEqual(repaired["nodes"][0]["parameters"]["binaryPropertyName"], "Invoice_PDF")
        self.assertIn("={{ JSON.stringify({\"content\":(\"p\" + $('2. Extract From File — PDF to Text').first().json.text)}) }}",
                      repaired["nodes"][1]["parameters"]["jsonBody"])
        self.assertNotIn("binaryPropertyName", workflow["nodes"][0]["parameters"])
        output = self.root / "repaired.json"
        source = self.root / "source.json"
        source.write_text(json.dumps(workflow), encoding="utf-8")
        run.materialize_repaired_baseline(source, output)
        self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
