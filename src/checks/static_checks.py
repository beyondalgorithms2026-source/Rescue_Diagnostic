"""Secret scan and configuration audit for exported n8n workflow JSON."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys


SECRET_PATTERNS = (
    r"sk-[A-Za-z0-9_-]{20,}",
    r"sk-proj-",
    r"ya29\.",
    r"AIza[0-9A-Za-z_-]{35}",
    r"Bearer [A-Za-z0-9._-]{20,}",
    r'"(access|refresh)_token"\s*:\s*"[^"]+"',
    r'"apiKey"\s*:\s*"[^"={]+"',
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
)
_COMPILED_PATTERNS = tuple((pattern, re.compile(pattern)) for pattern in SECRET_PATTERNS)
EXTERNAL_TYPES = {"httpRequest", "googleSheets", "gmail", "openAi"}


def scan_secrets(text):
    """Return one location record per matching pattern occurrence, without values."""
    findings = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for pattern, compiled in _COMPILED_PATTERNS:
            if compiled.search(line):
                findings.append({"pattern": pattern, "line": line_number})
    return findings


def _positive_timeout(value):
    if isinstance(value, bool):
        return False
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def audit_workflow(workflow):
    """Describe relevant nodes and return policy violations for a workflow object."""
    node_reports = []
    violations = []
    nodes = workflow.get("nodes", [])
    if not isinstance(nodes, list):
        return [], ["workflow.nodes must be a list"]
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            violations.append("nodes[{}] must be an object".format(index))
            continue
        node_type = node.get("type", "")
        short_type = node_type.rsplit(".", 1)[-1]
        if short_type not in EXTERNAL_TYPES:
            continue
        parameters = node.get("parameters") or {}
        options = parameters.get("options") or {}
        retry = bool(node.get("retryOnFail", False))
        max_tries = node.get("maxTries")
        timeout = options.get("timeout") if isinstance(options, dict) else None
        name = node.get("name", "")
        report = {
            "name": name,
            "type": node_type,
            "onError": node.get("onError"),
            "retry": retry,
            "maxTries": max_tries,
            "timeout": timeout,
        }
        node_reports.append(report)
        label = name or "nodes[{}]".format(index)
        if not node.get("onError"):
            violations.append("{}: external node has no onError".format(label))
        if retry:
            if isinstance(max_tries, bool) or not isinstance(max_tries, int) or max_tries > 3 or max_tries < 1:
                violations.append("{}: retryOnFail requires maxTries from 1 through 3".format(label))
        if short_type == "httpRequest" and not _positive_timeout(timeout):
            violations.append("{}: httpRequest has no positive options.timeout".format(label))
    return node_reports, violations


def check_file(path):
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8")
    secrets = scan_secrets(text)
    workflow = json.loads(text)
    nodes, violations = audit_workflow(workflow)
    return {
        "file": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "secrets": secrets,
        "nodes": nodes,
        "violations": violations,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="exported n8n workflow JSON to inspect")
    parser.add_argument("--out", default="static_checks.json", help="JSON report path")
    parser.add_argument("--strict", action="store_true", help="exit non-zero when secrets or violations exist")
    args = parser.parse_args(argv)
    result = check_file(args.file)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return int(args.strict and bool(result["secrets"] or result["violations"]))


if __name__ == "__main__":
    sys.exit(main())
