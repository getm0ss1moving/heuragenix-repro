"""Objective-mode conditioned EDA selector (HA-PR Phase 1, P2).

PHASE0_ORACLE_SENSITIVITY showed gcd aes have mode-dependent optima
(weighted_v2 vs lex_hpwl vs lex_power). This module makes objective_mode explicit
instead of claiming one oracle:

  modes: balanced | timing_first | HPWL_first | power_first

Mode-specific scalar score (relative improvements, higher better):
  balanced      0.5*d_HPWL + 0.4*d_TNS + 0.1*d_power   (canonical weighted_v2)
  timing_first  0.1*d_HPWL + 0.8*d_TNS + 0.1*d_power
  HPWL_first    0.8*d_HPWL + 0.1*d_TNS + 0.1*d_power
  power_first   0.1*d_HPWL + 0.1*d_TNS + 0.8*d_power

The lex_* policies in PHASE0_ORACLE_SENSITIVITY are qualitative checks; this
module evaluates mode-conditioned regret against the scalar above and reports
mode accuracy / gate pass rate for a selector that must output objective_mode.

Usage (offline sensitivity):
  python3 harness/selector_objective_mode.py --no-llm --mode all \
    --sweep results/canonical_server/gcd_candidates.json ... \
    --out-json results/canonical_server/PHASE0_OBJECTIVE_MODE_SELECTOR.json \
    --out-md results/canonical_server/PHASE0_OBJECTIVE_MODE_SELECTOR.md
"""
from __future__ import annotations
import argparse
import json
import re
import urllib.request
from pathlib import Path

import metrics_schema
import selector_v0

MODES = ["balanced", "timing_first", "HPWL_first", "power_first"]
WEIGHTS = {
    "balanced": (0.5, 0.4, 0.1),
    "timing_first": (0.1, 0.8, 0.1),
    "HPWL_first": (0.8, 0.1, 0.1),
    "power_first": (0.1, 0.1, 0.8),
}
MODE_TEXT = {
    "balanced": "balance HPWL, timing TNS and power (0.5/0.4/0.1)",
    "timing_first": "prioritize setup TNS improvement; HPWL/power are secondary",
    "HPWL_first": "prioritize routed HPWL reduction; TNS/power are secondary",
    "power_first": "prioritize total power reduction; HPWL/TNS are secondary",
}


def rel_components(record, base):
    hp = metrics_schema.fnum(record.get("hpwl_route_um"))
    bhp = metrics_schema.fnum(base.get("hpwl_route_um"))
    tns = metrics_schema.fnum(record.get("setup_tns_ns"))
    btns = metrics_schema.fnum(base.get("setup_tns_ns"))
    power = metrics_schema.fnum(record.get("total_power_w"))
    bpow = metrics_schema.fnum(base.get("total_power_w"))
    d_hpwl = ((bhp - hp) / bhp) if (hp is not None and bhp not in (None, 0)) else 0.0
    d_tns = ((abs(btns) - abs(tns)) / abs(btns)) if (tns is not None and btns not in (None, 0)) else 0.0
    d_power = ((bpow - power) / bpow) if (power is not None and bpow not in (None, 0)) else 0.0
    return {"d_hpwl": d_hpwl, "d_tns": d_tns, "d_power": d_power}


def mode_score(record, base, mode):
    comp = rel_components(record, base)
    w = WEIGHTS[mode]
    return w[0] * comp["d_hpwl"] + w[1] * comp["d_tns"] + w[2] * comp["d_power"], comp


def safe_candidates(candidates, base):
    out = {}
    for name, rec in candidates.items():
        if name == "base":
            continue
        if rec.get("gate_ok") and metrics_schema.timing_guard_ok(rec, base, require_setup=True):
            out[name] = rec
    return out


def oracle_for_mode(candidates, base, mode):
    safe = safe_candidates(candidates, base)
    if not safe:
        return None, {}, {}
    scores = {name: mode_score(rec, base, mode)[0] for name, rec in safe.items()}
    best = max(scores, key=lambda k: scores[k])
    return best, scores, safe


def evaluate_choice(candidates, base, mode, choice):
    oracle, scores, safe = oracle_for_mode(candidates, base, mode)
    if choice not in candidates:
        return {"choice": choice, "valid_choice": False, "oracle": oracle, "mode_score": None,
                "conditional_regret": None, "gate_ok": False, "safe": False}
    gate_ok = bool(candidates[choice].get("gate_ok")) and metrics_schema.timing_guard_ok(candidates[choice], base, require_setup=True)
    score = mode_score(candidates[choice], base, mode)[0]
    regret = None
    if oracle is not None:
        regret = max(0.0, scores[oracle] - score)
    return {"choice": choice, "valid_choice": True, "oracle": oracle, "mode_score": score,
            "conditional_regret": regret, "gate_ok": gate_ok, "safe": choice in safe}


def call_llm(design, state, candidates, base, mode, key, temperature=0.0):
    lines = []
    lines.append("Objective mode: %s (%s)." % (mode, MODE_TEXT[mode]))
    lines.append("Design state (post-route canonical timing):")
    for field in ["instance_count", "hpwl_route_um", "setup_wns_ns", "hold_wns_ns",
                  "setup_tns_ns", "hold_tns_ns", "vias", "total_power_w", "wirelength_um"]:
        lines.append("  %s: %s" % (field, state.get(field)))
    lines.append("Hard timing gate (canonical, setup + hold separately): setup_wns_ns >= "
                 "base_setup_wns_ns - 0.02 ns; hold_wns_ns >= base_hold_wns_ns - 0.02 ns; "
                 "if base value is nonnegative the candidate must stay nonnegative. WNS is a "
                 "gate only, never the soft objective.")
    lines.append("Candidate skills (baseline-normalized):")
    for name, rec in candidates.items():
        if name == "base":
            continue
        comp = rel_components(rec, base)
        lines.append("  %s: gate_hint=%s d_hpwl=%.4f d_tns=%.4f d_power=%.4f" % (
            name, "safe" if (rec.get("gate_ok") and metrics_schema.timing_guard_ok(rec, base, require_setup=True)) else "unsafe",
            comp["d_hpwl"], comp["d_tns"], comp["d_power"]))
    lines.append("Choose the timing-safe candidate that best serves objective_mode='%s'. "
                 "Output JSON only with keys objective_mode, skill_id, reason." % mode)
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are an EDA hyper-heuristic selector. Output JSON only."},
            {"role": "user", "content": "\n".join(lines)},
        ],
        "temperature": temperature,
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
        return {"raw": content, "parsed": None}
    try:
        parsed = json.loads(match.group(0))
    except Exception:
        return {"raw": content, "parsed": None}
    return {"raw": content, "parsed": parsed, "reason": parsed.get("reason", "")}


def main():
    ap = argparse.ArgumentParser(description="Objective-mode conditioned selector / sensitivity")
    ap.add_argument("--sweep", nargs="+", required=True)
    ap.add_argument("--out-json", default="results/canonical_server/PHASE0_OBJECTIVE_MODE_SELECTOR.json")
    ap.add_argument("--out-md", default="results/canonical_server/PHASE0_OBJECTIVE_MODE_SELECTOR.md")
    ap.add_argument("--mode", default="all", help="balanced,timing_first,HPWL_first,power_first,all")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    modes = MODES if args.mode == "all" else [m.strip() for m in args.mode.split(",") if m.strip()]
    for mode in modes:
        if mode not in MODES:
            raise SystemExit("unknown mode: %s" % mode)
    table = selector_v0.load_candidates(args.sweep)
    key = None if args.no_llm else selector_v0.load_key()

    rows = []
    for design in sorted(table):
        candidates = table[design]
        base = candidates["base"]
        state = dict(base)
        state["design"] = design
        for mode in modes:
            oracle, scores, safe = oracle_for_mode(candidates, base, mode)
            row = {
                "design": design, "mode": mode, "oracle": oracle,
                "safe_candidates": sorted(safe),
                "unsafe_candidates": sorted(n for n in candidates if n != "base" and n not in safe),
                "mode_scores": scores,
                "weights": WEIGHTS[mode],
            }
            if key is not None:
                try:
                    resp = call_llm(design, state, candidates, base, mode, key)
                    parsed = resp.get("parsed") or {}
                    choice = parsed.get("skill_id")
                    reported_mode = parsed.get("objective_mode")
                    ev = evaluate_choice(candidates, base, mode, choice)
                    ev["mode_accuracy"] = (reported_mode == mode) if reported_mode else None
                    ev["reported_mode"] = reported_mode
                    ev["llm_reason"] = resp.get("reason", "")
                    row["llm"] = ev
                except Exception as exc:
                    row["llm"] = {"error": str(exc)}
            rows.append(row)
    out = {
        "seed": args.seed,
        "modes": modes,
        "weights": WEIGHTS,
        "designs": rows,
        "key_found": bool(key) if not args.no_llm else False,
        "timing_convention": metrics_schema.TIMING_VERSION,
        "note": "No single oracle: objective mode conditions the oracle. Regret is relative to the mode-conditioned oracle.",
    }
    Path(args.out_json).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")

    lines = ["# Objective-mode conditioned selector", "",
             "| design | mode | safe candidates | mode oracle | LLM choice | mode acc | gate | cond. regret |",
             "|---|---|---|---|---|---|---|---|"]
    for row in rows:
        llm = row.get("llm") or {}
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            row["design"], row["mode"], ",".join(row["safe_candidates"]) or "NONE",
            row["oracle"], llm.get("choice", "-"), llm.get("mode_accuracy", "-"),
            llm.get("gate_ok", "-"), llm.get("conditional_regret", "-")))
    lines.append("")
    lines.append("Mode weights (d_HPWL, d_TNS, d_power): " + json.dumps(WEIGHTS, ensure_ascii=False))
    lines.append("WNS is a hard gate (setup and hold separately, guard 0.02 ns); not a soft objective.")
    Path(args.out_md).write_text("\n".join(lines) + "\n")
    print(json.dumps({"n_rows": len(rows), "modes": modes, "key_found": out["key_found"]}, indent=2))
    print("OBJECTIVE_MODE_WRITTEN", args.out_json, args.out_md)


if __name__ == "__main__":
    main()
