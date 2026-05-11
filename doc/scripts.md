# 脚本参考

所有脚本位于 `script/`，通过 `python3 script/<name>.py` 调用。
均支持 `--jobid` 参数（默认 `default`）。

---

## extract_aigc.py — Stage 1：提取标记

解析 HTML 报告中的紫色 AIGC 片段，在 `main.tex` 中插入 `% AIGC_BEGIN_{N}` / `% AIGC_END_{N}` 定位标记，
输出 CSV 和降重用 input 文件。

| 参数 | 说明 |
|------|------|
| `--jobid JOBID` | Job ID（默认 `default`） |

**前置条件**：`jobs/{jobid}/main.tex` 存在，`jobs/{jobid}/report/*.html` 存在。

**示例**：
```bash
python3 script/extract_aigc.py --jobid mypaper
```

**产物**（输出到 `jobs/{jobid}/result/stage1/`）：
- `疑似AIGC片段.csv` — 标记ID、AIGC片段、AIGC段落
- `input_fragments.txt` — 送降重（仅紫色文本）
- `input_paragraphs.txt` — 送降重（完整段落上下文）
- `main.tex.bak` — 原始备份

---

## stage2_api.py — Stage 2：API 适配

调用 LLM API 逐段将优化文本适配回 LaTeX，带并发、实时面板、自动验证和重试。

支持多厂商：DeepSeek、Kimi、Qwen、GLM、OpenAI、Claude、Gemini 及任何兼容 OpenAI 格式的自定义平台。

| 参数 | 说明 |
|------|------|
| `--jobid JOBID` | Job ID（默认 `default`） |
| `--concurrency N` | 并发 API 调用数（默认 `3`） |
| `--start N` | 仅处理从 N 开始的片段（断点续传） |
| `--end N` | 仅处理到 N 为止的片段 |
| `--no-dashboard` | 禁用 rich 实时面板（纯文本输出） |
| `--dry-run` | 仅展示面板，不调用 API |

**前置条件**：`main.tex` 含 `AIGC_BEGIN_` 标记，Stage 1 CSV 存在，`AIGC片段优化.txt` 存在，
`jobs/{jobid}/api.yaml` 存在。

**示例**：
```bash
# 完整运行（实时面板）
python3 -u script/stage2_api.py --jobid mypaper --concurrency 3

# 纯文本模式
python3 -u script/stage2_api.py --jobid mypaper --no-dashboard

# 仅重新处理片段 8-12
python3 -u script/stage2_api.py --jobid mypaper --start 8 --end 12
```

**产物**：
- `jobs/{jobid}/result/stage2/疑似AIGC片段_待确认.csv`
- `jobs/{jobid}/result/stage2/main.tex.bak`

---

## apply_stage2.py — 应用修改

读取确认后的 CSV，将"修改后片段"列写入 `main.tex` 对应标记之间。

| 参数 | 说明 |
|------|------|
| `--jobid JOBID` | Job ID（默认 `default`） |

**示例**：
```bash
python3 script/apply_stage2.py --jobid mypaper
```

---

## xvalidate.py — 交叉验证

对比用户降重幅度（Diff A）与 API 适配幅度（Diff B），标记无效适配。

| 参数 | 说明 |
|------|------|
| `--jobid JOBID` | Job ID（默认 `default`） |

**示例**：
```bash
python3 script/xvalidate.py --jobid mypaper
```

**输出**：每个片段的 Diff A、Diff B、状态（OK/FAIL/SKIP）。

---

## diagnose_fragments.py — 段落数诊断

检查 Stage 2 CSV 中每个片段的"原片段"和"修改后片段"段落数是否匹配。

**无参数**（直接读取 `jobs/default/result/stage2/疑似AIGC片段_待确认.csv`）。

**示例**：
```bash
python3 script/diagnose_fragments.py
```

---

## make_input.py — 重建 input 文件

从 Stage 1 CSV 重新生成 `input_fragments.txt` 和 `input_paragraphs.txt`。

| 参数 | 说明 |
|------|------|
| `--jobid JOBID` | Job ID（默认 `default`） |

**示例**：
```bash
python3 script/make_input.py --jobid mypaper
```

---

## fix_fragments.py / fix_zero_change.py — 修复工具

两个辅助脚本，用于修复 Stage 2 CSV 中的常见问题：

- `fix_fragments.py`：修复段落数不匹配的片段（文本被追加而非替换）
- `fix_zero_change.py`：修复适配不充分的片段（0% 词变化）

通常由 Agent 在审查阶段自动调用，用户无需手动运行。
