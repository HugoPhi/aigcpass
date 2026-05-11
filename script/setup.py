#!/usr/bin/env python3
"""Interactive setup wizard for aigcpass.

Guides the user through:
  1. Creating/finding a job directory
  2. Verifying main.tex and HTML report are in place
  3. Setting up per-job api.yaml from template
  4. Checking all prerequisites for Stage 1 and Stage 2

Usage:
  python3 setup.py                  # interactive mode
  python3 setup.py --jobid mypaper  # skip job selection
"""
import os, re, shutil, sys

# Find project root
import os as _os
def _find_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while d != "/" and not _os.path.exists(_os.path.join(d, ".git")):
        d = _os.path.dirname(d)
    return d if d != "/" else _os.getcwd()

ROOT = _find_root()
SKILL = ROOT  # template/ is at project root now

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

console = Console()


def banner():
    console.print()
    console.print(Panel.fit(
        "[bold cyan]aigcpass[/] — AIGC 检测报告处理流水线\n\n"
        "这个向导会帮你完成 job 创建、文件检查和 API 配置。\n"
        "完成后你就可以在 Claude Code 中说 '对 job X 执行 aigcpass' 来启动全自动处理。",
        title="欢迎", border_style="cyan"
    ))


def step_header(n, title):
    console.print(f"\n[bold cyan]Step {n}:[/] {title}")


def find_jobs():
    """List existing job directories."""
    jobs_dir = os.path.join(ROOT, "jobs")
    if not os.path.isdir(jobs_dir):
        return []
    return sorted(d for d in os.listdir(jobs_dir)
                  if os.path.isdir(os.path.join(jobs_dir, d)) and not d.startswith("."))


def check_and_show(condition, label, ok="✓", fail="✗"):
    if condition:
        console.print(f"  [green]{ok}[/] {label}")
        return True
    else:
        console.print(f"  [red]{fail}[/] {label}")
        return False


# ─── Step 1: job ────────────────────────────────────────────────────
def step_job(args):
    step_header(1, "选择或创建 job")

    existing = find_jobs()
    if existing:
        console.print(f"  已有 job: [cyan]{', '.join(existing)}[/]")
        if args.get("jobid"):
            jobid = args["jobid"]
            console.print(f"  使用指定的 job: [bold]{jobid}[/]")
        else:
            choice = Prompt.ask("  输入 jobid（或回车选择已存在的 job）",
                                default=existing[0] if existing else "default")
            jobid = choice.strip()
    else:
        if args.get("jobid"):
            jobid = args["jobid"]
        else:
            jobid = Prompt.ask("  输入新 job 的名称", default="default")
        jobid = jobid.strip()

    jobdir = os.path.join(ROOT, "jobs", jobid)
    if not os.path.isdir(jobdir):
        console.print(f"  创建 job 目录: [cyan]jobs/{jobid}/[/]")
        for sub in ["report", "result/stage1", "result/stage2"]:
            os.makedirs(os.path.join(jobdir, sub), exist_ok=True)

    return jobid


# ─── Step 2: files ──────────────────────────────────────────────────
def step_files(jobid):
    step_header(2, "检查必要文件")
    jobdir = os.path.join(ROOT, "jobs", jobid)

    tex = os.path.join(jobdir, "main.tex")
    htmls = []
    report_dir = os.path.join(jobdir, "report")
    if os.path.isdir(report_dir):
        htmls = [f for f in os.listdir(report_dir) if f.endswith(".html")]

    all_ok = True

    if os.path.isfile(tex) and os.path.getsize(tex) > 0:
        check_and_show(True, f"main.tex ({os.path.getsize(tex)} bytes)")
    else:
        check_and_show(False, "main.tex — 缺失")
        console.print(f"    [yellow]请把 LaTeX 源文件放到: {tex}[/]")
        all_ok = False

    if htmls:
        for h in htmls:
            check_and_show(True, f"HTML 报告: {h}")
    else:
        check_and_show(False, "HTML 报告 — 缺失")
        console.print(f"    [yellow]请把 AIGC 检测报告放到: {report_dir}/[/]")
        all_ok = False

    return all_ok


# ─── Step 3: API config ─────────────────────────────────────────────
def step_config(jobid):
    step_header(3, "API 配置")
    jobdir = os.path.join(ROOT, "jobs", jobid)
    api_yaml = os.path.join(jobdir, "api.yaml")
    template = os.path.join(SKILL, "template", "api.yaml.example")

    if os.path.exists(api_yaml):
        with open(api_yaml) as f:
            content = f.read()
        has_key = "YOUR_API_KEY_HERE" not in content and len(re.findall(r'sk-[a-zA-Z0-9]+', content)) > 0
        if has_key:
            check_and_show(True, "api.yaml 已配置")
            return True
        else:
            check_and_show(False, "api.yaml 存在但 API key 未填写")
    else:
        check_and_show(False, "api.yaml 不存在")
        shutil.copy(template, api_yaml)
        console.print(f"    [green]已从模板创建: {api_yaml}[/]")

    console.print()
    console.print("    [yellow]请编辑 api.yaml，填入你的 DeepSeek API key：[/]")
    console.print(f"    [dim]文件位置: {api_yaml}[/]")
    console.print(f"    [dim]申请地址: https://platform.deepseek.com/[/]")
    console.print()
    console.print("    [dim]只需修改 openai.api_key 这一行，其他保持默认即可。[/]")

    if Confirm.ask("   是否现在打开编辑器？", default=True):
        editor = os.environ.get("EDITOR", "nano")
        os.system(f"{editor} {api_yaml}")

    # Verify after edit
    if os.path.exists(api_yaml):
        with open(api_yaml) as f:
            content = f.read()
        if "YOUR_API_KEY_HERE" not in content:
            console.print("    [green]✓ API key 已配置[/]")
            return True

    console.print("    [red]API key 尚未配置，请稍后手动编辑 api.yaml[/]")
    return False


# ─── Step 4: summary ────────────────────────────────────────────────
def step_summary(jobid, files_ok, config_ok):
    step_header(4, "就绪检查")

    jobdir = os.path.join(ROOT, "jobs", jobid)
    table = Table(title="Job 状态总览")
    table.add_column("检查项", style="cyan")
    table.add_column("状态")
    table.add_column("说明")

    # Stage 1 prereqs
    tex = os.path.join(jobdir, "main.tex")
    tex_ok = os.path.isfile(tex) and os.path.getsize(tex) > 0
    table.add_row("main.tex", "✓" if tex_ok else "✗",
                  "就绪" if tex_ok else f"放入 {tex}")

    report_dir = os.path.join(jobdir, "report")
    htmls = [f for f in os.listdir(report_dir) if f.endswith(".html")] if os.path.isdir(report_dir) else []
    table.add_row("HTML 报告", "✓" if htmls else "✗",
                  f"{len(htmls)} 个" if htmls else f"放入 {report_dir}/")

    table.add_row("api.yaml", "✓" if config_ok else "✗",
                  "已配置" if config_ok else "需编辑填入 key")

    # Check if stage1 done
    markers = 0
    if tex_ok:
        with open(tex) as f:
            markers = len(re.findall(r'% AIGC_BEGIN_', f.read()))
    table.add_row("Stage 1 标记", "✓" if markers > 0 else "—",
                  f"{markers} 个片段" if markers > 0 else "未执行")

    opt_txt = os.path.join(jobdir, "report", "AIGC片段优化.txt")
    opt_ok = os.path.exists(opt_txt)
    table.add_row("降重结果", "✓" if opt_ok else "—",
                  "就绪" if opt_ok else "Stage 1 完成后送降重")

    console.print(table)

    if tex_ok and htmls and config_ok:
        console.print()
        if markers == 0:
            console.print("[bold green]✓ 准备就绪！[/] 下一步：")
            console.print(f"  在 Claude Code 中说：[cyan]对 job {jobid} 执行 aigcpass[/]")
        elif not opt_ok:
            console.print("[bold yellow]Stage 1 已完成，等待降重。[/]")
            console.print(f"  将降重结果保存为：[cyan]{opt_txt}[/]")
            console.print(f"  然后说：[cyan]对 job {jobid} 执行 aigcpass[/]")
        else:
            console.print("[bold green]✓ 全部就绪！[/] 下一步：")
            console.print(f"  在 Claude Code 中说：[cyan]对 job {jobid} 执行 aigcpass[/]")
    else:
        console.print()
        console.print("[yellow]上述 ✗ 项需要处理后再继续。[/]")


# ─── main ───────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="aigcpass 交互式设置向导")
    parser.add_argument("--jobid", help="跳过 job 选择，直接使用指定 jobid")
    args = parser.parse_args()

    banner()

    _args = {"jobid": args.jobid} if args.jobid else {}

    # Step 1
    jobid = step_job(_args)

    # Step 2
    files_ok = step_files(jobid)
    if not files_ok:
        console.print()
        console.print("[yellow]请将缺失的文件放入指定位置后重新运行本向导。[/]")
        sys.exit(0)

    # Step 3
    config_ok = step_config(jobid)

    # Step 4
    step_summary(jobid, files_ok, config_ok)


if __name__ == "__main__":
    main()
