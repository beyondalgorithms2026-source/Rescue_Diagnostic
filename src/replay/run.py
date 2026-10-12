"""Run the template 16643 replay against local n8n without its public API.

The runner talks to the local sink and webhook, but imports, publishes, and
unpublishes workflows through the n8n CLI.  Execution evidence is read from
SQLite in read-only mode.  Nothing in this module prints credentials, webhook
paths, or token counts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.baseline import equivalent


RUN_CAP = 0.25
TIMEOUT_SECONDS = 180
STAGES = {
    "0. Webhook — Replay Intake": "intake",
    "1. Form — Upload Invoice PDF": "intake",
    "2. Extract From File — PDF to Text": "extract",
    "3. HTTP — AI Extract Invoice Fields": "extract",
    "4. Code — Parse Invoice JSON Safely": "validate",
    "5a. Sheets — Log Invoice Header": "act",
    "5b. Split Out — Line Items": "act",
    "6. Code — Add Unique Key and Line Metadata": "act",
    "7. Sheets — Log Each Line Item": "act",
    "8. Aggregate — Collect All Line Items": "validate",
    "9. Code — Verify Totals and Build Report": "validate",
    "10. Gmail — Send Extraction Report": "approve",
}
LEDGER_HEADER = ("run_id,run_phase,target,started_utc,ended_utc,model,llm_calls,"
                 "tokens_in,tokens_out,usd,run_usd_cap,capped_inputs".split(","))
REPAIRED_BASELINE = Path("workflows/baseline/upstream/16643-repaired-to-run.json")
EQUIVALENT_BASELINE = "workflows/baseline/upstream/16643-equivalent.json"
HARDENED = Path("workflows/hardened/t2-hardened.json")
HANDLER = Path("workflows/hardened/t2-error-handler.json")
HARDENED_LLM = "H6 LLM Extract — DeepSeek"
BASELINE_MODEL = "gpt-4o-mini-2024-07-18"
CREDENTIAL_IDS = {"t2-openai": "t2OpenAiSmoke001", "t2-webhook-auth": "t2WebhookAuth001",
                  "t2-sink-auth": "t2SinkAuth000001", "t2-deepseek": "t2DeepSeekKey001"}
HARDENED_STAGES = (("H1 ", "intake"), ("H2 ", "intake"), ("H3 ", "extract"), ("H4 ", "extract"), ("H5 ", "extract"),
                   ("H6 ", "extract"), ("H7 ", "extract"), ("H8 ", "validate"), ("H10 ", "decide"),
                   ("H11 ", "act"), ("H12 ", "act"), ("H13 ", "act"), ("H14 ", "act"), ("H15 ", "approve"),
                   ("H16 ", "record"), ("E ", "record"), ("0. ", "intake"))


def stage_for(node):
    if node in STAGES:
        return STAGES[node]
    for prefix, stage in HARDENED_STAGES:
        if node.startswith(prefix):
            return stage
    return "record"


def config_values(workflow):
    """Return the hardened `0. Config` assignments (§3.2) as a dict."""
    for node in workflow.get("nodes", []):
        if node.get("name") == "0. Config":
            return {a["name"]: a["value"] for a in node["parameters"]["assignments"]["assignments"]}
    raise ValueError("hardened workflow has no 0. Config node")


def load_env_file(path):
    """Copy KEY=value lines into os.environ without overriding values already set. Values stay in memory."""
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def phase_settings(phase, workflow):
    """Webhook path variable, credential names, model, prices, and LLM node name for one phase."""
    if phase == "hardened":
        cfg = config_values(workflow)
        if float(cfg["run_usd_cap"]) != RUN_CAP:
            raise ValueError("0. Config run_usd_cap must be 0.25")
        return {"path_var": "T2_WEBHOOK_PATH_HARDENED", "model": cfg["llm_model"], "llm_node": HARDENED_LLM,
                "credentials": ("t2-webhook-auth", "t2-sink-auth", "t2-deepseek"),
                "price_in": float(cfg["llm_price_in_per_mtok"]), "price_out": float(cfg["llm_price_out_per_mtok"])}
    return {"path_var": "T2_WEBHOOK_PATH_BASELINE", "model": BASELINE_MODEL, "llm_node": equivalent.LLM,
            "credentials": tuple(name for _, name in equivalent.CREDENTIALS.values()),
            "price_in": float(os.environ["LLM_PRICE_IN_PER_MTOK"]),
            "price_out": float(os.environ["LLM_PRICE_OUT_PER_MTOK"])}


def credential_payload(env):
    """Local-target credentials (§3.6), built in memory from the environment."""
    def header(cid, name, header_name, value):
        return {"id": cid, "name": name, "type": "httpHeaderAuth", "data": {"name": header_name, "value": value}}
    return [header(CREDENTIAL_IDS["t2-webhook-auth"], "t2-webhook-auth", "X-T2-Token", env["T2_WEBHOOK_TOKEN"]),
            header(CREDENTIAL_IDS["t2-sink-auth"], "t2-sink-auth", "X-Sink-Token", env["SINK_TOKEN"]),
            header(CREDENTIAL_IDS["t2-deepseek"], "t2-deepseek", "Authorization",
                   "Bearer " + env.get("DEEPSEEK_API_KEY", "")),
            {"id": CREDENTIAL_IDS["t2-openai"], "name": "t2-openai", "type": "openAiApi",
             "data": {"apiKey": env.get("OPENAI_API_KEY", "")}}]


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def request_json(method, url, token, body=None, timeout=10):
    """Make a sink request.  Errors are explicit; requests are never retried."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"X-Sink-Token": token}
    if data is not None:
        headers["Content-Type"] = "application/json"
    try:
        with urlopen(Request(url, data=data, headers=headers, method=method), timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))
    except URLError as error:
        raise RuntimeError("sink request failed") from error


def multipart(fields, field_name, filename, content, headers):
    boundary = "----t2replay" + uuid.uuid4().hex
    parts = []
    for key, value in fields.items():
        parts.extend(("--" + boundary, 'Content-Disposition: form-data; name="{}"'.format(key), "", str(value)))
    parts.extend(("--" + boundary,
                  'Content-Disposition: form-data; name="{}"; filename="{}"'.format(field_name, filename),
                  "Content-Type: application/pdf", ""))
    prefix = "\r\n".join(parts).encode("utf-8") + b"\r\n"
    data = prefix + content + b"\r\n--" + boundary.encode("ascii") + b"--\r\n"
    outgoing = dict(headers)
    outgoing["Content-Type"] = "multipart/form-data; boundary=" + boundary
    return data, outgoing


def submit(webhook_url, token, run_id, item, pdf_path, timeout=TIMEOUT_SECONDS):
    form = item["form"]
    fields = {"Your Name": form.get("name", ""), "Your Email": form.get("email", ""),
              "Currency": form.get("currency", ""), "Notes": form.get("notes", "")}
    headers = {"X-T2-Token": token, "X-Replay-Run-Id": run_id, "X-Replay-Input-Id": item["input_id"]}
    data, headers = multipart(fields, equivalent.FILE_BINARY_KEY, pdf_path.name, pdf_path.read_bytes(), headers)
    try:
        with urlopen(Request(webhook_url, data=data, headers=headers, method="POST"), timeout=timeout) as response:
            return response.status
    except HTTPError as error:
        return error.code
    except URLError as error:
        raise RuntimeError("webhook submission failed") from error


def repaired_to_run(workflow):
    """Apply only Q-7 repairs R-1 and R-2 to an equivalent workflow copy."""
    repaired = json.loads(json.dumps(workflow))
    nodes = {node["name"]: node for node in repaired["nodes"]}
    extract = nodes["2. Extract From File — PDF to Text"]
    extract["parameters"]["binaryPropertyName"] = equivalent.FILE_BINARY_KEY  # R-1
    llm = nodes[equivalent.LLM]
    body = llm["parameters"]["jsonBody"]
    prefix = '"content": {{ JSON.stringify('
    suffix = ") + $('2. Extract From File — PDF to Text').first().json.text }}\""
    if not body.startswith("={") or prefix not in body or suffix not in body:
        raise ValueError("baseline JSON body no longer has the documented R-2 defect")
    raw_body = body[1:]
    start = raw_body.index(prefix) + len(prefix)
    end = raw_body.index(suffix, start)
    prompt = json.loads(raw_body[start:end])
    marker = "__T2_R2_PDF_TEXT__"
    payload = json.loads(raw_body.replace(raw_body[start - len(prefix):end + len(suffix)],
                                          '"content": "{}"'.format(marker), 1))
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    text = "({} + $('2. Extract From File — PDF to Text').first().json.text)".format(
        json.dumps(prompt, ensure_ascii=False))
    # R-2: JSON.stringify serializes the complete request object after text joins
    # its user-content string, so text cannot escape the HTTP JSON body.
    llm["parameters"]["jsonBody"] = "={{{{ JSON.stringify({}) }}}}".format(
        encoded.replace(json.dumps(marker), text, 1))
    return repaired


def materialize_repaired_baseline(source, output=REPAIRED_BASELINE):
    """Write the disclosed, pre-substitution R-1/R-2 baseline beside the fetched JSON."""
    workflow = json.loads(Path(source).read_text(encoding="utf-8"))
    repaired = repaired_to_run(workflow)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(repaired, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


class LocalN8n:
    """CLI lifecycle and read-only SQLite execution reader for the local container."""

    def __init__(self, db_path, command=subprocess.run, sleeper=time.sleep):
        self.db_path = Path(db_path)
        self.command, self.sleeper = command, sleeper

    def _run(self, args, input_text=None):
        result = self.command(args, input=input_text, text=True, capture_output=True, check=False)
        if result.returncode:
            raise RuntimeError("n8n CLI command failed")

    def import_workflow(self, workflow):
        # /dev/stdin keeps target-specific substitutions out of the working tree.
        self._run(["docker", "exec", "-i", "n8n", "n8n", "import:workflow", "--input=/dev/stdin"],
                  json.dumps(workflow, ensure_ascii=False))

    def import_credentials(self, credentials):
        self._run(["docker", "exec", "-i", "n8n", "n8n", "import:credentials", "--input=/dev/stdin"],
                  json.dumps(credentials))

    def publish(self, workflow_id):
        self._run(["docker", "exec", "-e", "N8N_SECURE_COOKIE=false", "n8n", "n8n",
                   "publish:workflow", "--id=" + workflow_id])
        self._run(["docker", "restart", "n8n"])

    def unpublish(self, workflow_id):
        self._run(["docker", "exec", "-e", "N8N_SECURE_COOKIE=false", "n8n", "n8n",
                   "unpublish:workflow", "--id=" + workflow_id])
        self._run(["docker", "restart", "n8n"])

    def wait_ready(self, base_url, timeout=30):
        """Wait for the restarted local n8n HTTP service before one submission."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urlopen(base_url.rstrip("/") + "/healthz", timeout=2) as response:
                    if response.status == 200:
                        # The health endpoint can respond before active webhooks register.
                        self.sleeper(5)
                        return
            except (OSError, URLError):
                pass
            self.sleeper(0.25)
        raise RuntimeError("n8n did not become ready after restart")

    def _container_query(self, sql, parameters):
        """Run a read-only SQLite query inside the local n8n container."""
        script = """const sqlite3=require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3');
const input=JSON.parse(process.argv[1]);
const db=new sqlite3.Database('/home/node/.n8n/database.sqlite', sqlite3.OPEN_READONLY, error => {
  if (error) throw error;
  db.all(input.sql, input.parameters, (queryError, rows) => {
    if (queryError) throw queryError;
    process.stdout.write(JSON.stringify(rows));
    db.close();
  });
});"""
        result = self.command(["docker", "exec", "n8n", "node", "-e", script,
                               json.dumps({"sql": sql, "parameters": parameters})],
                              text=True, capture_output=True, check=False)
        if result.returncode:
            raise RuntimeError("n8n SQLite query failed")
        return json.loads(result.stdout or "[]")

    def _query(self, sql, parameters):
        try:
            with sqlite3.connect("file:{}?mode=ro".format(self.db_path), uri=True) as connection:
                return connection.execute(sql, parameters).fetchall()
        except sqlite3.OperationalError:
            return [tuple(row.values()) for row in self._container_query(sql, parameters)]

    def _decode_execution_data(self, value):
        """Decode n8n's bundled Flatted execution data without writing to SQLite."""
        script = """const flatted=require('/usr/local/lib/node_modules/n8n/node_modules/flatted');
const value=flatted.parse(process.argv[1]);
process.stdout.write(JSON.stringify(value));"""
        result = self.command(["docker", "exec", "n8n", "node", "-e", script, value],
                              text=True, capture_output=True, check=False)
        if result.returncode:
            raise RuntimeError("n8n execution-data decode failed")
        return json.loads(result.stdout)

    def latest_id(self, workflow_id):
        row = self._query("SELECT MAX(id) FROM execution_entity WHERE workflowId = ?", (workflow_id,))[0]
        return int(row[0] or 0)

    def credential_ids(self, names):
        placeholders = ",".join("?" for _ in names)
        rows = self._query("SELECT id, name FROM credentials_entity WHERE name IN ({})".format(placeholders),
                           tuple(names))
        ids = {row[1]: row[0] for row in rows}
        missing = set(names) - set(ids)
        if missing:
            raise RuntimeError("required local credentials are missing")
        return ids

    def wait_execution(self, workflow_id, after_id, timeout=TIMEOUT_SECONDS):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rows = self._query("SELECT id, status, startedAt, stoppedAt FROM execution_entity "
                               "WHERE workflowId = ? AND id > ? ORDER BY id DESC LIMIT 1",
                               (workflow_id, after_id))
            row = rows[0] if rows else None
            if row and row[1] not in ("new", "running", "waiting"):
                data_rows = self._query("SELECT data FROM execution_data WHERE executionId = ?", (row[0],))
                data = data_rows[0] if data_rows else None
                return {"id": int(row[0]), "status": row[1], "started": row[2], "stopped": row[3],
                        "data": (self._decode_execution_data(data[0])
                                 if data and data[0] and data[0].lstrip().startswith("[")
                                 else json.loads(data[0]) if data and data[0] else None)}
            self.sleeper(0.25)
        return None


class LocalSink:
    """A fresh local sink process for one replay run."""

    def __init__(self, state_dir, token, port):
        self.state_dir, self.token, self.port = state_dir, token, port
        self.process = None

    def start(self):
        child_env = dict(os.environ)
        child_env["SINK_TOKEN"] = self.token
        self.process = subprocess.Popen([sys.executable, "-m", "src.sink.server", "--state-dir", str(self.state_dir),
                                         "--host", "127.0.0.1", "--port", str(self.port)],
                                        env=child_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        health = "http://127.0.0.1:{}/_health".format(self.port)
        for _ in range(40):
            try:
                status, _ = request_json("GET", health, self.token)
                if status == 200:
                    return
            except RuntimeError:
                pass
            time.sleep(0.05)
        self.stop()
        raise RuntimeError("local sink did not become healthy")

    def stop(self):
        if self.process is not None:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None


def _usage(value):
    if not isinstance(value, dict):
        return 0, 0
    main = value.get("main")
    if isinstance(main, list) and main and isinstance(main[0], list) and main[0]:
        item = main[0][0]
        if isinstance(item, dict):
            value = item.get("json", value)
    usage = value.get("usage", value.get("tokenUsage", {}))
    if not isinstance(usage, dict):
        return 0, 0
    return int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0), int(
        usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)


def trace_events(execution, run_id, pass_name, input_id, price_in, price_out):
    if not execution or not execution.get("data"):
        return [{"ts": utc_now(), "node": "runner", "ok": False, "tokens": 0, "usd": 0.0,
                 "run_id": run_id, "pass": pass_name, "input_id": input_id,
                 "stage": "record", "error": "audit_gap"}]
    run_data = execution["data"].get("resultData", {}).get("runData", {})
    events = []
    for node, entries in run_data.items():
        for entry in entries or []:
            token_in, token_out = _usage(entry.get("data", {}))
            usd = token_in * price_in / 1000000 + token_out * price_out / 1000000
            error = entry.get("error")
            events.append({"ts": entry.get("startTime") or execution.get("started") or utc_now(), "node": node,
                           "ok": not bool(error), "tokens": token_in + token_out, "usd": usd,
                           "run_id": run_id, "pass": pass_name, "input_id": input_id,
                           "execution_id": execution["id"], "stage": stage_for(node),
                           "tokens_in": token_in, "tokens_out": token_out,
                           **({"error": str(error)} if error else {})})
    return events or [{"ts": execution.get("started") or utc_now(), "node": "runner", "ok": False,
                       "tokens": 0, "usd": 0.0, "run_id": run_id, "pass": pass_name,
                       "input_id": input_id, "execution_id": execution["id"], "stage": "record",
                       "error": "audit_gap"}]


def _count_rows(path):
    if not Path(path).exists():
        return 0
    with open(path, newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


def load_manifest(manifest):
    with open(manifest, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_replay(args, n8n=None):
    if args.target != "local":
        raise ValueError("T7 permits the local target only")
    env = os.environ
    hardened = args.phase == "hardened"
    path_var = "T2_WEBHOOK_PATH_HARDENED" if hardened else "T2_WEBHOOK_PATH_BASELINE"
    required = ("SINK_TOKEN", "T2_WEBHOOK_TOKEN", path_var, "SINK_BASE_URL") + (
        () if hardened else ("LLM_PRICE_IN_PER_MTOK", "LLM_PRICE_OUT_PER_MTOK"))
    missing = [name for name in required if not env.get(name)]
    if missing:
        raise ValueError("missing required runner configuration")
    if float(env.get("RUN_USD_CAP", RUN_CAP)) != RUN_CAP:
        raise ValueError("RUN_USD_CAP must be 0.25")
    source = Path(args.workflow or (HARDENED if hardened else EQUIVALENT_BASELINE))
    if args.phase == "baseline" and args.baseline_mode == "repaired":
        source = materialize_repaired_baseline(source, Path(args.repaired_workflow))
    workflow = json.loads(source.read_text(encoding="utf-8"))
    settings = phase_settings(args.phase, workflow)
    price_in, price_out = settings["price_in"], settings["price_out"]
    n8n = n8n or LocalN8n(args.sqlite)
    ids = n8n.credential_ids(settings["credentials"])
    workflow = equivalent.bind_credentials(workflow, ids)
    workflow = equivalent.substitute(workflow, env["SINK_BASE_URL"], env[path_var])
    handler = None
    if hardened:
        handler = json.loads(Path(getattr(args, "handler_workflow", None) or HANDLER).read_text(encoding="utf-8"))
        handler = equivalent.substitute(equivalent.bind_credentials(handler, ids), env["SINK_BASE_URL"], "unused")
    workflow_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    replay_of = getattr(args, "replay_of", None)
    if replay_of:
        # I-8: replay pass B into an existing run's sink; record new header rows in that run's summary.
        run_id = replay_of
        run_dir = Path(args.runs_dir) / run_id
        if not (run_dir / "sink").is_dir():
            raise ValueError("replay-of run has no sink")
        args.passes = "B"
        trace_path = run_dir / "replay_trace.jsonl"
    else:
        run_id = "{}-local-{}-{}".format(args.phase, datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), "nogit")
        run_dir = Path(args.runs_dir) / run_id
        run_dir.mkdir(parents=True)
        trace_path = run_dir / "trace.jsonl"
    headers_before = _count_rows(run_dir / "sink" / "invoices.csv")
    started = utc_now()
    sink_process = None
    if getattr(args, "start_sink", True):
        sink_process = LocalSink(run_dir / "sink", env["SINK_TOKEN"], int(env.get("SINK_PORT", "8787")))
        sink_process.start()
    webhook = env["N8N_BASE_URL"].rstrip("/") + "/webhook/" + env[path_var]
    # The workflow runs in Docker and uses SINK_BASE_URL.  The runner runs on
    # the host, where its freshly started sink is reachable on loopback.
    sink = "http://127.0.0.1:{}".format(env.get("SINK_PORT", "8787"))
    rows, total_usd, capped, published = load_manifest(args.manifest), 0.0, 0, False
    all_events = []
    handler_published = False
    try:
        if handler is not None:
            n8n.import_workflow(handler)
            handler_published = True
            n8n.publish(handler["id"])  # n8n runs an error workflow only when it is published.
        n8n.import_workflow(workflow)
        published = True
        n8n.publish(workflow["id"])
        if isinstance(n8n, LocalN8n):
            n8n.wait_ready(env["N8N_BASE_URL"])
        for pass_name in args.passes:
            for row in rows:
                if total_usd >= RUN_CAP:
                    capped += 1
                    all_events.append({"ts": utc_now(), "node": "runner", "ok": False, "tokens": 0, "usd": 0.0,
                                       "run_id": run_id, "pass": pass_name, "input_id": row["input_id"],
                                       "stage": "record", "capped": True, "error": "runner_cap"})
                    continue
                gold = json.loads(Path(row["gold_path"]).read_text(encoding="utf-8"))
                status, _ = request_json("POST", sink + "/_replay/active", env["SINK_TOKEN"],
                                         {"input_id": row["input_id"], "pass": pass_name})
                if status != 200:
                    raise RuntimeError("sink did not accept active input")
                fault = gold.get("fault")
                if fault and fault.get("pass") == pass_name:
                    request_json("POST", sink + "/_replay/fault", env["SINK_TOKEN"], fault)
                before = n8n.latest_id(workflow["id"])
                response_status = submit(webhook, env["T2_WEBHOOK_TOKEN"], run_id, gold,
                                         Path(args.inputs_dir) / row["filename"])
                if response_status < 200 or (400 <= response_status < 500):
                    raise RuntimeError("webhook submission returned HTTP {}".format(response_status))
                execution = n8n.wait_execution(workflow["id"], before)
                events = trace_events(execution, run_id, pass_name, row["input_id"], price_in, price_out)
                all_events.extend(events)
                total_usd += sum(event["usd"] for event in events)
                request_json("POST", sink + "/_replay/fault", env["SINK_TOKEN"], {})
    finally:
        if published:
            n8n.unpublish(workflow["id"])
        if handler_published:
            n8n.unpublish(handler["id"])
        if sink_process is not None:
            sink_process.stop()
    with trace_path.open("w", encoding="utf-8") as f:
        for event in all_events:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")
    tokens_in = sum(event.get("tokens_in", 0) for event in all_events)
    tokens_out = sum(event.get("tokens_out", 0) for event in all_events)
    llm_calls = sum(event["node"] == settings["llm_node"] for event in all_events)
    if replay_of:
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        summary["replay_check"] = {"started": started, "ended": utc_now(), "pass": "B", "inputs": len(rows),
                                   "new_header_rows": _count_rows(run_dir / "sink" / "invoices.csv") - headers_before,
                                   "llm_calls": llm_calls, "usd": total_usd}
    else:
        summary = {"run_id": run_id, "phase": args.phase, "target": "local", "workflow_sha256": workflow_sha,
                   "n8n_version": "2.22.5", "model": settings["model"], "started": started,
                   "ended": utc_now(), "inputs": len(rows), "passes": args.passes, "tokens": tokens_in + tokens_out,
                   "usd": total_usd, "capped": capped}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    ledger = Path(args.cost_ledger)
    write_header = not ledger.exists()
    with ledger.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_HEADER)
        if write_header:
            writer.writeheader()
        writer.writerow({"run_id": run_id + ("-replayB" if replay_of else ""), "run_phase": args.phase,
                         "target": "local", "started_utc": started,
                         "ended_utc": utc_now(), "model": settings["model"], "llm_calls": llm_calls,
                         "tokens_in": tokens_in, "tokens_out": tokens_out, "usd": total_usd,
                         "run_usd_cap": RUN_CAP, "capped_inputs": capped})
    return run_dir


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "run"))
    parser.add_argument("--target", default="local", choices=("local",))
    parser.add_argument("--phase", required=True, choices=("baseline", "hardened"))
    parser.add_argument("--baseline-mode", default="as-published", choices=("as-published", "repaired"))
    parser.add_argument("--passes", default="AB", choices=("A", "AB"))
    parser.add_argument("--workflow", default=None, help="default: baseline equivalent or hardened by phase")
    parser.add_argument("--handler-workflow", default=str(HANDLER))
    parser.add_argument("--replay-of", default=None, help="I-8: replay pass B into this existing run's sink")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--repaired-workflow", default=str(REPAIRED_BASELINE))
    parser.add_argument("--sqlite", required=True)
    parser.add_argument("--manifest", default="evals/inputs/manifest.csv")
    parser.add_argument("--inputs-dir", default="evals/inputs")
    parser.add_argument("--runs-dir", default="evals/runs")
    parser.add_argument("--cost-ledger", default="evals/cost_ledger.csv")
    parser.add_argument("--no-start-sink", dest="start_sink", action="store_false")
    args = parser.parse_args(argv)
    load_env_file(args.env_file)
    if args.command == "setup":
        if args.target != "local":
            raise ValueError("T7 permits the local target only")
        # §3.6 local target: credentials are created in memory from the environment, never written to disk.
        LocalN8n(args.sqlite).import_credentials(credential_payload(os.environ))
    else:
        run_replay(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
