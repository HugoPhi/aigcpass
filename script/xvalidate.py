#!/usr/bin/env python3
"""Cross-validate Stage 2 adaptation quality.

Compares the user's optimized text changes (Diff A) with the Agent's
LaTeX adaptation changes (Diff B) for each fragment, flagging any
fragments where the Agent's adaptation is suspiciously weak.

Usage: python3 script/xvalidate.py [--jobid JOBID]
"""
import argparse, csv, os, re, sys

parser = argparse.ArgumentParser()
parser.add_argument("--jobid", default="default")
args = parser.parse_args()

# Find project root (scripts now live in .claude/skills/aigcpass/script/)
import os as _os
def _find_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while d != "/" and not _os.path.exists(_os.path.join(d, ".git")):
        d = _os.path.dirname(d)
    return d if d != "/" else _os.getcwd()
BASE = _find_root()
JOB  = os.path.join(BASE, "jobs", args.jobid)

OPT = os.path.join(JOB, "report", "AIGC片段优化.txt")
INP = os.path.join(JOB, "result", "stage1", "input_fragments.txt")
CSV = os.path.join(JOB, "result", "stage2", "疑似AIGC片段_待确认.csv")

for fpath, name in [(OPT, "AIGC片段优化.txt"), (INP, "input_fragments.txt"), (CSV, "疑似AIGC片段_待确认.csv")]:
    if not os.path.exists(fpath):
        print(f"ERROR: {name} not found at {fpath}")
        sys.exit(1)

with open(OPT) as f:
    opt_parts = [p.strip() for p in f.read().split("\n\n\n") if p.strip()]
with open(INP) as f:
    inp_parts = [p.strip() for p in f.read().split("\n\n\n") if p.strip()]
with open(CSV, encoding="utf-8-sig") as f:
    rows = list(csv.reader(f))

header = rows[0]
col_orig = header.index("原片段")
col_mod  = header.index("修改后片段")

def words(text):
    return set(re.sub(r"[^\w\s]", "", text).split())

def strip_latex(t):
    t = re.sub(r'\\begin\{equation\}.*?\\end\{equation\}', ' ', t, flags=re.DOTALL)
    t = re.sub(r'\\begin\{aligned\}.*?\\end\{aligned\}', ' ', t, flags=re.DOTALL)
    t = re.sub(r'\\begin\{table\}.*?\\end\{table\}', ' ', t, flags=re.DOTALL)
    t = re.sub(r'\\begin\{enumerate\}.*?\\end\{enumerate\}', ' ', t, flags=re.DOTALL)
    t = re.sub(r'\\begin\{figure\}.*?\\end\{figure\}', ' ', t, flags=re.DOTALL)
    t = re.sub(r'\\[a-zA-Z]+(\{[^}]*\})*', ' ', t)
    t = re.sub(r'\\[a-zA-Z]+', ' ', t)
    t = re.sub(r'\$[^$]*\$', ' ', t)
    t = re.sub(r'\\\(.*?\\\)', ' ', t)
    return t

print(f"{'Frag':>5s} {'Diff A':>8s} {'Diff B':>8s} {'Status'}")
print("-" * 45)
errors = 0

for row in rows[1:]:
    mid = int(row[0])
    orig = row[col_orig]
    mod = row[col_mod]

    # Diff B
    ow = words(strip_latex(orig))
    mw = words(strip_latex(mod))
    diff_b = len(mw - ow) + len(ow - mw)
    ratio_b = diff_b / max(len(ow), 1) * 100

    # Diff A
    i = mid - 1
    ow_opt = words(opt_parts[i]) if i < len(opt_parts) else set()
    pw_inp = words(inp_parts[i]) if i < len(inp_parts) else set()
    diff_a = len(ow_opt - pw_inp) + len(pw_inp - ow_opt)
    ratio_a = diff_a / max(len(pw_inp), 1) * 100

    status = "OK"
    if "<不用改>" in opt_parts[i]:
        status = "SKIP (marked <不用改>)"
    elif ratio_b < 1 and ratio_a > 5:
        status = "FAIL: 0% adaptation but user made changes"
        errors += 1
    elif ratio_b < 3 and ratio_a > 20:
        status = "WARN: very weak adaptation vs user changes"
        errors += 1

    print(f"{mid:5d} {ratio_a:6.1f}% {ratio_b:6.1f}%  {status}")

print(f"\n{errors} issue(s) found.")
sys.exit(1 if errors else 0)
