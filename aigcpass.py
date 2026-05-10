#!/usr/bin/env python3
"""aigcpass — AIGC 检测报告处理流水线管理工具

所有功能的统一入口。用法：

  python3 aigcpass.py init --jobid JOBID       创建新 job
  python3 aigcpass.py stage1 --jobid JOBID     执行 Stage 1（提取标记）
  python3 aigcpass.py stage2 --jobid JOBID     执行 Stage 2（API 适配，带面板）
  python3 aigcpass.py diff --csv CSV -t A B    对比 CSV 两个字段
  python3 aigcpass.py xvalidate --jobid JOBID  交叉验证 Stage 2 结果
  python3 aigcpass.py apply --jobid JOBID      将确认后的 CSV 写入 main.tex
"""
import argparse, csv, os, re, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.abspath(__file__))


# ─── helpers ──────────────────────────────────────────────────────────
def _run_script(script_rel, extra_args=None, passthru=False):
    """Run a python script from the script/ directory."""
    script = os.path.join(BASE, "script", script_rel)
    cmd = [sys.executable, "-u", script] + (extra_args or [])
    if passthru:
        os.execv(sys.executable, cmd)
    else:
        subprocess.run(cmd, check=True)


def _job_path(jobid, *parts):
    return os.path.join(BASE, "jobs", jobid, *parts)


# ─── init ────────────────────────────────────────────────────────────
def cmd_init(args):
    jobdir = _job_path(args.jobid)
    for d in ["report", "result/stage1", "result/stage2"]:
        os.makedirs(os.path.join(jobdir, d), exist_ok=True)
    tex = os.path.join(jobdir, "main.tex")
    if not os.path.exists(tex):
        open(tex, "w").close()
    print(f"Job '{args.jobid}' 已创建:")
    print(f"  {jobdir}/")
    print(f"  {jobdir}/report/")
    print(f"  {jobdir}/result/stage1/")
    print(f"  {jobdir}/result/stage2/")
    print(f"  {tex}")
    print()
    print("下一步:")
    print(f"  1. 将 LaTeX 源文件放入 jobs/{args.jobid}/main.tex")
    print(f"  2. 将 AIGC 检测报告 HTML 放入 jobs/{args.jobid}/report/")
    print(f"  3. python3 aigcpass.py stage1 --jobid {args.jobid}")


# ─── stage1 ─────────────────────────────────────────────────────────
def cmd_stage1(args):
    _run_script("extract_aigc.py", ["--jobid", args.jobid])


# ─── stage2 ─────────────────────────────────────────────────────────
def cmd_stage2(args):
    """Run Stage 2 API adaptation. Passes through to keep the live dashboard."""
    script = os.path.join(BASE, "script", "stage2_api.py")
    cmd = [sys.executable, "-u", script, "--jobid", args.jobid,
           "--concurrency", str(args.concurrency)]
    if args.start:
        cmd += ["--start", str(args.start)]
    if args.end:
        cmd += ["--end", str(args.end)]
    if args.no_dashboard:
        cmd += ["--no-dashboard"]
    # execv replaces this process so the live dashboard gets the terminal
    os.execv(sys.executable, cmd)


# ─── diff ────────────────────────────────────────────────────────────
def write_input_format(path, items):
    with open(path, "w", encoding="utf-8") as f:
        for i, text in enumerate(items):
            line = text.replace("\n", " ").replace("\r", " ")
            line = re.sub(r"\s+", " ", line).strip()
            f.write(line)
            if i < len(items) - 1:
                f.write("\n\n\n")


def cmd_diff(args):
    csv_path = args.csv
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    header = rows[0]
    for cn in [args.col1, args.col2]:
        if cn not in header:
            print(f"ERROR: column '{cn}' not found. Available: {header}", file=sys.stderr)
            sys.exit(1)

    idx1, idx2 = header.index(args.col1), header.index(args.col2)
    items1 = [row[idx1] for row in rows[1:]]
    items2 = [row[idx2] for row in rows[1:]]

    tmpdir = tempfile.mkdtemp(prefix="aigcpass_diff_")
    file1 = os.path.join(tmpdir, args.col1)
    file2 = os.path.join(tmpdir, args.col2)
    write_input_format(file1, items1)
    write_input_format(file2, items2)

    try:
        p1 = subprocess.Popen(["icdiff", file1, file2], stdout=subprocess.PIPE)
        subprocess.run(["less", "-R"], stdin=p1.stdout)
        p1.stdout.close()
        p1.wait()
    except FileNotFoundError:
        print("ERROR: icdiff 未安装。请运行: brew install icdiff", file=sys.stderr)
        sys.exit(1)
    finally:
        os.remove(file1); os.remove(file2); os.rmdir(tmpdir)


# ─── xvalidate ──────────────────────────────────────────────────────
def cmd_xvalidate(args):
    _run_script("xvalidate.py", ["--jobid", args.jobid])


# ─── apply ──────────────────────────────────────────────────────────
def cmd_apply(args):
    _run_script("apply_stage2.py", ["--jobid", args.jobid])


# ─── diagnose ───────────────────────────────────────────────────────
def cmd_diagnose(args):
    _run_script("diagnose_fragments.py")


# ─── CLI ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="AIGC 检测报告处理流水线管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 aigcpass.py init --jobid mypaper
  python3 aigcpass.py stage1 --jobid mypaper
  python3 aigcpass.py stage2 --jobid mypaper --concurrency 3
  python3 aigcpass.py diff --csv jobs/mypaper/result/stage2/疑似AIGC片段_待确认.csv -t 原片段 修改后片段
  python3 aigcpass.py xvalidate --jobid mypaper
  python3 aigcpass.py apply --jobid mypaper
        """,
    )
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("init", help="创建新 job 目录结构")
    p.add_argument("--jobid", default="default")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("stage1", help="执行 Stage 1：提取 AIGC 片段并插入标记")
    p.add_argument("--jobid", default="default")
    p.set_defaults(func=cmd_stage1)

    p = sub.add_parser("stage2", help="执行 Stage 2：LLM API 逐段适配（实时面板）")
    p.add_argument("--jobid", default="default")
    p.add_argument("--concurrency", type=int, default=3)
    p.add_argument("--start", type=int)
    p.add_argument("--end", type=int)
    p.add_argument("--no-dashboard", action="store_true")
    p.set_defaults(func=cmd_stage2)

    p = sub.add_parser("diff", help="对比 CSV 两个字段（icdiff 分屏）")
    p.add_argument("--csv", required=True, dest="csv")
    p.add_argument("-t", nargs=2, required=True, dest="cols",
                   metavar=("COL1", "COL2"), help="要对比的两个字段名")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("xvalidate", help="交叉验证 Stage 2 适配质量")
    p.add_argument("--jobid", default="default")
    p.set_defaults(func=cmd_xvalidate)

    p = sub.add_parser("apply", help="将确认后的 CSV 写入 main.tex")
    p.add_argument("--jobid", default="default")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("diagnose", help="诊断 CSV 段落数匹配情况")
    p.set_defaults(func=cmd_diagnose)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    if args.cmd == "diff":
        args.col1, args.col2 = args.cols

    args.func(args)


if __name__ == "__main__":
    main()
