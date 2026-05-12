#!/usr/bin/env python3
"""Stage 2 via LLM API — 并发逐段适配，rich 面板实时监控。

Usage:
  python3 -u script/stage2_api.py --jobid default
  python3 -u script/stage2_api.py --jobid default --concurrency 5
  python3 -u script/stage2_api.py --jobid default --start 8 --end 12
"""
import argparse, csv, difflib, json, os, re, sys, time, threading, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.progress import BarColumn, Progress, TextColumn
from rich import box

from _root import ROOT
console = Console()

# Import multi-provider API dispatcher
from providers import call_api

# ─── config ──────────────────────────────────────────────────────────
def load_config(path):
    import yaml
    with open(path) as f:
        raw = f.read()
    return yaml.safe_load(re.sub(r'\$\{(\w+)\}', lambda m: os.environ.get(m.group(1), ""), raw))

# ─── LaTeX helpers ──────────────────────────────────────────────────
def extract_between_markers(tex, marker_id):
    begin = f"% AIGC_BEGIN_{marker_id}"
    end = f"% AIGC_END_{marker_id}"
    bpos = tex.find(begin)
    epos = tex.find(end)
    if bpos < 0 or epos < 0:
        return None
    return tex[tex.find('\n', bpos) + 1:epos].rstrip('\n')

def count_units(text):
    if not text: return 0
    parts = re.split(r'(\n\n)', text.strip())
    return len([p for p in parts if p])

# ─── text diff ─────────────────────────────────────────────────────
def strip_latex(t):
    t = re.sub(r'\\begin\{.*?\}.*?\\end\{.*?\}', ' ', t, flags=re.DOTALL)
    t = re.sub(r'\\[a-zA-Z]+(\{[^}]*\})*', ' ', t)
    t = re.sub(r'\\[a-zA-Z]+', ' ', t)
    t = re.sub(r'\$[^$]*\$', ' ', t)
    t = re.sub(r'\\\(.*?\\\)', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def text_change_ratio(text_a, text_b):
    """Character-level change ratio via SequenceMatcher. Returns 0.0-1.0."""
    if not text_a and not text_b:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(None, text_a, text_b).ratio()


def pure_text_diff_rate(purple_text, optimized_text):
    """How much the user's 降重 changed the purple text (0.0-1.0)."""
    return text_change_ratio(purple_text, optimized_text)


def adapt_diff_rate(original_latex, adapted_latex, purple_text):
    """How much the API changed the AIGC-marked text portions (0.0-1.0).

    Strips LaTeX from both versions, then compares the stripped text
    to the original purple text.  A high rate means the purple-marked
    portions were substantively changed; a rate near 0 means the API
    left the AIGC text untouched.
    """
    stripped = strip_latex(adapted_latex)
    if not stripped or not purple_text:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(None, purple_text, stripped).ratio()

# ─── validation ─────────────────────────────────────────────────────
def validate(original, adapted, cfg, purple_text, optimized_text):
    """Returns (errors, pure_diff_ratio, adapt_diff_ratio)."""
    errors = []
    val = cfg.get("validation", {})

    if val.get("check_paragraph_count", True):
        ou, au = count_units(original), count_units(adapted)
        if ou != au:
            errors.append(f"段落单位数不匹配：原={ou} 适配后={au}")

    if val.get("check_latex_braces", True):
        oe = set(re.findall(r'\\begin\{([^}]+)\}', original))
        ae = set(re.findall(r'\\begin\{([^}]+)\}', adapted))
        if oe != ae:
            if oe - ae: errors.append(f"缺失环境: {', '.join(sorted(oe-ae))}")
            if ae - oe: errors.append(f"多余环境: {', '.join(sorted(ae-oe))}")

    if val.get("check_cite_preserved", True):
        oc = set(re.findall(r'\\cite\{([^}]+)\}', original))
        ac = set(re.findall(r'\\cite\{([^}]+)\}', adapted))
        if oc != ac:
            if oc - ac: errors.append(f"缺失引用: {', '.join(sorted(oc-ac))}")
            if ac - oc: errors.append(f"多余引用: {', '.join(sorted(ac-oc))}")

    if val.get("check_ref_preserved", True):
        oref = set(re.findall(r'\\ref\{([^}]+)\}', original))
        aref = set(re.findall(r'\\ref\{([^}]+)\}', adapted))
        if oref != aref:
            if oref - aref: errors.append(f"缺失ref: {', '.join(sorted(oref-aref))}")
            if aref - oref: errors.append(f"多余ref: {', '.join(sorted(aref-oref))}")

    # Two ratios
    pure_diff = pure_text_diff_rate(purple_text, optimized_text) if purple_text and optimized_text else 0
    adapt_diff = adapt_diff_rate(original, adapted, purple_text)

    if val.get("check_content_changed", True) and adapt_diff < 0.05:
        errors.append(f"适配修改率过低 ({adapt_diff:.0%})，请根据优化文本认真替换措辞")

    return errors, pure_diff, adapt_diff

def clean_response(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:latex|tex)?\s*\n', '', text)
        text = re.sub(r'\n```\s*$', '', text)
    return text.strip()

# ─── fragment job ────────────────────────────────────────────────────
class FragmentJob:
    __slots__ = ('mid', 'original', 'optimized', 'purple_text', 'adapted',
                 'status', 'attempt', 'max_retries', 'last_error',
                 'pure_diff', 'adapt_diff')
    def __init__(self, mid, original, optimized, purple_text, max_retries):
        self.mid = mid
        self.original = original
        self.optimized = optimized
        self.purple_text = purple_text
        self.adapted = None
        self.status = "pending"
        self.attempt = 0
        self.max_retries = max_retries
        self.last_error = ""
        self.pure_diff = 0.0   # 纯文本修改率（用户降重幅度）
        self.adapt_diff = 0.0  # 适配修改率（API 实际修改幅度）

# ─── rich dashboard ──────────────────────────────────────────────────
STATUS_ICON = {
    "pending":  "[dim]⏳[/]",
    "running":  "[bold yellow]🏃[/]",
    "retrying": "[bold magenta]↩[/]",
    "passed":   "[bold green]✓[/]",
    "failed":   "[bold red]✗[/]",
    "skipped":  "[dim]──[/]",
}

def build_dashboard(jobs, concurrency, start_time):
    """Build a rich Table for the dashboard."""
    table = Table(box=box.ROUNDED, expand=True, show_header=True,
                  header_style="bold cyan")
    table.add_column("片段", width=5, style="dim")
    table.add_column("状态", width=8)
    table.add_column("尝试", width=5)
    table.add_column("纯文本diff rate", width=7, style="yellow")
    table.add_column("适配diff rate", width=7, style="green")
    table.add_column("说明", max_width=35)

    sc = {"pending": 0, "running": 0, "retrying": 0, "passed": 0, "failed": 0, "skipped": 0}
    for j in jobs:
        sc[j.status] = sc.get(j.status, 0) + 1

    done = sc["passed"] + sc["failed"] + sc["skipped"]
    total = len(jobs)
    elapsed = time.time() - start_time
    eta = (elapsed / done * (total - done)) if done > 0 else 0

    # Progress bar
    bar_w = 30
    filled = int(bar_w * done / total) if total else 0
    bar = "█" * filled + "░" * (bar_w - filled)

    table.title_style = "bold"  # override rich default italic for titles
    table.title = (
        f"Stage 2 fitback process : "
        f"[{bar}] {done}/{total} | "
        f"并发:[cyan]{concurrency}[/] | "
        f"通过:[green]{sc['passed']}[/] 重试:[magenta]{sc['retrying']}[/] "
        f"失败:[red]{sc['failed']}[/] 待处理:[dim]{sc['pending']}[/] | "
        f"耗时:[yellow]{elapsed:.0f}s[/] 剩余:[yellow]{eta:.0f}s[/]"
    )

    for j in jobs:
        icon = STATUS_ICON.get(j.status, "  ")
        attempt_str = f"{j.attempt}/{j.max_retries}" if j.status not in ("pending", "skipped") else "-"
        pure_str = f"{j.pure_diff:4.0%}" if j.pure_diff > 0 else "  -"
        adapt_str = f"{j.adapt_diff:4.0%}" if j.adapt_diff > 0 else "  -"

        detail = j.last_error[:40] if j.last_error else ""
        if j.status == "running":
            detail = "调用 API 中..."
        elif j.status == "passed":
            detail = "通过"
        elif j.status == "skipped":
            detail = "<不用改>"
        elif j.status == "failed":
            detail = "使用原片段"

        table.add_row(j.mid, icon, attempt_str, pure_str, adapt_str, detail)

    return table

# ─── main ───────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobid", default="default")
    parser.add_argument("--config", default=None, help="api.yaml path (默认: jobs/{jobid}/api.yaml)")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=999)
    parser.add_argument("--no-dashboard", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="仅展示面板，不调用 API")
    args = parser.parse_args()

    # Default config: per-job api.yaml
    if args.config is None:
        args.config = os.path.join(ROOT, "jobs", args.jobid, "api.yaml")
    if not os.path.exists(args.config):
        template = os.path.join(os.path.dirname(__file__), "..", "template", "api.yaml.example")
        console.print(f"[red]ERROR:[/] {args.config} 不存在")
        console.print(f"  请从模板创建: cp {template} {args.config}")
        console.print(f"  然后编辑填入 API key")
        sys.exit(1)

    cfg = load_config(args.config)
    JOB = os.path.join(ROOT, "jobs", args.jobid)
    TEX = os.path.join(JOB, "main.tex")
    CSV_IN = os.path.join(JOB, "result", "stage1", "疑似AIGC片段.csv")
    CSV_OUT = os.path.join(JOB, "result", "stage2", "疑似AIGC片段_待确认.csv")
    OPT_TXT = os.path.join(JOB, "report", "AIGC片段优化.txt")

    for f, desc in [(TEX, "main.tex"), (CSV_IN, "Stage 1 CSV"), (OPT_TXT, "优化文本")]:
        if not os.path.exists(f):
            console.print(f"[red]ERROR:[/] {desc} 不存在: {f}")
            sys.exit(1)

    # Read prompt template
    PROMPT = os.path.join(os.path.dirname(__file__), "..", "prompt", "stage2_fitback.md")
    with open(PROMPT, encoding="utf-8") as f:
        template = f.read()
    system_prompt = template.split("## 原片段", 1)[0].strip()

    # Read data
    with open(TEX, encoding="utf-8") as f:
        tex = f.read()
    with open(CSV_IN, encoding="utf-8-sig") as f:
        in_rows = list(csv.reader(f))
    with open(OPT_TXT, encoding="utf-8") as f:
        opt_parts = [p.strip() for p in f.read().split("\n\n\n") if p.strip()]

    INP_TXT = os.path.join(JOB, "result", "stage1", "input_fragments.txt")
    with open(INP_TXT, encoding="utf-8") as f:
        inp_parts = [p.strip() for p in f.read().split("\n\n\n") if p.strip()]

    # ─── backup with pollution check ─────────────────────────────────
    bak = os.path.join(JOB, "result", "stage2", "main.tex.bak")
    os.makedirs(os.path.dirname(bak), exist_ok=True)
    if os.path.exists(bak):
        with open(bak, encoding="utf-8") as f:
            if f.read() != tex:
                console.print(f"[red]ERROR:[/] {bak} 已被污染（与当前 main.tex 不同）")
                console.print(f"  请先恢复: [cyan]cp {bak} {TEX}[/]")
                sys.exit(1)
    with open(bak, "w", encoding="utf-8") as f:
        f.write(tex)

    # Load existing results (resume)
    existing = {}
    if os.path.exists(CSV_OUT):
        with open(CSV_OUT, encoding="utf-8-sig") as f:
            for r in list(csv.reader(f))[1:]:
                if len(r) >= 5 and r[4].strip():
                    existing[r[0]] = r

    max_retries = cfg.get("retry", {}).get("max_retries", 3)
    temp_delta = cfg.get("retry", {}).get("temperature_delta", 0.1)
    base_temp = cfg["api"]["temperature"]

    # Build jobs
    jobs = []
    for row in in_rows[1:]:
        mid = int(row[0])
        if mid < args.start or mid > args.end:
            continue
        opt = opt_parts[mid - 1] if mid - 1 < len(opt_parts) else ""
        pt = inp_parts[mid - 1] if mid - 1 < len(inp_parts) else ""
        original = extract_between_markers(tex, str(mid))

        if original is None:
            console.print(f"  [{mid:2d}] MARKER NOT FOUND — skipped")
            continue

        job = FragmentJob(str(mid), original, opt, pt, max_retries)

        # Pre-compute pure text diff (known before API call)
        job.pure_diff = pure_text_diff_rate(pt, opt) if pt and opt else 0

        # Resume check
        if str(mid) in existing:
            prev = existing[str(mid)][4]
            errs, _, adapt_d = validate(original, prev, cfg, pt, opt)
            if not errs:
                job.adapted = prev
                job.status = "passed"
                job.attempt = 1
                job.adapt_diff = adapt_d

        if "<不用改>" in opt:
            job.adapted = original
            job.status = "skipped"

        jobs.append(job)

    # ─── helpers inside main scope ───────────────────────────────────
    status_lock = threading.Lock()

    def update_job(job, **kw):
        with status_lock:
            for k, v in kw.items():
                setattr(job, k, v)

    def write_csv():
        header = in_rows[0] + ["原片段", "修改后片段"]
        out_rows = [header]
        for row in in_rows[1:]:
            mid = row[0]
            job = next((j for j in jobs if j.mid == mid), None)
            if job and job.adapted:
                out_rows.append(row + [job.original, job.adapted])
            elif mid in existing:
                out_rows.append(existing[mid])
            else:
                out_rows.append(row + ["", ""])
        os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)
        with open(CSV_OUT, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerows(out_rows)

    # ─── worker ──────────────────────────────────────────────────────
    def adapt_one(job):
        if job.status in ("passed", "skipped"):
            return True

        if args.dry_run:
            job.adapt_diff = job.pure_diff * 0.7  # simulated
            update_job(job, status="passed", attempt=1, adapted=job.original, adapt_diff=job.adapt_diff)
            write_csv()
            return True

        update_job(job, status="running", attempt=1, last_error="")

        for attempt in range(1, max_retries + 2):
            temp = base_temp + (attempt - 1) * temp_delta
            update_job(job, status=("retrying" if attempt > 1 else "running"),
                       attempt=attempt, last_error="")

            try:
                if attempt == 1:
                    user_prompt = template
                    user_prompt = user_prompt.replace("{original_fragment}", job.original)
                    user_prompt = user_prompt.replace("{purple_text}", job.purple_text)
                    user_prompt = user_prompt.replace("{optimized_text}", job.optimized)
                    # Strip system prompt part
                    if "## 原片段" in user_prompt:
                        user_prompt = "## 原片段" + user_prompt.split("## 原片段", 1)[1]
                else:
                    err_fb = "\n".join(f"- {e}" for e in job.last_error.split("\n") if e)
                    user_prompt = template
                    user_prompt = user_prompt.replace("{original_fragment}", job.original)
                    user_prompt = user_prompt.replace("{purple_text}", job.purple_text)
                    user_prompt = user_prompt.replace("{optimized_text}", job.optimized)
                    if "## 原片段" in user_prompt:
                        user_prompt = "## 原片段" + user_prompt.split("## 原片段", 1)[1]
                    user_prompt += f"\n\n## 上一次输出验证失败\n\n{err_fb}\n\n请重新输出："

                adapted_raw = call_api(cfg, system_prompt, user_prompt, temp)
                adapted = clean_response(adapted_raw)
                errors, pure_d, adapt_d = validate(job.original, adapted, cfg, job.purple_text, job.optimized)

                if not errors:
                    update_job(job, status="passed", attempt=attempt, last_error="",
                              adapted=adapted, adapt_diff=adapt_d)
                    write_csv()
                    return True
                else:
                    update_job(job, status="retrying", attempt=attempt,
                              last_error="; ".join(errors)[:80])

            except Exception as e:
                update_job(job, status="retrying", attempt=attempt, last_error=str(e)[:80])
                time.sleep(2 ** attempt)

        update_job(job, status="failed", attempt=max_retries + 1,
                   last_error="全部尝试失败，使用原片段", adapted=job.original, adapt_diff=0)
        write_csv()
        return False

    # ─── Run ─────────────────────────────────────────────────────────
    pending = [j for j in jobs if j.status == "pending"]

    start_time = time.time()
    if args.no_dashboard:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            list(pool.map(adapt_one, pending))
    else:
        with Live(build_dashboard(jobs, args.concurrency, start_time),
                  refresh_per_second=3, console=console) as live:
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                futures = {pool.submit(adapt_one, j): j for j in pending}
                while any(not f.done() for f in futures):
                    live.update(build_dashboard(jobs, args.concurrency, start_time))
                    time.sleep(0.3)
                live.update(build_dashboard(jobs, args.concurrency, start_time))
            for f in as_completed(futures):
                try: f.result()
                except Exception as e: console.print(f"[red]Worker error:[/] {e}")

    write_csv()

    # Summary
    passed = sum(1 for j in jobs if j.status == "passed")
    failed = sum(1 for j in jobs if j.status == "failed")
    skipped = sum(1 for j in jobs if j.status == "skipped")
    elapsed = time.time() - start_time

    console.print(f"\n[bold]完成:[/] {len(jobs)} 片段 | 耗时: {elapsed:.0f}s")
    console.print(f"  通过: [green]{passed}[/] | 失败: [red]{failed}[/] | 跳过: [dim]{skipped}[/]")
    console.print(f"\n[bold]输出:[/] {CSV_OUT}")
    console.print(f"\n[bold]审阅:[/]")
    console.print(f"  [cyan]python3 aigcpass.py diff --csv {CSV_OUT} -t 原片段 修改后片段[/]")
    console.print(f"  [cyan]python3 script/xvalidate.py --jobid {args.jobid}[/]")
    console.print(f"\n[bold]应用:[/]")
    console.print(f"  [cyan]python3 script/apply_stage2.py --jobid {args.jobid}[/]")


if __name__ == "__main__":
    main()
