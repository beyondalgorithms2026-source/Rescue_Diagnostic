"""T6 baseline equivalence tests.

The synthetic workflow below only mimics the node names and types of template 16643; it is not the
upstream JSON (Q-3). If the operator has fetched the real template, the same checks also run on it.
"""
import copy
import json
import os
import unittest

from src.baseline import equivalent as eq
from src.baseline.fetch import ORIGINAL_PATH, TEMPLATE_ID, TEMPLATE_NAME, extract_workflow
from src.checks.static_checks import scan_secrets


def _sheet(name, columns):
    return {
        "id": "id-" + name, "name": name, "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5,
        "position": [100, 100], "parameters": {
            "operation": "append",
            "columns": {"mappingMode": "defineBelow",
                        "value": {c: "={{ $json.k" + str(i) + " }}" for i, c in enumerate(columns)},
                        "schema": [{"id": c} for c in reversed(columns)]},
        },
    }


def synthetic_template():
    header_cols = ["H{}".format(i) for i in range(12)]
    line_cols = ["L{}".format(i) for i in range(12)]
    names = [eq.FORM, "2. Extract From File — PDF to Text", eq.LLM, "4. Code — Parse Invoice JSON Safely",
             eq.HEADER, "5b. Split Out — Line Items", "6. Code — Add Unique Key and Line Metadata",
             eq.LINES, "8. Aggregate — Collect All Line Items", eq.VERIFY, eq.GMAIL]
    nodes = [
        {"id": "s", "name": "Overview", "type": "n8n-nodes-base.stickyNote", "position": [0, 0],
         "parameters": {"content": "note"}},
        {"id": "f", "name": eq.FORM, "type": "n8n-nodes-base.formTrigger", "typeVersion": 2.2,
         "position": [0, 300], "webhookId": "w", "parameters": {"formFields": {"values": [
             {"fieldLabel": "Your Name"}, {"fieldLabel": "Your Email"},
             {"fieldLabel": eq.FILE_FIELD, "fieldType": "file"},
             {"fieldLabel": "Currency", "fieldType": "dropdown"}, {"fieldLabel": "Notes"}]}}},
        {"id": "x", "name": names[1], "type": "n8n-nodes-base.extractFromFile", "parameters": {"operation": "pdf"}},
        {"id": "l", "name": eq.LLM, "type": "n8n-nodes-base.httpRequest", "parameters": {
            "jsonBody": '={ "model": "gpt-4o-mini", "messages": [] }', "options": {"timeout": 60000}}},
        {"id": "p", "name": names[3], "type": "n8n-nodes-base.code", "parameters": {"jsCode": "return [];"}},
        _sheet(eq.HEADER, header_cols),
        {"id": "o", "name": names[5], "type": "n8n-nodes-base.splitOut", "parameters": {}},
        {"id": "m", "name": names[6], "type": "n8n-nodes-base.code", "parameters": {"jsCode": "return {};"}},
        _sheet(eq.LINES, line_cols),
        {"id": "a", "name": names[8], "type": "n8n-nodes-base.aggregate", "parameters": {}},
        {"id": "v", "name": eq.VERIFY, "type": "n8n-nodes-base.code", "parameters": {"jsCode": "return [];"}},
        {"id": "g", "name": eq.GMAIL, "type": "n8n-nodes-base.gmail", "typeVersion": 2.1, "position": [900, 300],
         "webhookId": "g", "parameters": {"sendTo": "={{ $json.email }}", "subject": "={{ $json.emailSubject }}",
                                          "message": "={{ $json.htmlEmail }}", "options": {}}},
    ]
    for node in nodes:
        node.setdefault("position", [0, 0])
    chain = [(names[i], names[i + 1]) for i in range(len(names) - 1) if names[i] != eq.HEADER]
    connections = {}
    for source, target in chain:
        if source == names[3]:
            continue
        connections[source] = {"main": [[{"node": target, "type": "main", "index": 0}]]}
    connections[names[3]] = {"main": [[{"node": eq.HEADER, "type": "main", "index": 0},
                                       {"node": names[5], "type": "main", "index": 0}]]}
    return {"name": "synthetic", "nodes": nodes, "connections": connections, "settings": {}, "versionId": "v"}


def assert_equivalent(test, original, result):
    before = {n["name"]: n for n in original["nodes"]}
    after = {n["name"]: n for n in result["nodes"]}
    test.assertEqual(set(after), set(before) | set(eq.ADDED))
    for name, node in before.items():
        if name not in eq.SWAPPED + eq.CHANGED:
            test.assertEqual(after[name], node, name + " must be unchanged")

    llm_before, llm_after = before[eq.LLM], after[eq.LLM]
    test.assertEqual({k: v for k, v in llm_after.items() if k not in ("parameters", "credentials")},
                     {k: v for k, v in llm_before.items() if k != "parameters"})
    params_before = copy.deepcopy(llm_before["parameters"])
    params_before["jsonBody"] = params_before["jsonBody"].replace(eq.UPSTREAM_MODEL, eq.PINNED_MODEL)
    test.assertEqual(llm_after["parameters"], params_before)
    test.assertEqual(llm_after["credentials"], {"openAiApi": {"name": "t2-openai"}})

    for name, table in ((eq.HEADER, "invoices"), (eq.LINES, "line_items")):
        node = after[name]
        test.assertTrue(node["type"].endswith(".httpRequest"))
        test.assertEqual(node["parameters"]["url"], eq.SINK_PLACEHOLDER + "/append/" + table)
        test.assertEqual(node["credentials"], {"httpHeaderAuth": {"name": "t2-sink-auth"}})
        test.assertEqual(node["position"], before[name]["position"])
        sent = {p["name"]: p["value"] for p in node["parameters"]["bodyParameters"]["parameters"]}
        test.assertEqual(sent, before[name]["parameters"]["columns"]["value"])
        test.assertNotIn("retryOnFail", node)
        test.assertNotIn("onError", node)

    gmail = before[eq.GMAIL]["parameters"]
    outbox = {p["name"]: p["value"] for p in after[eq.GMAIL]["parameters"]["bodyParameters"]["parameters"]}
    test.assertEqual(outbox, {"to": gmail["sendTo"], "subject": gmail["subject"], "html": gmail["message"]})
    test.assertEqual(after[eq.GMAIL]["parameters"]["url"], eq.SINK_PLACEHOLDER + "/append/outbox")

    form = after[eq.FORM]
    test.assertTrue(form["type"].endswith(".code"))
    test.assertIn("'" + eq.FILE_BINARY_KEY + "'", form["parameters"]["jsCode"])
    webhook = after[eq.WEBHOOK]
    test.assertEqual(webhook["parameters"]["path"], eq.WEBHOOK_PLACEHOLDER)
    test.assertEqual(webhook["parameters"]["authentication"], "headerAuth")
    test.assertEqual(webhook["credentials"], {"httpHeaderAuth": {"name": "t2-webhook-auth"}})

    def edges(connections):
        return sorted((s, e["node"]) for s, c in connections.items() for out in c["main"] for e in out)
    expected = [(s, t) for s, t in edges(original["connections"]) if (s, t) != (eq.VERIFY, eq.GMAIL)]
    expected += [(eq.WEBHOOK, eq.FORM), (eq.VERIFY, eq.RECIPIENT_CHECK), (eq.RECIPIENT_CHECK, eq.GMAIL)]
    test.assertEqual(edges(result["connections"]), sorted(expected))

    text = json.dumps(result, ensure_ascii=False)
    test.assertNotIn("$env", text)
    test.assertNotIn('"id": "t2', json.dumps([n.get("credentials") for n in result["nodes"]]))
    test.assertEqual(scan_secrets(json.dumps(result, indent=2, ensure_ascii=False)), [])
    test.assertEqual(result["id"], eq.WORKFLOW_ID)
    test.assertFalse(result["active"])


class BaselineEquivalentTests(unittest.TestCase):
    def test_synthetic_template_swaps_only_documented_nodes(self):
        original = synthetic_template()
        frozen = copy.deepcopy(original)
        result = eq.build_equivalent(original)
        self.assertEqual(original, frozen, "input must not be mutated")
        assert_equivalent(self, original, result)

    def test_sink_columns_follow_sheet_schema_order(self):
        result = eq.build_equivalent(synthetic_template())
        header = next(n for n in result["nodes"] if n["name"] == eq.HEADER)
        names = [p["name"] for p in header["parameters"]["bodyParameters"]["parameters"]]
        self.assertEqual(names, ["H{}".format(i) for i in reversed(range(12))])

    def test_unexpected_upstream_shapes_fail_loudly(self):
        no_model = synthetic_template()
        next(n for n in no_model["nodes"] if n["name"] == eq.LLM)["parameters"]["jsonBody"] = "={}"
        other_recipient = synthetic_template()
        next(n for n in other_recipient["nodes"] if n["name"] == eq.GMAIL)["parameters"]["sendTo"] = "a@b.c"
        auto_map = synthetic_template()
        next(n for n in auto_map["nodes"] if n["name"] == eq.HEADER)["parameters"]["columns"]["mappingMode"] = "x"
        for workflow in (no_model, other_recipient, auto_map):
            with self.assertRaises(ValueError):
                eq.build_equivalent(workflow)

    def test_bind_credentials_and_substitute_return_copies(self):
        built = eq.build_equivalent(synthetic_template())
        ids = {"t2-openai": "a1", "t2-webhook-auth": "b2", "t2-sink-auth": "c3"}
        bound = eq.bind_credentials(built, ids)
        self.assertEqual(next(n for n in bound["nodes"] if n["name"] == eq.LLM)["credentials"],
                         {"openAiApi": {"name": "t2-openai", "id": "a1"}})
        with self.assertRaises(KeyError):
            eq.bind_credentials(built, {"t2-openai": "a1"})
        live = eq.substitute(bound, "http://127.0.0.1:8787", "abc123")
        text = json.dumps(live, ensure_ascii=False)
        self.assertNotIn(eq.SINK_PLACEHOLDER, text)
        self.assertNotIn(eq.WEBHOOK_PLACEHOLDER, text)
        self.assertIn(eq.SINK_PLACEHOLDER, json.dumps(built, ensure_ascii=False))
        with self.assertRaises(ValueError):
            eq.substitute(built, 'http://x"', "p")

    def test_fetch_extracts_inner_workflow_and_checks_identity(self):
        inner = {"nodes": [], "connections": {}}
        payload = {"workflow": {"id": TEMPLATE_ID, "name": TEMPLATE_NAME, "workflow": inner}}
        self.assertIs(extract_workflow(payload), inner)
        for bad in ({"workflow": {"id": 1, "name": TEMPLATE_NAME, "workflow": inner}}, {"workflow": {}}):
            with self.assertRaises(ValueError):
                extract_workflow(bad)

    @unittest.skipUnless(os.path.exists(ORIGINAL_PATH), "upstream template not fetched (python3 -m src.baseline.fetch)")
    def test_real_upstream_template(self):
        with open(ORIGINAL_PATH, encoding="utf-8") as f:
            original = json.load(f)
        result = eq.build_equivalent(original)
        assert_equivalent(self, original, result)
        self.assertEqual(len(original["nodes"]), 15)
        self.assertEqual(len(result["nodes"]), 17)


if __name__ == "__main__":
    unittest.main()
