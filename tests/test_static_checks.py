import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

from src.checks.static_checks import audit_workflow, check_file, main, scan_secrets


class StaticCheckTests(unittest.TestCase):
    def test_clean_external_node(self):
        report, violations = audit_workflow({"nodes": [{
            "name": "HTTP call", "type": "httpRequest", "onError": "continueErrorOutput",
            "retryOnFail": True, "maxTries": 3, "parameters": {"options": {"timeout": 60000}},
        }]})
        self.assertEqual(violations, [])
        self.assertEqual(report, [{"name": "HTTP call", "type": "httpRequest", "onError": "continueErrorOutput",
                                  "retry": True, "maxTries": 3, "timeout": 60000}])

    def test_missing_error_handling_unbounded_retry_and_timeout(self):
        report, violations = audit_workflow({"nodes": [{
            "name": "Bad HTTP", "type": "httpRequest", "retryOnFail": True, "maxTries": 4,
            "parameters": {"options": {}},
        }]})
        self.assertEqual(report[0]["onError"], None)
        self.assertEqual(len(violations), 3)
        self.assertIn("Bad HTTP: external node has no onError", violations)
        self.assertTrue(any("maxTries" in v for v in violations))
        self.assertTrue(any("timeout" in v for v in violations))

    def test_secret_scan_reports_location_without_secret_text(self):
        marker = "Bearer " + ("A" * 20)
        findings = scan_secrets('{"authorization": "' + marker + '"}')
        self.assertEqual(findings, [{"pattern": r"Bearer [A-Za-z0-9._-]{20,}", "line": 1}])
        self.assertNotIn(marker, json.dumps(findings))

    def test_documented_secret_pattern_families(self):
        samples = [
            "sk-" + ("A" * 20), "sk-proj-", "ya29." + ("x" * 8),
            "AIza" + ("A" * 35), "Bearer " + ("A" * 20),
            '"access_token": "example"', '"apiKey": "x"',
            "-----BEGIN RSA PRIVATE KEY-----",
        ]
        self.assertEqual(len(scan_secrets("\n".join(samples))), len(samples))

    def test_cli_writes_frozen_report_and_strict_status(self):
        with tempfile.TemporaryDirectory() as temp:
            workflow_path = os.path.join(temp, "workflow.json")
            out_path = os.path.join(temp, "static_checks.json")
            with open(workflow_path, "w", encoding="utf-8") as f:
                json.dump({"nodes": [{"name": "HTTP", "type": "httpRequest", "parameters": {}}]}, f)
            with redirect_stdout(StringIO()):
                status = main([workflow_path, "--out", out_path, "--strict"])
            with open(out_path, encoding="utf-8") as f:
                result = json.load(f)
            self.assertEqual(status, 1)
            self.assertEqual(set(result), {"file", "sha256", "secrets", "nodes", "violations"})
            self.assertEqual(set(result["nodes"][0]), {"name", "type", "onError", "retry", "maxTries", "timeout"})
            with redirect_stdout(StringIO()):
                status = main([workflow_path, "--out", out_path])
            self.assertEqual(status, 0)

    def test_strict_clean_workflow_exits_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            workflow_path = os.path.join(temp, "workflow.json")
            with open(workflow_path, "w", encoding="utf-8") as f:
                json.dump({"nodes": [{
                    "name": "HTTP", "type": "n8n-nodes-base.httpRequest", "onError": "continueErrorOutput",
                    "parameters": {"options": {"timeout": 5000}},
                }]}, f)
            with redirect_stdout(StringIO()):
                status = main([workflow_path, "--out", os.path.join(temp, "report.json"), "--strict"])
            self.assertEqual(status, 0)


if __name__ == "__main__":
    unittest.main()
