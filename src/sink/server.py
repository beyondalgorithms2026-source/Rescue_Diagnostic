"""Local append-only CSV sink for sequential n8n replay."""
from __future__ import annotations

import argparse
import csv
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


STAMPS = ("sink_seq", "sink_ts", "replay_input_id", "replay_pass")
COLUMNS = {
    "invoices": ("run_id", "dedupe_key", "content_sha256", "invoice_no", "vendor", "vendor_norm",
                 "invoice_date", "currency", "subtotal", "tax", "total", "line_count", "submitter_email"),
    "line_items": ("run_id", "dedupe_key", "line_key", "line_no", "description", "quantity",
                   "unit_price", "line_total"),
    "review_queue": ("run_id", "dedupe_key", "reason", "extracted_json"),
    "outbox": ("run_id", "to", "subject", "html"),
    "errors": ("run_id", "input_ref", "stage", "node", "code", "message"),
    "ledger": ("run_id", "input_ref", "model", "tokens_in", "tokens_out", "usd"),
    "audit": ("run_id", "input_ref", "execution_id", "stage", "node", "ok", "status",
              "content_sha256", "dedupe_key", "tokens_in", "tokens_out", "usd", "duration_ms"),
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _csv_value(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    return str(value)


class SinkState:
    def __init__(self, directory, token):
        if not token:
            raise ValueError("SINK_TOKEN is required")
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.token = token
        self.active_input = ""
        self.active_pass = ""
        self.fault = None
        self.seq = 0
        for table in COLUMNS:
            for row in self.rows(table):
                self.seq = max(self.seq, int(row.get("sink_seq") or 0))

    def rows(self, table):
        path = self.directory / (table + ".csv")
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def append(self, table, payload):
        if not isinstance(payload, dict) or not payload or any(key in STAMPS for key in payload):
            raise ValueError("append body must be a nonempty object without sink stamps")
        canonical = COLUMNS[table]
        keys = tuple(payload)
        path = self.directory / (table + ".csv")
        if path.exists():
            with path.open(newline="", encoding="utf-8") as f:
                header = tuple(next(csv.reader(f)))
            if set(keys) - set(header):
                raise ValueError("row columns differ from table header")
        elif table in ("invoices", "line_items") and set(keys) != set(canonical):
            # The baseline mapping has twelve columns, whose names come from its first append.
            if len(keys) != 12:
                raise ValueError("baseline row must have twelve columns")
            header = STAMPS + keys
        else:
            if set(keys) - set(canonical):
                raise ValueError("unknown table column")
            header = STAMPS + canonical
        self.seq += 1
        row = {key: "" for key in header}
        row.update({key: _csv_value(value) for key, value in payload.items()})
        row.update({"sink_seq": str(self.seq), "sink_ts": _now(),
                    "replay_input_id": self.active_input, "replay_pass": self.active_pass})
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow(row)
        return row

    def log(self, method, path, status):
        event = {"ts": _now(), "method": method, "path": path, "status": status,
                 "active_input": self.active_input, "pass": self.active_pass}
        with (self.directory / "requests.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")


def make_server(state_dir, token, host="127.0.0.1", port=0):
    """Return a single-threaded server. Port zero selects an ephemeral test port."""
    state = SinkState(state_dir, token)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format_string, *args):
            pass

        def _reply(self, status, body):
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 2_000_000:
                raise ValueError("invalid body size")
            value = json.loads(self.rfile.read(size))
            if not isinstance(value, dict):
                raise ValueError("body must be a JSON object")
            return value

        def _handle(self):
            url = urlsplit(self.path)
            path = url.path
            method = self.command
            supplied = self.headers.get("X-Sink-Token", "").encode("utf-8")
            if not hmac.compare_digest(supplied, state.token.encode("utf-8")):
                return 401, {"error": "unauthorized"}
            if method == "GET" and path == "/_health":
                return 200, {"ok": True}
            if method == "POST" and path == "/_replay/active":
                body = self._body()
                if not isinstance(body.get("input_id"), str) or body.get("pass") not in ("A", "B"):
                    raise ValueError("active requires input_id and pass A or B")
                state.active_input, state.active_pass = body["input_id"], body["pass"]
                state.fault = None
                return 200, {"ok": True}
            if method == "POST" and path == "/_replay/fault":
                body = self._body()
                if not body or body.get("times") == 0:
                    state.fault = None
                elif (body.get("target") not in ("invoices", "line_items", "outbox") or
                      body.get("status") not in (500, 503) or body.get("pass") not in ("A", "B") or
                      type(body.get("times")) is not int or body["times"] < 1):
                    raise ValueError("invalid fault")
                else:
                    state.fault = dict(body)
                return 200, {"ok": True}
            if path.startswith("/append/") and method == "POST":
                table = path.removeprefix("/append/")
                if table not in COLUMNS:
                    return 400, {"error": "unknown table"}
                body = self._body()
                fault = state.fault
                if fault and fault["target"] == table and fault["pass"] == state.active_pass:
                    fault["times"] -= 1
                    if fault["times"] == 0:
                        state.fault = None
                    return fault["status"], {"error": "injected fault"}
                return 200, {"row": state.append(table, body)}
            if path.startswith("/lookup/") and method == "GET":
                table = path.removeprefix("/lookup/")
                if table not in COLUMNS:
                    return 400, {"error": "unknown table"}
                query = parse_qs(url.query, keep_blank_values=True)
                if not query or any(len(values) != 1 for values in query.values()):
                    raise ValueError("lookup requires single-valued filters")
                rows = [row for row in state.rows(table) if all(row.get(key) == values[0]
                                                                 for key, values in query.items())]
                return 200, {"count": len(rows), "rows": rows}
            if method == "GET" and path in ("/ledger/sum", "/ledger/count"):
                query = parse_qs(url.query, keep_blank_values=True)
                run_ids = query.get("run_id", [])
                if len(run_ids) != 1 or not run_ids[0]:
                    raise ValueError("run_id is required")
                rows = [row for row in state.rows("ledger") if row.get("run_id") == run_ids[0]]
                if path == "/ledger/sum":
                    try:
                        amount = sum((Decimal(row.get("usd") or "0") for row in rows), Decimal("0"))
                    except InvalidOperation as error:
                        raise ValueError("invalid ledger usd") from error
                    return 200, {"usd": float(amount)}
                try:
                    since = float(query.get("since_s", [""])[0])
                except ValueError as error:
                    raise ValueError("since_s is required") from error
                if since < 0:
                    raise ValueError("since_s must be nonnegative")
                threshold = datetime.now(timezone.utc) - timedelta(seconds=since)
                count = sum(datetime.fromisoformat(row["sink_ts"]) >= threshold for row in rows)
                return 200, {"count": count}
            return 404, {"error": "not found"}

        def _dispatch(self):
            path = urlsplit(self.path).path
            try:
                status, body = self._handle()
            except (ValueError, json.JSONDecodeError) as error:
                status, body = 400, {"error": str(error)}
            state.log(self.command, path, status)
            self._reply(status, body)

        def do_GET(self):
            self._dispatch()

        def do_POST(self):
            self._dispatch()

    server = HTTPServer((host, port), Handler)
    server.state = state
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("SINK_PORT", "8787")))
    args = parser.parse_args(argv)
    with make_server(args.state_dir, os.environ.get("SINK_TOKEN", ""), args.host, args.port) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
