#!/usr/bin/env python3
"""Apply approved Stage 2 modifications to main.tex.

Reads the confirmed CSV (with 修改后片段 column) and replaces the content
between each AIGC_BEGIN_N / AIGC_END_N marker pair with the adapted text.

Usage: python3 apply_stage2.py --jobid JOBID
"""
import csv, re, os, argparse, shutil

parser = argparse.ArgumentParser()
parser.add_argument("--jobid", default="default")
args = parser.parse_args()

from _root import ROOT as BASE
JOB  = os.path.join(BASE, "jobs", args.jobid)
CSV  = os.path.join(JOB, "result", "stage2", "疑似AIGC片段_待确认.csv")
TEX  = os.path.join(JOB, "main.tex")

if not os.path.exists(CSV):
    print(f"ERROR: {CSV} not found")
    exit(1)

with open(CSV, encoding="utf-8-sig") as f:
    rows = list(csv.reader(f))

# Header: 标记ID, AIGC片段, AIGC段落, 原片段, 修改后片段
header = rows[0]
col_modified = header.index("修改后片段")

with open(TEX, encoding="utf-8") as f:
    tex = f.read()

# Process in reverse to keep positions stable
for row in reversed(rows[1:]):
    marker_id = row[0]
    modified  = row[col_modified].strip()

    if not modified:
        continue  # skip empty

    begin = f"% AIGC_BEGIN_{marker_id}"
    end   = f"% AIGC_END_{marker_id}"
    bpos = tex.find(begin)
    epos = tex.find(end)
    if bpos < 0 or epos < 0:
        print(f"  [{marker_id:2s}] MARKER NOT FOUND — skipped")
        continue

    new_block = f"{begin}\n{modified}\n{end}"
    old_block = tex[bpos:epos + len(end)]
    tex = tex.replace(old_block, new_block, 1)
    print(f"  [{marker_id:2s}] inserted ({len(modified)}B)")

with open(TEX, "w", encoding="utf-8") as f:
    f.write(tex)

markers = re.findall(r'% AIGC_(BEGIN|END)_(\d+)', tex)
print(f"\nMarkers: {len(markers)}, IDs: {sorted(set(int(m[1]) for m in markers))}")
print("Done.")
