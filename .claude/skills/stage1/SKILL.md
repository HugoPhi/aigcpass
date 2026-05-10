---
name: stage1
description: |
  Extracts suspected AIGC fragments from HTML detection reports and inserts
  location markers into LaTeX source files.  Use this skill whenever the user
  mentions Stage 1, extracting AIGC fragments, inserting markers, processing
  HTML reports, or preparing LaTeX for AIGC de-duplication.  Triggers on
  phrases like "执行 stage1", "对 job X 执行 stage1", "提取 AIGC 片段",
  "标记疑似 AIGC", or any request to analyze AIGC detection HTML reports.
---

# Stage 1: 疑似 AIGC 片段提取与标记

从 AIGC 检测系统导出的 HTML 统计报告中提取紫色标记的疑似 AIGC 文本，
在 LaTeX 源文件中插入 `% AIGC_BEGIN_{N}` / `% AIGC_END_{N}` 定位标记，
输出结构化 CSV 和降重用 input 文件。

## 前置检查

执行前必须逐一验证。若任一条件不满足，停止并向用户报告缺失项。

```
ls -la jobs/{jobid}/main.tex            # 文件存在且大小 > 0
ls jobs/{jobid}/report/*.html           # 至少一个 .html 文件
```

## 执行

运行提取脚本：

```
python3 script/extract_aigc.py --jobid {jobid}
```

或通过统一入口：

```
python3 aigcpass.py stage1 --jobid {jobid}
```

该脚本自动完成：

1. 从 HTML 中解析紫色片段（通常由 `<a class="cl3">` 标记）
2. 在 `main.tex` 中定位紫色文本并插入标记（标记独占一行，按段落边界扩展）
3. 提取完整 LaTeX 段落并清洗为纯文本（图表→`<类型: label>`，公式→`<公式>`，`\cite{key}`→`[key]`）
4. 输出 CSV 和 input 文件到 `result/stage1/`
5. 备份原始 `main.tex` → `result/stage1/main.tex.bak`

## 验证

脚本运行后确认：

```
grep -c 'AIGC_BEGIN_' jobs/{jobid}/main.tex    # 应 = 23（本项目的片段数）
ls jobs/{jobid}/result/stage1/疑似AIGC片段.csv   # 存在
ls jobs/{jobid}/result/stage1/input_fragments.txt # 存在
```

所有标记 ID 连续无缺失，每个标记在单独一行。

## 产物

| 文件 | 说明 |
|------|------|
| `疑似AIGC片段.csv` | 标记ID、AIGC片段（紫色文本）、AIGC段落（完整上下文） |
| `input_fragments.txt` | 每行一个 AIGC片段，双空行分隔，送降重 |
| `input_paragraphs.txt` | 每行一个 AIGC段落，双空行分隔，送降重 |
| `main.tex.bak` | 原始 LaTeX 备份 |

## 缺少标记时的处理

若自动匹配遗漏了某些片段（输出 `[MISS]`），需要将手动验证的 (start_line, start_col, end_line, end_col)
位置添加到 `script/extract_aigc.py` 的 `MANUAL_POSITIONS` 字典中，然后恢复 `main.tex` 并重新运行。
