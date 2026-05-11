#!/usr/bin/env python3
"""Interactive setup wizard for aigcpass.

Guides the user through:
  1. Creating/finding a job directory
  2. Verifying main.tex and HTML report are in place
  3. Selecting an LLM provider and configuring api.yaml
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
SKILL = ROOT

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint
from rich.prompt import Prompt, Confirm, IntPrompt

console = Console()

# Try to import questionary for better UX; fall back to rich prompts
try:
    import questionary
    _HAS_QUESTIONARY = True
except ImportError:
    _HAS_QUESTIONARY = False

# Import provider registry
sys.path.insert(0, os.path.join(ROOT, "script"))
from providers import PROVIDERS, list_providers, get_provider


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


# ─── Provider Selection Helper ──────────────────────────────────────
def _select_provider_interactive():
    """Let user select a provider from the registry. Returns provider key."""
    keys = list_providers()

    if _HAS_QUESTIONARY:
        choices = [
            questionary.Choice(
                title=f"{p['name']:24s}  [{p['type']:10s}]  推荐: {p['models'][0]}",
                value=k,
            )
            for k in keys
        ]
        choices.append(questionary.Separator())
        choices.append(questionary.Choice("自定义 / Other", value="custom"))

        selected = questionary.select(
            "请选择 LLM 服务商:",
            choices=choices,
            use_arrow_keys=True,
            instruction="\n  使用 ↑↓ 选择，回车确认",
        ).ask()
    else:
        console.print("\n[bold]可选服务商:[/]")
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("编号", width=4, justify="right")
        table.add_column("服务商", width=22)
        table.add_column("协议", width=10)
        table.add_column("推荐模型")
        for i, k in enumerate(keys, 1):
            p = PROVIDERS[k]
            table.add_row(str(i), p["name"], p["type"], p["models"][0])
        table.add_row(str(len(keys)+1), "自定义 / Other", "-", "手动输入")
        console.print(table)

        idx = IntPrompt.ask("  选择编号", default=1)
        if 1 <= idx <= len(keys):
            selected = keys[idx - 1]
        else:
            selected = "custom"

    return selected


def _select_model_interactive(provider_key, provider_meta):
    """Let user select or enter a model. Returns model string."""
    models = provider_meta["models"]

    if _HAS_QUESTIONARY:
        choices = [questionary.Choice(m, value=m) for m in models]
        choices.append(questionary.Separator())
        choices.append(questionary.Choice("其他（手动输入）", value="__custom__"))

        selected = questionary.select(
            f"请选择 {provider_meta['name']} 的模型:",
            choices=choices,
            use_arrow_keys=True,
        ).ask()

        if selected == "__custom__":
            selected = questionary.text("输入模型 ID:").ask()
    else:
        console.print(f"\n  [bold]{provider_meta['name']} 推荐模型:[/]")
        for i, m in enumerate(models, 1):
            console.print(f"    [{i}] {m}")
        console.print(f"    [{len(models)+1}] 其他（手动输入）")

        idx = IntPrompt.ask("  选择编号", default=1)
        if 1 <= idx <= len(models):
            selected = models[idx - 1]
        else:
            selected = Prompt.ask("  输入模型 ID", default=models[0])

    return selected


# ─── Step 3: API config ─────────────────────────────────────────────
def step_config(jobid):
    step_header(3, "API 配置")
    jobdir = os.path.join(ROOT, "jobs", jobid)
    api_yaml = os.path.join(jobdir, "api.yaml")

    # If already configured and valid, offer to keep or reconfigure
    existing_cfg = None
    if os.path.exists(api_yaml):
        try:
            import yaml
            with open(api_yaml) as f:
                existing_cfg = yaml.safe_load(f.read())
        except Exception:
            existing_cfg = None

        if existing_cfg and existing_cfg.get("api", {}).get("api_key"):
            old_key = existing_cfg["api"].get("provider", "unknown")
            if Confirm.ask(f"  检测到已配置的 API ({old_key})，是否重新配置?", default=False):
                pass  # continue to reconfigure
            else:
                check_and_show(True, "api.yaml 已配置（保留现有）")
                return True

    # ── Provider selection ──────────────────────────────────────────
    selected_provider = _select_provider_interactive()

    if selected_provider == "custom":
        # Custom provider: ask for everything manually
        console.print("\n[bold yellow]自定义厂商配置[/]")
        custom_type = Prompt.ask(
            "  适配器类型",
            choices=["openai", "anthropic", "gemini"],
            default="openai"
        )
        custom_name = Prompt.ask("  厂商名称（用于显示）", default="custom")
        custom_base = Prompt.ask("  API base URL")
        custom_models = Prompt.ask("  推荐模型（逗号分隔）", default="gpt-4o")
        custom_models = [m.strip() for m in custom_models.split(",") if m.strip()]

        provider_meta = {
            "name": custom_name,
            "type": custom_type,
            "base_url": custom_base,
            "models": custom_models,
            "key_hint": "请从对应平台获取",
            "docs_url": "",
        }
        provider_key = "custom"
    else:
        provider_meta = get_provider(selected_provider)
        provider_key = selected_provider

    console.print(f"\n[bold]已选择:[/] [cyan]{provider_meta['name']}[/]  ({provider_meta['type']} 协议)")
    console.print(f"  文档: [dim]{provider_meta['docs_url']}[/]")

    # ── Model selection ─────────────────────────────────────────────
    model = _select_model_interactive(provider_key, provider_meta)
    console.print(f"  模型: [cyan]{model}[/]")

    # ── API key ─────────────────────────────────────────────────────
    console.print(f"\n  [yellow]请从以下地址获取 API key:[/]")
    console.print(f"    {provider_meta['key_hint']}")

    if _HAS_QUESTIONARY:
        api_key = questionary.password("  输入 API key:").ask()
    else:
        api_key = Prompt.ask("  输入 API key", password=True)

    if not api_key or api_key.strip() == "":
        console.print("    [red]API key 为空，请稍后手动编辑 api.yaml[/]")
        api_key = "YOUR_API_KEY_HERE"

    # ── Base URL override ───────────────────────────────────────────
    default_base = provider_meta["base_url"]
    if _HAS_QUESTIONARY:
        if questionary.confirm(f"使用默认 endpoint?\n  {default_base}", default=True).ask():
            base_url = default_base
        else:
            base_url = questionary.text("输入自定义 endpoint:", default=default_base).ask()
    else:
        if Confirm.ask(f"  使用默认 endpoint? ({default_base})", default=True):
            base_url = default_base
        else:
            base_url = Prompt.ask("  输入自定义 endpoint", default=default_base)

    # ── Parameters ──────────────────────────────────────────────────
    console.print("\n[bold]生成参数[/]")
    temp = float(Prompt.ask("  temperature", default="0.3"))
    max_tok = int(Prompt.ask("  max_tokens", default="8192"))

    # ── Write api.yaml ──────────────────────────────────────────────
    cfg = {
        "api": {
            "provider": provider_key,
            "type": provider_meta["type"],
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
            "temperature": temp,
            "max_tokens": max_tok,
        },
        "retry": {
            "max_retries": 3,
            "temperature_delta": 0.1,
        },
        "validation": {
            "check_paragraph_count": True,
            "check_latex_braces": True,
            "check_cite_preserved": True,
            "check_ref_preserved": True,
            "check_content_changed": True,
        },
    }

    import yaml
    with open(api_yaml, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    console.print(f"\n  [green]✓ 配置已保存:[/] {api_yaml}")
    return True


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

    # Show provider info if available
    api_yaml = os.path.join(jobdir, "api.yaml")
    if os.path.exists(api_yaml):
        try:
            import yaml
            with open(api_yaml) as f:
                cfg = yaml.safe_load(f.read())
            prov = cfg.get("api", {}).get("provider", "-")
            model = cfg.get("api", {}).get("model", "-")
            table.add_row("服务商", "", f"{prov} / {model}")
        except Exception:
            pass

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
