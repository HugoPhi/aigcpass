#!/usr/bin/env python3
"""Read CSV → write input_fragments.txt + input_paragraphs.txt.

Usage: python3 make_input.py [--jobid JOBID]
"""
import csv, re, os, argparse

parser = argparse.ArgumentParser()
parser.add_argument("--jobid", default="default")
args = parser.parse_args()

JOBID = args.jobid
from _root import ROOT as BASE
JOB  = os.path.join(BASE, "jobs", JOBID)
CSV  = os.path.join(JOB, "result", "stage1", "疑似AIGC片段.csv")
INP_F = os.path.join(JOB, "result", "stage1", "input_fragments.txt")
INP_P = os.path.join(JOB, "result", "stage1", "input_paragraphs.txt")

if not os.path.exists(CSV):
    print(f"ERROR: {CSV} not found")
    exit(1)

with open(CSV, encoding="utf-8-sig") as f:
    rows = list(csv.reader(f))
# Header: 标记ID, AIGC片段, AIGC段落

def write_input(path, col_idx):
    with open(path, "w", encoding="utf-8") as f:
        for i, row in enumerate(rows[1:]):
            text = row[col_idx].replace("\n", " ").replace("\r", " ")
            text = re.sub(r"\s+", " ", text).strip()
            f.write(text)
            if i < len(rows) - 2: f.write("\n\n\n")
    return len(rows) - 1

n = write_input(INP_F, 1)  # AIGC片段
print(f"input_fragments.txt : {n} paragraphs")
n = write_input(INP_P, 2)  # AIGC段落
print(f"input_paragraphs.txt: {n} paragraphs")
