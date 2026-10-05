import csv
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.sink.server import COLUMNS, make_server


class SinkTests(unittest.TestCase):
    @staticmethod
    def invoice(**values):
        row = {column: "" for column in COLUMNS["invoices"]}
        row.update(values)
        return row

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = make_server(self.temp.name, "test-token", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:{}".format(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, method, path, body=None, token="test-token"):
        headers = {"X-Sink-Token": token}
        data = None if body is None else json.dumps(body).encode("utf-8")
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_auth_lookup_stamps_and_append_only(self):
        self.assertEqual(self.request("GET", "/_health", token="wrong")[0], 401)
        self.assertEqual(self.request("GET", "/_health", token="")[0], 401)
        self.assertEqual(self.request("GET", "/_health"), (200, {"ok": True}))
        self.assertEqual(self.request("POST", "/_replay/active", {"input_id": "t2-001", "pass": "A"})[0], 200)
        payload = self.invoice(run_id="run-1", dedupe_key="INV-1|vendor|USD", invoice_no="INV-1")
        first = self.request("POST", "/append/invoices", payload)
        second = self.request("POST", "/append/invoices", payload)
        self.assertEqual((first[0], second[0]), (200, 200))
        self.assertEqual(first[1]["row"]["sink_seq"], "1")
        self.assertEqual(second[1]["row"]["sink_seq"], "2")
        self.assertEqual(first[1]["row"]["replay_input_id"], "t2-001")
        self.assertEqual(first[1]["row"]["replay_pass"], "A")
        self.assertTrue(first[1]["row"]["sink_ts"])
        status, match = self.request("GET", "/lookup/invoices?dedupe_key=INV-1%7Cvendor%7CUSD")
        self.assertEqual((status, match["count"]), (200, 2))
        self.assertEqual(len(match["rows"]), 2)
        self.assertEqual(self.request("GET", "/lookup/invoices?dedupe_key=missing")[1]["count"], 0)
        self.assertEqual(self.request("POST", "/append/unknown", payload)[0], 400)
        self.assertEqual(self.request("GET", "/lookup/unknown?run_id=run-1")[0], 400)
        self.assertEqual(self.request("POST", "/append/invoices", {"not_a_column": 1})[0], 400)
        self.assertEqual(self.request("POST", "/append/invoices", {"sink_seq": 999})[0], 400)
        with Path(self.temp.name, "invoices.csv").open(newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        self.assertEqual(len(rows), 3)  # one header plus two appends
        self.assertEqual(rows[0][:4], ["sink_seq", "sink_ts", "replay_input_id", "replay_pass"])
        events = [json.loads(line) for line in Path(self.temp.name, "requests.jsonl").read_text().splitlines()]
        self.assertEqual(events[0]["status"], 401)
        self.assertEqual(events[0]["path"], "/_health")
        self.assertEqual(events[-1]["active_input"], "t2-001")
        self.assertNotIn("test-token", Path(self.temp.name, "requests.jsonl").read_text())

    def test_fault_is_one_shot_and_only_hits_matching_append(self):
        self.request("POST", "/_replay/active", {"input_id": "t2-003", "pass": "A"})
        self.assertEqual(self.request("POST", "/_replay/fault", {"target": "invoices", "status": 503,
                                                               "pass": "A", "times": 1})[0], 200)
        payload = self.invoice(run_id="run-1", invoice_no="INV-3")
        self.assertEqual(self.request("POST", "/append/invoices", payload)[0], 503)
        self.assertEqual(self.request("GET", "/lookup/invoices?run_id=run-1")[1]["count"], 0)
        self.assertEqual(self.request("POST", "/append/invoices", payload)[0], 200)
        self.request("POST", "/_replay/fault", {"target": "invoices", "status": 500,
                                                  "pass": "B", "times": 1})
        self.assertEqual(self.request("POST", "/append/invoices", payload)[0], 200)
        self.request("POST", "/_replay/active", {"input_id": "t2-004", "pass": "B"})
        self.assertEqual(self.request("POST", "/append/invoices", payload)[0], 200)
        self.assertEqual(self.request("POST", "/_replay/fault", {})[0], 200)

    def test_ledger_sum_count_and_restart_sequence(self):
        self.request("POST", "/_replay/active", {"input_id": "t2-007", "pass": "A"})
        for amount in ("0.01", "0.02"):
            self.assertEqual(self.request("POST", "/append/ledger", {"run_id": "run-7", "usd": amount})[0], 200)
        self.request("POST", "/append/ledger", {"run_id": "other", "usd": "1.00"})
        self.assertEqual(self.request("GET", "/ledger/sum?run_id=run-7"), (200, {"usd": 0.03}))
        self.assertEqual(self.request("GET", "/ledger/count?run_id=run-7&since_s=60"), (200, {"count": 2}))
        self.assertEqual(self.request("GET", "/ledger/count?run_id=run-7&since_s=bad")[0], 400)
        self.assertEqual(self.request("GET", "/ledger/sum")[0], 400)
        with make_server(self.temp.name, "test-token", port=0) as restarted:
            self.assertEqual(restarted.state.seq, 3)
        self.assertEqual(self.request("POST", "/append/outbox", {"to": "ap@example.com", "subject": "Test"})[1]["row"]["sink_seq"], "4")

    def test_empty_token_refuses_start(self):
        with self.assertRaises(ValueError):
            make_server(self.temp.name, "", port=0)


if __name__ == "__main__":
    unittest.main()
