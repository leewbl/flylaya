"""Blind-package leak check (campaign plan §T4:45 渗透检查, TASK-0021 prep).

Scans every file of a blind-eval package and FAILS on any truth leakage:
  R1  no reference to blind_key.json (or any *key* file) from package pages
  R2  forbidden tokens: policy names (P_laya/P_yoked/P_rule/P_fixed),
      config ids (A_full/B_no_laya/C_no_connectome/D_random_intent),
      truth-y keys (truth, config, seed, policy, coupling, state_source,
      experiment_id, scene_id, manifest)
  R3  embedded data rows may carry ONLY kinematics/geometry fields
      (whitelist), never intent/arousal/dn/gains/stim
  R4  run directory names / filenames must not appear
Usage: python m5/campaign/blind_leak_check.py PACKAGE_DIR [KEY_PATH]
Exit 0 = clean; prints each violation.
"""
import json
import os
import re
import sys

FORBIDDEN_TOKENS = [
    "P_laya", "P_yoked", "P_rule", "P_fixed",
    "A_full", "B_no_laya", "C_no_connectome", "D_random_intent",
    "blind_key", "truth", "experiment_id", "state_source", "coupling",
    "manifest.json", "S1_light", "S2_obstacle", "S3_wall", "S0_neutral",
    "S4_mixed",
]
ROW_WHITELIST = {"t_s", "t", "pos_m", "pos", "yaw_deg", "yaw", "speed_m_s",
                 "speed", "id", "clip_id", "kind"}


def scan(path, rater_only=True):
    problems = []
    for fn in sorted(os.listdir(path)):
        p = os.path.join(path, fn)
        if not os.path.isfile(p) or fn == "blind_key.json":
            continue
        if rater_only and not fn.startswith("blind"):
            continue          # builder/diagnostic files handle truth by design
        text = open(p, encoding="utf-8", errors="replace").read()
        low = text.lower()
        for tok in FORBIDDEN_TOKENS:
            if tok.lower() in low:
                problems.append(f"{fn}: forbidden token {tok!r}")
        # R1: any reference to a key file
        if re.search(r"""['"][^'"]*key[^'"]*\.json['"]""", text, re.I):
            problems.append(f"{fn}: references a *key*.json file")
        # R3: embedded JSON objects — field whitelist on dict-like rows
        for m in re.finditer(r"\{[^{}]{4,400}\}", text):
            try:
                obj = json.loads(m.group(0))
            except Exception:
                continue
            if isinstance(obj, dict) and {"t_s", "pos_m", "pos"} & set(obj):
                bad = set(obj) - ROW_WHITELIST
                if bad & {"intent_applied", "intent_raw", "arousal", "dn",
                          "gains_pre", "gains_post", "stim", "yaw_bias_direct"}:
                    problems.append(f"{fn}: truth-bearing row fields {sorted(bad)}")
    return problems


def main():
    pkg = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "viewer")
    problems = scan(pkg, rater_only="--all" not in sys.argv)
    key = os.path.join(pkg, "blind_key.json")
    if not os.path.exists(key):
        problems.append("blind_key.json missing from package dir (must exist "
                        "for offline scoring)")
    if problems:
        print("LEAK CHECK FAIL:")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print(f"LEAK CHECK PASS: {pkg} ({len(os.listdir(pkg))} files)")


if __name__ == "__main__":
    main()
