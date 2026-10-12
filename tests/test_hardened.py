"""T10 structure tests for the hardened workflow, plus the §3.5 normalizer vectors run under node."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from src.common.norm import invoice_no_norm, vendor_norm

HARDENED = Path("workflows/hardened/t2-hardened.json")
HANDLER = Path("workflows/hardened/t2-error-handler.json")
VECTORS = [  # ARCHITECTURE §3.5
    (" inv-00042 ", "invoice_no", "INV-00042"),
    ("INV 00042", "invoice_no", "INV00042"),
    ("Harbour & Finch Ltd.", "vendor", "harbour and finch"),
    ("HARBOUR AND FINCH LIMITED", "vendor", "harbour and finch"),
    ("Müller Druck GmbH", "vendor", "müller druck"),
    ("Acme Co. Inc.", "vendor", "acme"),
    ("Co-Op Supplies LLC", "vendor", "co op supplies"),
    ("Blue Heron S.A.S.", "vendor", "blue heron s a s"),
]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class HardenedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = load(HARDENED)
        self.nodes = {n["name"]: n for n in self.workflow["nodes"]}

    def test_every_stage_node_exists_and_connections_resolve(self):
        for name in ("H8 Schema Gate", "H10 Reject?", "H10 Review?", "H11 Dedupe Lookup", "H12 Line Append",
                     "H13 Header Append", "H14 Report Build", "H15 Review Append", "H16 Audit Append"):
            self.assertIn(name, self.nodes)
        for source, outputs in self.workflow["connections"].items():
            self.assertIn(source, self.nodes)
            for output in outputs["main"]:
                for edge in output:
                    self.assertIn(edge["node"], self.nodes)

    def test_external_calls_authenticate_and_have_connected_error_outputs(self):
        for node in self.workflow["nodes"]:
            if not node["type"].endswith(".httpRequest"):
                continue
            self.assertEqual(node["parameters"].get("authentication"), "genericCredentialType", node["name"])
            self.assertEqual(node["parameters"].get("genericAuthType"), "httpHeaderAuth", node["name"])
            self.assertEqual(list(node["credentials"]), ["httpHeaderAuth"])
            self.assertEqual(node.get("onError"), "continueErrorOutput", node["name"])
            outputs = self.workflow["connections"].get(node["name"], {}).get("main", [])
            self.assertEqual(len(outputs), 2, node["name"])
            self.assertTrue(outputs[1], node["name"] + " error output is not connected")

    def test_header_is_written_after_line_items(self):
        conn = self.workflow["connections"]
        self.assertEqual(conn["H12 Line Append"]["main"][0][0]["node"], "H13 Header Build")
        self.assertEqual(conn["H13 Header Build"]["main"][0][0]["node"], "H13 Header Append")

    def test_config_keeps_input_and_notes_never_reach_the_model(self):
        self.assertTrue(self.nodes["0. Config"]["parameters"]["includeOtherFields"])
        body = self.nodes["H6 LLM Extract"]["parameters"]["jsonBody"]
        self.assertNotIn("notes", body.lower())
        self.assertIn("json_object", body)
        self.assertIn("json", body.split("system", 1)[1].lower())

    def test_if_operators_exist_in_n8n_filter_engine(self):
        # n8n-workflow 2.22.5 filter-parameter.js accepts only these operation names.
        valid = {"equals", "notEquals", "contains", "notContains", "startsWith", "notStartsWith", "endsWith",
                 "notEndsWith", "regex", "notRegex", "empty", "notEmpty", "gt", "gte", "lt", "lte", "true", "false"}
        for node in self.workflow["nodes"]:
            if node["type"].endswith(".if"):
                for cond in node["parameters"]["conditions"]["conditions"]:
                    self.assertIn(cond["operator"]["operation"], valid, node["name"])

    def test_webhook_has_fixed_webhook_id(self):
        hook = self.nodes["0. Webhook — Replay Intake"]
        self.assertTrue(hook.get("webhookId"), "without webhookId n8n prefixes the path with the workflow id")

    def test_error_workflow_points_at_the_handler(self):
        self.assertEqual(self.workflow["settings"]["errorWorkflow"], load(HANDLER)["id"])

    def test_no_env_and_no_literal_urls_for_sink(self):
        text = HARDENED.read_text(encoding="utf-8")
        self.assertNotIn("$env", text)
        self.assertNotIn("host.docker.internal", text)
        self.assertNotIn("127.0.0.1", text)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class HardenedJavaScriptTests(unittest.TestCase):
    def run_node(self, script):
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_js_normalizer_matches_vectors_and_python(self):
        code = {n["name"]: n for n in load(HARDENED)["nodes"]}["H8 Schema Gate"]["parameters"]["jsCode"]
        block = code[code.index("// NORM-BEGIN"):code.index("// NORM-END")]
        cases = [[value, kind] for value, kind, _ in VECTORS]
        out = self.run_node(block + "\nprocess.stdout.write(JSON.stringify(" + json.dumps(cases) +
                            ".map(([v, k]) => k === 'invoice_no' ? invoiceNoNorm(v) : vendorNorm(v))));")
        for (value, kind, expected), got in zip(VECTORS, out):
            python = invoice_no_norm(value) if kind == "invoice_no" else vendor_norm(value)
            self.assertEqual(got, expected, value)
            self.assertEqual(got, python, value)

    def test_js_sha256_matches_hashlib(self):
        import hashlib
        code = {n["name"]: n for n in load(HARDENED)["nodes"]}["H1 PDF SHA-256"]["parameters"]["jsCode"]
        block = code[code.index("// SHA256-BEGIN"):code.index("// SHA256-END")]
        pdf = Path("evals/inputs/t2-047.pdf").read_bytes()
        samples = [b"", b"abc", bytes(range(256)) * 3, pdf]
        hexes = [s.hex() for s in samples]
        out = self.run_node(block + "\nprocess.stdout.write(JSON.stringify(" + json.dumps(hexes) +
                            ".map((h) => sha256Hex(Uint8Array.from(Buffer.from(h, 'hex'))))));")
        self.assertEqual(out, [hashlib.sha256(s).hexdigest() for s in samples])

    def test_report_escapes_injected_html(self):
        code = {n["name"]: n for n in load(HARDENED)["nodes"]}["H14 Report Build"]["parameters"]["jsCode"]
        gate = {"run_id": "r", "submitter_email": "ap@example.com", "report_recipient_allowlist": "example.com",
                "invoice": {"invoice_no": "INV-1", "vendor": "<b>Injected report text</b>", "invoice_date": "2026-01-01",
                            "currency": "USD", "total": 1, "line_items": [{"description": "<img src=x>", "line_total": 1}]}}
        stub = "const $ = () => ({ first: () => ({ json: " + json.dumps(gate) + " }) });\n"
        out = self.run_node(stub + "const r = (() => {" + code + "})();\nprocess.stdout.write(JSON.stringify(r));")
        html = out[0]["json"]["html"]
        self.assertNotIn("<b>", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;b&gt;", html)
        self.assertTrue(out[0]["json"]["send"])
        gate["submitter_email"] = "report@example.invalid"
        stub = "const $ = () => ({ first: () => ({ json: " + json.dumps(gate) + " }) });\n"
        out = self.run_node(stub + "const r = (() => {" + code + "})();\nprocess.stdout.write(JSON.stringify(r));")
        self.assertFalse(out[0]["json"]["send"])


if __name__ == "__main__":
    unittest.main()
