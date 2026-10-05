"""Build the baseline-equivalent workflow from the fetched template 16643 (ARCHITECTURE §2.3).

Only the swaps listed in workflows/baseline/DIFF.md are applied. Every other node is copied unchanged.
The output stays in the gitignored upstream folder because it is derived from upstream JSON (Q-3).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import uuid
from pathlib import Path

from src.baseline.fetch import ORIGINAL_PATH, UPSTREAM_DIR


EQUIVALENT_PATH = UPSTREAM_DIR / "16643-equivalent.json"
WORKFLOW_ID = "t2BaselineEquiv1"
WORKFLOW_NAME = "T2 baseline — template 16643 equivalent"
SINK_PLACEHOLDER = "__SINK_BASE_URL__"
WEBHOOK_PLACEHOLDER = "__WEBHOOK_PATH__"
UPSTREAM_MODEL = '"model": "gpt-4o-mini",'
PINNED_MODEL = '"model": "gpt-4o-mini-2024-07-18",'  # QUESTIONS Q-1

FORM = "1. Form — Upload Invoice PDF"
LLM = "3. HTTP — AI Extract Invoice Fields"
HEADER = "5a. Sheets — Log Invoice Header"
LINES = "7. Sheets — Log Each Line Item"
VERIFY = "9. Code — Verify Totals and Build Report"
GMAIL = "10. Gmail — Send Extraction Report"
WEBHOOK = "0. Webhook — Replay Intake"
RECIPIENT_CHECK = "10a. Gmail — Recipient Check (equivalence shim)"
FILE_FIELD = "Invoice PDF"
FILE_BINARY_KEY = "Invoice_PDF"  # Form Trigger: fieldLabel.replace(/\W/g, '_')

CREDENTIALS = {
    "openai": ("openAiApi", "t2-openai"),
    "webhook": ("httpHeaderAuth", "t2-webhook-auth"),
    "sink": ("httpHeaderAuth", "t2-sink-auth"),
}
SWAPPED = (FORM, HEADER, LINES, GMAIL)
CHANGED = (LLM,)
ADDED = (WEBHOOK, RECIPIENT_CHECK)

FORM_SHIM_CODE = """// Equivalence shim (T6): reproduces the Form Trigger v2.2 output item from a Webhook request.
// Downstream nodes read $('1. Form — Upload Invoice PDF').first().json[...] unchanged.
const item = $input.first();
const body = item.json.body || {};
const file = (item.binary || {})['__BINARY_KEY__'];
if (!file) {
  throw new Error("equivalence shim: multipart file field '__BINARY_KEY__' is missing");
}
const json = {};
for (const label of __TEXT_LABELS__) {
  json[label] = body[label] === undefined ? '' : body[label];
}
json['__FILE_FIELD__'] = { filename: file.fileName, mimetype: file.mimeType, size: file.fileSize };
json.submittedAt = new Date().toISOString();
json.formMode = 'production';
return [{ json, binary: { '__BINARY_KEY__': file } }];
"""

RECIPIENT_CHECK_CODE = """// Equivalence shim (T6): reproduces the recipient check that the Gmail v2 node runs before
// any network call (n8n-nodes-base Gmail GenericFunctions prepareEmailsInput, n8n 2.22.5).
// Upstream sendTo is __SEND_TO__ ; this shim reads the same field.
return $input.all().map((item, itemIndex) => {
  const sendTo = item.json.__SEND_TO_FIELD__ === undefined || item.json.__SEND_TO_FIELD__ === null
    ? '' : String(item.json.__SEND_TO_FIELD__);
  for (const entry of sendTo.split(',')) {
    const email = entry.trim();
    if (email.indexOf('@') === -1) {
      const error = new Error('Invalid email address');
      error.description = "The email address '" + email + "' in the 'To' field isn't valid";
      throw error;
    }
  }
  return item;
});
"""


def _nodes_by_name(workflow):
    nodes = {}
    for node in workflow["nodes"]:
        if node["name"] in nodes:
            raise ValueError("duplicate node name: " + node["name"])
        nodes[node["name"]] = node
    return nodes


def _require(nodes, name, type_suffix):
    node = nodes.get(name)
    if node is None or not node.get("type", "").endswith("." + type_suffix):
        raise ValueError("expected node {!r} of type {}".format(name, type_suffix))
    return node


def _credential(kind):
    credential_type, name = CREDENTIALS[kind]
    return {credential_type: {"name": name}}


def _offset(position, dx, dy=0):
    return [position[0] + dx, position[1] + dy]


def _node_id(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "t2-rescue/baseline/" + name))


def _sink_node(original, table, pairs):
    return {
        "id": original.get("id") or _node_id(original["name"]),
        "name": original["name"],
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": original["position"],
        "credentials": _credential("sink"),
        "parameters": {
            "method": "POST",
            "url": SINK_PLACEHOLDER + "/append/" + table,
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "keypair",
            "bodyParameters": {"parameters": [{"name": key, "value": value} for key, value in pairs]},
            "options": {},
        },
    }


def _sheet_pairs(node):
    columns = node["parameters"]["columns"]
    if columns.get("mappingMode") != "defineBelow":
        raise ValueError(node["name"] + ": expected columns.mappingMode defineBelow")
    values = columns["value"]
    order = [entry["id"] for entry in columns.get("schema", []) if entry["id"] in values]
    order += [key for key in values if key not in order]
    if len(order) != 12:
        raise ValueError(node["name"] + ": expected twelve mapped columns")
    return [(key, values[key]) for key in order]


def _form_text_labels(form):
    labels = []
    for field in form["parameters"]["formFields"]["values"]:
        if field.get("fieldType") != "file":
            labels.append(field["fieldLabel"])
    return labels


def build_equivalent(original):
    """Return a new workflow dict with only the documented swaps applied."""
    workflow = copy.deepcopy(original)
    nodes = _nodes_by_name(workflow)
    form = _require(nodes, FORM, "formTrigger")
    llm = _require(nodes, LLM, "httpRequest")
    header = _require(nodes, HEADER, "googleSheets")
    lines = _require(nodes, LINES, "googleSheets")
    gmail = _require(nodes, GMAIL, "gmail")
    file_fields = [f for f in form["parameters"]["formFields"]["values"] if f.get("fieldType") == "file"]
    if [f["fieldLabel"] for f in file_fields] != [FILE_FIELD]:
        raise ValueError("expected exactly one form file field named " + FILE_FIELD)

    webhook = {
        "id": _node_id(WEBHOOK),
        "name": WEBHOOK,
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": _offset(form["position"], -240),
        "webhookId": _node_id(WEBHOOK + "/webhookId"),
        "credentials": _credential("webhook"),
        "parameters": {
            "httpMethod": "POST",
            "path": WEBHOOK_PLACEHOLDER,
            "authentication": "headerAuth",
            "responseMode": "lastNode",
            "options": {},
        },
    }
    form_code = (FORM_SHIM_CODE.replace("__BINARY_KEY__", FILE_BINARY_KEY)
                 .replace("__FILE_FIELD__", FILE_FIELD)
                 .replace("__TEXT_LABELS__", json.dumps(_form_text_labels(form), ensure_ascii=False)))
    form_shim = {
        "id": form.get("id") or _node_id(FORM),
        "name": FORM,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": form["position"],
        "parameters": {"jsCode": form_code},
    }

    body = llm["parameters"]["jsonBody"]
    if body.count(UPSTREAM_MODEL) != 1:
        raise ValueError("expected exactly one upstream model string in " + LLM)
    llm["parameters"]["jsonBody"] = body.replace(UPSTREAM_MODEL, PINNED_MODEL)
    llm["credentials"] = _credential("openai")

    send_to = gmail["parameters"]["sendTo"]
    if send_to != "={{ $json.email }}":
        raise ValueError("unexpected Gmail sendTo expression")
    recipient_check = {
        "id": _node_id(RECIPIENT_CHECK),
        "name": RECIPIENT_CHECK,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": _offset(gmail["position"], -120, 160),
        "parameters": {"jsCode": RECIPIENT_CHECK_CODE.replace("__SEND_TO__", send_to)
                       .replace("__SEND_TO_FIELD__", "email")},
    }
    outbox = _sink_node(gmail, "outbox", [("to", send_to), ("subject", gmail["parameters"]["subject"]),
                                          ("html", gmail["parameters"]["message"])])

    replacements = {
        FORM: form_shim,
        HEADER: _sink_node(header, "invoices", _sheet_pairs(header)),
        LINES: _sink_node(lines, "line_items", _sheet_pairs(lines)),
        GMAIL: outbox,
    }
    workflow["nodes"] = [replacements.get(node["name"], node) for node in workflow["nodes"]]
    workflow["nodes"][0:0] = [webhook]
    workflow["nodes"].append(recipient_check)

    connections = workflow["connections"]
    connections[WEBHOOK] = {"main": [[{"node": FORM, "type": "main", "index": 0}]]}
    for output in connections.get(VERIFY, {}).get("main", []):
        for edge in output:
            if edge["node"] == GMAIL:
                edge["node"] = RECIPIENT_CHECK
    connections[RECIPIENT_CHECK] = {"main": [[{"node": GMAIL, "type": "main", "index": 0}]]}

    workflow["id"] = WORKFLOW_ID
    workflow["name"] = WORKFLOW_NAME
    workflow["active"] = False
    workflow.pop("versionId", None)
    return workflow


def bind_credentials(workflow, ids_by_name):
    """Return a copy with credential ids filled in from a {credential name: id} map (§3.6)."""
    bound = copy.deepcopy(workflow)
    for node in bound["nodes"]:
        for reference in (node.get("credentials") or {}).values():
            if reference["name"] not in ids_by_name:
                raise KeyError("no credential id for " + reference["name"])
            reference["id"] = ids_by_name[reference["name"]]
    return bound


def substitute(workflow, sink_base_url, webhook_path):
    """Return a copy with §1.1 placeholders replaced. Never write the result to the repo."""
    text = json.dumps(workflow, ensure_ascii=False)
    for placeholder, value in ((SINK_PLACEHOLDER, sink_base_url), (WEBHOOK_PLACEHOLDER, webhook_path)):
        if not value or '"' in value or "\\" in value:
            raise ValueError("invalid substitution value for " + placeholder)
        text = text.replace(placeholder, value)
    return json.loads(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="source", default=str(ORIGINAL_PATH))
    parser.add_argument("--out", default=str(EQUIVALENT_PATH))
    args = parser.parse_args(argv)
    with open(args.source, encoding="utf-8") as f:
        original = json.load(f)
    equivalent = build_equivalent(original)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(equivalent, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("wrote {} nodes={}".format(out, len(equivalent["nodes"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
