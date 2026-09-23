import argparse
import json
import os
import random
import re
import urllib.request
from pathlib import Path

import metrics_schema


def load_key():
    for name in ["DEEPSEEK_LAB_API_KEY", "DEEPSEEK_API_KEY"]:
        value = os.environ.get(name)
        if value:
            return value.strip().rstrip(",")
    path = Path.home() / ".dsh" / ".credentials.yaml"
    if path.exists():
        found = {}
        for line in path.read_text().splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'").rstrip(",")
                if key in ["DEEPSEEK_LAB_API_KEY", "DEEPSEEK_API_KEY"] and value:
                    found[key] = value
        for name in ["DEEPSEEK_LAB_API_KEY", "DEEPSEEK_API_KEY"]:
            if name in found:
                return found[name]
    return None


def load_candidates(sweep_paths):
    table = {}
    for sweep_path in sweep_paths:
        sweep = json.loads(Path(sweep_path).read_text())
        design = sweep.get("design", "gcd")
        table.setdefault(design, {})
        for record in sweep["runs"]:
            if record.get("gate_ok"):
                table[design][record["variant"]] = metrics_schema.canonicalize_record(record)
    return table


def timing_guard_ok(record, base, guard_ns=0.02):
    return metrics_schema.timing_guard_ok(record, base, guard_ns=guard_ns, require_setup=True)


def timing_guard_text(record, base, guard_ns=0.02):
    status = metrics_schema.guard_status(record, base, guard_ns=guard_ns)
    parts = []
    for name, check in status["checks"].items():
        if not check.get("checked"):
            parts.append("%s=missing" % name)
        else:
            parts.append("%s=%s(%s)" % (name, "ok" if check["ok"] else "FAIL", check["reason"]))
    return ", ".join(parts)


SCORE_UNSAFE_PENALTY = 1.0


def utility(record, base):
    return metrics_schema.utility(record, base)


def selection_score(record, base):
    """Gate-aware score for oracle/regret.

    Unsafe candidates remain numerically rankable but receive a fixed penalty so a
    selector that ignores the timing gate shows a positive regret.
    """
    score = utility(record, base)
    if record.get("gate_ok") and timing_guard_ok(record, base):
        return score
    return score - SCORE_UNSAFE_PENALTY


def oracle(candidate_table, design):
    candidates = candidate_table[design]
    base = candidates["base"]
    valid = [(name, rec) for name, rec in candidates.items()
             if rec.get("gate_ok") and timing_guard_ok(rec, base)]
    if not valid:
        valid = [(name, rec) for name, rec in candidates.items() if rec.get("gate_ok")]
    best = max(valid, key=lambda kv: utility(kv[1], base))
    return best[0]


def promise(state, candidate_table, policy):
    design = state["design"]
    candidates = list(candidate_table[design].keys())
    base = candidate_table[design]["base"]
    if policy == "rule":
        if "pad_2" in candidates:
            return "pad_2"
        if "density_040" in candidates:
            return "density_040"
        return "base"
    if policy == "oracle":
        return oracle(candidate_table, design)
    if policy == "random_mean":
        values = [selection_score(candidate_table[design][c], base) for c in candidates]
        best = max(values)
        return "random_mean", sum(best - v for v in values) / len(values)
    return "base"


def call_llm(state, candidate_table, key):
    design = state["design"]
    candidates = candidate_table[design]
    base = candidates["base"]
    lines = []
    lines.append("Design state (post-route, canonical timing fields):")
    for field in ["instance_count", "hpwl_route_um", "setup_wns_ns", "hold_wns_ns",
                  "setup_tns_ns", "hold_tns_ns", "clock_skew_ns", "vias",
                  "total_power_w", "wirelength_um", "duration_s"]:
        lines.append("  %s: %s" % (field, state.get(field)))
    lines.append("Hard timing gate (canonical): setup_wns_ns (DRT::worst_slack_max) "
                 "must be >= base_setup_wns_ns - 0.02 ns, and hold_wns_ns "
                 "(DRT::worst_slack_min) must be >= base_hold_wns_ns - 0.02 ns; "
                 "if a baseline value is nonnegative, the candidate must stay "
                 "nonnegative for that analysis. Reject any candidate that fails. "
                 "Among timing-safe candidates optimize HPWL/TNS/power; WNS is a gate only.")
    lines.append("Candidate skills (baseline-normalized; do not use WNS as a soft score):")
    for name, record in candidates.items():
        lines.append("  %s: hpwl=%s setup_wns=%s hold_wns=%s setup_tns=%s vias=%s power=%s guard=[%s]" % (
            name, record.get("hpwl_route_um"), record.get("setup_wns_ns"),
            record.get("hold_wns_ns"), record.get("setup_tns_ns"), record.get("vias"),
            record.get("total_power_w"), timing_guard_text(record, base)))
    lines.append("Choose one timing-safe candidate that gives the best PPA trade-off; output JSON with skill_id.")
    prompt = "\n".join(lines)
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are an EDA hyper-heuristic selector. Output JSON only, with keys skill_id and reason."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 300,
    }
    request = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        body = json.loads(response.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        return None, content
    try:
        parsed = json.loads(match.group(0))
        return parsed.get("skill_id"), parsed.get("reason", "")
    except Exception:
        return None, content


def main():
    parser = argparse.ArgumentParser(description="Phase 0 selector v0: random/rule/oracle/dsv4-flash (canonical WNS)")
    parser.add_argument("--sweep", nargs="+", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-llm", action="store_true", help="skip API calls and only run random/rule/oracle")
    args = parser.parse_args()
    random.seed(args.seed)
    table = load_candidates(args.sweep)
    designs = sorted(table.keys())
    key = None if args.no_llm else load_key()
    rows = []
    for design in designs:
        candidates = table[design]
        base = candidates["base"]
        state = dict(base)
        state["design"] = design
        best = oracle(table, design)
        row = {"design": design, "oracle": best, "candidates": list(candidates.keys())}
        row["random_mean_regret"] = promise(state, table, "random_mean")[1]
        row["rule"] = promise(state, table, "rule")
        if key:
            try:
                choice, reason = call_llm(state, table, key)
                row["llm"] = choice
                row["llm_reason"] = reason
            except Exception as exc:
                row["llm"] = None
                row["llm_error"] = str(exc)
        else:
            row["llm"] = None
            row["llm_error"] = "no key" if not args.no_llm else "skipped_by_flag"
        for name in ["rule", "llm"]:
            chosen = row.get(name)
            if chosen in candidates:
                row[name + "_regret"] = max(selection_score(candidates[best], base) - selection_score(candidates[chosen], base), 0.0)
            else:
                row[name + "_regret"] = None
        row["oracle_regret"] = 0.0
        row["guard_notes"] = {
            name: timing_guard_text(rec, base) for name, rec in candidates.items()
        }
        rows.append(row)
    out = {"seed": args.seed, "designs": rows, "key_found": bool(key),
           "timing_convention": metrics_schema.TIMING_VERSION,
           "utility_spec": metrics_schema.utility_spec()}
    Path(args.out_json).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    lines = ["# Phase 0 selector v0 (canonical setup/hold WNS)", "",
             "| design | candidates | oracle | rule | rule regret | dsv4-flash | llm regret | random mean regret |",
             "|---|---|---|---|---|---|---|---|"]
    for row in rows:
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            row["design"], ",".join(row["candidates"]), row["oracle"], row["rule"],
            row["rule_regret"], row.get("llm"), row.get("llm_regret"), row["random_mean_regret"]))
    lines.append("")
    lines.append("Timing convention: " + metrics_schema.TIMING_VERSION)
    Path(args.out_md).write_text("\n".join(lines) + "\n")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
