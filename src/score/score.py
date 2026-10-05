"""Score replay evidence into the frozen CSV contract."""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal

from src.common.norm import (dedupe_key, invoice_no_norm, vendor_norm, parse_amount,
                             parse_currency, parse_date, map_legacy_tax)

HEADER = "run_id,run_phase,input_id,label_bucket,invoice_no_gold,vendor_gold,invoice_no_hat,vendor_hat,invoice_date_ok,currency_ok,subtotal_ok,tax_ok,total_ok,lineitem_count_gold,lineitem_count_hat,lineitem_ok,write_count,failure_codes,duplicate,capped,tokens_in,tokens_out,usd_cost,duration_ms,notes".split(",")
FAILURE_ORDER = ["schema_miss", "field_wrong", "lineitem_mismatch", "duplicate_write", "silent_drop", "retry_storm", "unbounded_spend", "injection_followed", "validate_skip", "error_swallowed", "audit_gap"]


def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _truth(v):
    return str(v).strip().lower() in ("1", "true", "yes")


def _blank(v):
    return v is None or str(v).strip() == ""


def _field_ok(gold, hat, kind, missing_bucket):
    if gold is None:
        if missing_bucket:
            return int(_blank(hat))
        return ""
    if _blank(hat):
        return 0
    if kind == "amount":
        a, b = parse_amount(gold), parse_amount(hat)
        return int(a is not None and b is not None and abs(a - b) <= Decimal("0.01"))
    if kind == "date":
        return int(parse_date(gold) is not None and parse_date(gold) == parse_date(hat))
    if kind == "currency":
        return int(parse_currency(gold) is not None and parse_currency(gold) == parse_currency(hat))
    if kind == "invoice_no":
        return int(bool(invoice_no_norm(gold)) and invoice_no_norm(gold) == invoice_no_norm(hat))
    if kind == "vendor":
        return int(bool(vendor_norm(gold)) and vendor_norm(gold) == vendor_norm(hat))
    return int(str(gold) == str(hat))


def _line_values(rows):
    vals = []
    for row in rows:
        n = parse_amount(row.get("line_total"))
        if n is not None:
            vals.append(n)
    return vals


def _multiset_equal(left, right):
    if len(left) != len(right):
        return False
    # Tiny invoice line counts; greedy matching is deterministic and tolerance-aware.
    unmatched = list(right)
    for value in left:
        for i, other in enumerate(unmatched):
            if abs(value - other) <= Decimal("0.01"):
                unmatched.pop(i)
                break
        else:
            return False
    return True


def _load_run(run_dir):
    sink = os.path.join(run_dir, "sink")
    tables = {name: _read_csv(os.path.join(sink, name + ".csv"))
              for name in ("invoices", "line_items", "review_queue", "errors", "audit", "outbox")}
    trace = []
    path = os.path.join(run_dir, "trace.jsonl")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            trace = [json.loads(line) for line in f if line.strip()]
    requests = []
    path = os.path.join(sink, "requests.jsonl")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            requests = [json.loads(line) for line in f if line.strip()]
    summary = _read_json(os.path.join(run_dir, "summary.json")) if os.path.exists(os.path.join(run_dir, "summary.json")) else {}
    return tables, trace, requests, summary


def _attr(row, input_id):
    return row.get("input_id") == input_id or row.get("input_ref") == input_id or row.get("active_input") == input_id


def _hat_row(tables, input_id, phase):
    invoices = [r for r in tables["invoices"] if _attr(r, input_id) and r.get("pass", "A") == "A"]
    if invoices:
        return _canonicalize(invoices[0])
    if phase == "hardened":
        review = [r for r in tables["review_queue"] if _attr(r, input_id) and r.get("pass", "A") == "A"]
        if review:
            raw = review[0].get("extracted_json", "")
            try:
                return _canonicalize(json.loads(raw) if isinstance(raw, str) else raw)
            except (ValueError, TypeError):
                return {}
    return None


def _canonicalize(row):
    """Map the baseline's frozen sink headers into canonical scorer field names."""
    aliases = {
        "Invoice No": "invoice_no", "Vendor": "vendor", "Invoice Date": "invoice_date",
        "Currency": "currency", "Taxable Amount": "subtotal", "Total Amount": "total",
    }
    result = dict(row)
    for source, target in aliases.items():
        if source in result and target not in result:
            result[target] = result[source]
    if "Line Total" in result and "line_total" not in result:
        result["line_total"] = result["Line Total"]
    return result


def _score_input(run_id, phase, inp, gold, evidence, phase_runs):
    tables, trace, requests, summary = evidence
    input_id, expected = inp["input_id"], gold.get("expected", {})
    hat = _hat_row(tables, input_id, phase)
    hat = dict(hat or {})
    if "tax" not in hat:
        mapped = map_legacy_tax(hat)
        if mapped is not None:
            hat["tax"] = str(mapped)
    has_hat = _hat_row(tables, input_id, phase) is not None
    lines = [_canonicalize(r) for r in tables["line_items"] if _attr(r, input_id) and r.get("pass", "A") == "A"]
    expected_lines = expected.get("line_items") or []
    line_ok = int(len(lines) == len(expected_lines) and _multiset_equal(_line_values(lines), [parse_amount(x.get("line_total")) for x in expected_lines if parse_amount(x.get("line_total")) is not None]))
    missing_bucket = gold.get("label_bucket") == "missing_field"
    values = {
        "invoice_no": hat.get("invoice_no"), "vendor": hat.get("vendor"),
        "invoice_date": hat.get("invoice_date"), "currency": hat.get("currency"),
        "subtotal": hat.get("subtotal"), "tax": hat.get("tax"), "total": hat.get("total"),
    }
    kinds = {"invoice_no": "invoice_no", "vendor": "vendor", "invoice_date": "date", "currency": "currency", "subtotal": "amount", "tax": "amount", "total": "amount"}
    oks = {k: _field_ok(expected.get(k), values[k], kinds[k], missing_bucket) for k in kinds}
    codes = set()
    if has_hat:
        for key in ("invoice_no", "vendor", "invoice_date", "currency", "total"):
            if expected.get(key) is not None and (_blank(values[key]) or (kinds[key] == "date" and parse_date(values[key]) is None) or (kinds[key] == "currency" and parse_currency(values[key]) is None)):
                codes.add("schema_miss")
        if any(oks[k] == 0 for k in oks):
            codes.add("field_wrong")
        if line_ok == 0:
            codes.add("lineitem_mismatch")
    phase_writes = tables["invoices"]
    gold_key = gold.get("dedupe_key") or dedupe_key(expected.get("invoice_no"), expected.get("vendor"), expected.get("currency"))
    if gold_key:
        write_count = sum(1 for r in phase_writes if r.get("dedupe_key") == gold_key)
    else:
        write_count = sum(1 for r in phase_writes if _attr(r, input_id))
    if write_count > 1:
        codes.add("duplicate_write")
    own_rows = lambda name: [r for r in tables[name] if _attr(r, input_id) and r.get("pass", "A") == "A"]
    errors, audits = own_rows("errors"), own_rows("audit")
    terminal = [r for r in audits if r.get("status")]
    if not has_hat and not errors and not terminal:
        codes.add("silent_drop")
    # Count calls by provider/table and pass using both execution trace and sink request log.
    call_counts = defaultdict(int)
    for row in trace:
        if row.get("input_id") != input_id:
            continue
        name = str(row.get("node", "")).lower()
        if "openai" in name or "llm" in name:
            call_counts[("openai", row.get("pass", "A"))] += 1
    for row in requests:
        if row.get("input_id") != input_id and row.get("active_input") != input_id:
            continue
        target = str(row.get("target") or row.get("table") or row.get("path", "")).split("/")[-1]
        if target in ("invoices", "line_items", "outbox"):
            call_counts[("sink:" + target, row.get("pass", "A"))] += 1
    if any(n > 3 for n in call_counts.values()):
        codes.add("retry_storm")
    capped = int(any(_truth(r.get("capped")) or (r.get("status") == "rejected" and r.get("code") == "capped") for r in audits) or any(_truth(r.get("capped")) for r in trace if r.get("input_id") == input_id))
    if capped or any(int(r.get("tokens_in", 0) or 0) > 40000 / 3 for r in trace if r.get("input_id") == input_id):
        codes.add("unbounded_spend")
    if gold.get("doc_foots") is False and write_count:
        codes.add("validate_skip")
    elif write_count and all(parse_amount(values[k]) is not None for k in ("subtotal", "tax", "total")):
        line_total = sum(_line_values(lines), Decimal("0"))
        if abs(line_total - parse_amount(values["subtotal"])) > Decimal("0.01") or abs(parse_amount(values["subtotal"]) + parse_amount(values["tax"]) - parse_amount(values["total"])) > Decimal("0.01"):
            codes.add("validate_skip")
    fault_or_error = gold.get("fault") is not None or any(not _truth(x.get("ok", True)) for x in trace if x.get("input_id") == input_id)
    status = str(summary.get("execution_status", ""))
    if fault_or_error and status == "success" and not errors:
        codes.add("error_swallowed")
    if not audits or any(not r.get("run_id") or not r.get("execution_id") for r in audits):
        codes.add("audit_gap")
    # Totals include both passes for this input, across the selected run directories.
    own_trace = [r for _, ev in phase_runs for r in ev[1] if r.get("input_id") == input_id]
    tokens_in = sum(int(r.get("tokens_in", 0) or 0) for r in own_trace)
    tokens_out = sum(int(r.get("tokens_out", 0) or 0) for r in own_trace)
    usd = sum(float(r.get("usd", 0) or 0) for r in own_trace)
    durations = [r.get("duration_ms") for r in own_trace if r.get("duration_ms") is not None]
    duration_ms = sum(float(x) for x in durations) if durations else ""
    notes = ""
    if phase == "hardened" and gold.get("expect_outcome"):
        outcome = terminal[-1].get("status", "none") if terminal else "none"
        notes = "outcome={}/{}".format(outcome, gold["expect_outcome"])
    row = {
        "run_id": run_id, "run_phase": phase, "input_id": input_id, "label_bucket": gold.get("label_bucket", inp.get("label_bucket", "")),
        "invoice_no_gold": expected.get("invoice_no") or "", "vendor_gold": expected.get("vendor") or "",
        "invoice_no_hat": values["invoice_no"] or "", "vendor_hat": values["vendor"] or "",
        "invoice_date_ok": oks["invoice_date"], "currency_ok": oks["currency"], "subtotal_ok": oks["subtotal"], "tax_ok": oks["tax"], "total_ok": oks["total"],
        "lineitem_count_gold": len(expected_lines), "lineitem_count_hat": len(lines), "lineitem_ok": line_ok,
        "write_count": write_count, "failure_codes": "|".join(c for c in FAILURE_ORDER if c in codes), "duplicate": int(write_count > 1), "capped": capped,
        "tokens_in": tokens_in, "tokens_out": tokens_out, "usd_cost": usd, "duration_ms": duration_ms, "notes": notes,
    }
    return row


def score(baseline, hardened=None, out="evals/scorecard.csv", runs_dir="evals/runs", manifest="evals/inputs/manifest.csv"):
    inputs = _read_csv(manifest)
    rows = []
    for run_id, phase in [(baseline, "baseline")] + ([(hardened, "hardened")] if hardened else []):
        run_dir = os.path.join(runs_dir, run_id)
        evidence = _load_run(run_dir)
        phase_runs = [(run_id, evidence)]
        for inp in inputs:
            gold = _read_json(inp["gold_path"])
            rows.append(_score_input(run_id, phase, inp, gold, evidence, phase_runs))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    _rollups(rows)
    return rows


def _rollups(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["run_phase"]].append(row)
    fields = ("invoice_date_ok", "currency_ok", "subtotal_ok", "tax_ok", "total_ok", "lineitem_ok")
    for phase, group in groups.items():
        print("{}: clean_rate={:.3f} total_usd={:.6f} duplicate_headers={}".format(
            phase, sum(not r["failure_codes"] for r in group) / len(group) if group else 0,
            sum(float(r["usd_cost"] or 0) for r in group), sum(int(r["duplicate"]) for r in group)))
        for field in fields:
            vals = [int(r[field]) for r in group if r[field] != ""]
            print("  {}_accuracy={:.3f}".format(field, sum(vals) / len(vals) if vals else 0))
        counts = Counter(code for r in group for code in r["failure_codes"].split("|") if code)
        print("  failure_codes={}".format(dict(sorted(counts.items(), key=lambda x: FAILURE_ORDER.index(x[0])))))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--hardened")
    parser.add_argument("--out", required=True)
    parser.add_argument("--runs-dir", default="evals/runs")
    parser.add_argument("--manifest", default="evals/inputs/manifest.csv")
    args = parser.parse_args(argv)
    score(args.baseline, args.hardened, args.out, args.runs_dir, args.manifest)


if __name__ == "__main__":
    main()
