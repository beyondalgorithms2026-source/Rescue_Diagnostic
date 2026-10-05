"""Fetch n8n community template 16643 into the gitignored upstream folder.

The upstream JSON is not vendored (QUESTIONS Q-3). Each operator fetches it from api.n8n.io.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


TEMPLATE_ID = 16643
TEMPLATE_URL = "https://n8n.io/workflows/16643-extract-and-validate-invoice-pdfs-with-openai-google-sheets-and-gmail/"
API_URL = "https://api.n8n.io/api/templates/workflows/{}".format(TEMPLATE_ID)
TEMPLATE_NAME = "Extract and validate invoice PDFs with OpenAI, Google Sheets, and Gmail"
UPSTREAM_DIR = Path("workflows/baseline/upstream")
ORIGINAL_PATH = UPSTREAM_DIR / "16643-original.json"


def canonical_sha256(workflow):
    text = json.dumps(workflow, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_workflow(payload):
    """Return the importable workflow object from an api.n8n.io template response."""
    outer = payload.get("workflow") if isinstance(payload, dict) else None
    inner = outer.get("workflow") if isinstance(outer, dict) else None
    if not isinstance(inner, dict) or not isinstance(inner.get("nodes"), list):
        raise ValueError("template response has no workflow.workflow.nodes")
    if outer.get("id") != TEMPLATE_ID or outer.get("name") != TEMPLATE_NAME:
        raise ValueError("template id or name changed upstream; stop and ask (Q-3)")
    return inner


def fetch(url=API_URL, timeout=30):
    # api.n8n.io answers 403 to the default Python-urllib user agent.
    request = urllib.request.Request(url, headers={"Accept": "application/json",
                                                   "User-Agent": "rescue-diagnostic-t2/fetch"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ORIGINAL_PATH))
    args = parser.parse_args(argv)
    try:
        workflow = extract_workflow(fetch())
    except urllib.error.HTTPError as error:
        print("fetch failed: HTTP {} — if 404, stop and ask; do not swap templates".format(error.code),
              file=sys.stderr)
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("wrote {} nodes={} canonical_sha256={}".format(out, len(workflow["nodes"]), canonical_sha256(workflow)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
