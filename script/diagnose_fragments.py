#!/usr/bin/env python3
"""Diagnose paragraph counts for problematic fragments."""
import csv, os, re

# Find project root (scripts now live in .claude/skills/aigcpass/script/)
import os as _os
def _find_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while d != "/" and not _os.path.exists(_os.path.join(d, ".git")):
        d = _os.path.dirname(d)
    return d if d != "/" else _os.getcwd()
BASE = _find_root()
CSV  = os.path.join(BASE, "jobs", "default", "result", "stage2", "疑似AIGC片段_待确认.csv")

with open(CSV, encoding="utf-8-sig") as f:
    rows = list(csv.reader(f))

header = rows[0]
col_orig = header.index("原片段")
col_mod  = header.index("修改后片段")

def count_paras(text):
    """Count paragraphs by splitting on blank lines (2+ newlines)."""
    if not text:
        return 0
    # Normalize: collapse 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    parts = [p for p in text.split('\n\n') if p.strip()]
    return len(parts)

def show_paras(text, label):
    paras = count_paras(text)
    print(f"  {label}: {paras} paragraphs")
    return paras

problem_ids = [8, 9, 11, 14, 18]

for row in rows[1:]:
    mid = int(row[0])
    if mid not in problem_ids:
        continue
    print(f"\n{'='*60}")
    print(f"Fragment {mid}")
    print(f"{'='*60}")
    o = show_paras(row[col_orig], "原片段")
    m = show_paras(row[col_mod], "修改后片段")
    if o != m:
        print(f"  *** MISMATCH! 原={o}, 修改后={m} ***")

    # Show first/last 100 chars of modified to detect "pasted after" pattern
    mod_text = row[col_mod]
    orig_text = row[col_orig]
    if len(mod_text) > len(orig_text) * 1.5:
        print(f"  *** 修改后片段 is {len(mod_text)/len(orig_text):.1f}x longer than 原片段 ***")

    # Check if modified contains substantial new content after original ends
    orig_last_50 = orig_text.strip()[-50:]
    idx = mod_text.find(orig_last_50)
    if idx >= 0 and idx + len(orig_last_50) < len(mod_text) - 100:
        leftover = mod_text[idx + len(orig_last_50):].strip()
        print(f"  *** Extra content after original ends: {len(leftover)} chars")
        print(f"  First 80 chars of extra: {leftover[:80]}")
