---
name: stage2
description: |
  Adapts optimized plain text back into LaTeX source using LLM API calls with
  automatic validation and retry.  Use this skill whenever the user mentions
  Stage 2, restoring optimized text to LaTeX, applying de-duplication results,
  or adapting plain text back into marked LaTeX.  Triggers on phrases like
  "执行 stage2", "对 job X 执行 stage2", "还原到 LaTeX", "把优化文本还原",
  or any request to merge optimized text back into marked LaTeX files.
---

# Stage 2: 优化后文本还原到 LaTeX（API 自动适配）

将降重优化后的纯文本还原到 `main.tex` 的对应标记位置。
使用 LLM API 逐段调用 + 自动验证 + 失败重试。

## 前置检查

执行前必须逐一验证。若任一条件不满足，停止并向用户报告缺失项。

```
# 1. main.tex 含标记
grep -c 'AIGC_BEGIN_' jobs/{jobid}/main.tex        # 应 > 0

# 2. Stage 1 CSV 存在
ls jobs/{jobid}/result/stage1/疑似AIGC片段.csv

# 3. 优化文本存在（片段路径或段落路径，二选一）
ls jobs/{jobid}/report/AIGC片段优化.txt            # 片段路径
ls jobs/{jobid}/report/AIGC段落优化.txt            # 段落路径
```

## 备份污染检查

脚本在备份 `main.tex` 前会自动检查已有备份是否与当前文件一致。
若不一致（备份被污染），脚本会终止并提示恢复方法：

```
cp jobs/{jobid}/result/stage2/main.tex.bak jobs/{jobid}/main.tex
```

## 执行

```
python3 -u script/stage2_api.py --jobid {jobid} --concurrency 3
```

或通过统一入口（注意 `aigcpass.py stage2` 会接管终端以显示实时面板）：

```
python3 aigcpass.py stage2 --jobid {jobid} --concurrency 3
```

该脚本自动完成：

1. 备份带标记的 `main.tex` → `result/stage2/main.tex.bak`（含污染检查）
2. 对每个非 `<不用改>` 片段，并发调用 LLM API（默认 3 并发）
3. 每个响应返回后立即验证：段落数、LaTeX 环境配对、`\cite`/`\ref` 完整性、内容变化率
4. 验证失败则附带错误反馈自动重试（最多 3 次，每次升温）
5. 每完成一个片段立即写入 CSV（支持断点续传）
6. 断点续传：已通过的片段不会重复请求

## 面板

脚本启动后显示 `rich` 实时面板。面板展示每个片段的：

| 列 | 含义 |
|----|------|
| 片段 | 标记 ID |
| 状态 | ⏳ 待处理 / 🏃 调用中 / ↩ 重试中 / ✓ 通过 / ✗ 失败 / ── 跳过 |
| 尝试 | 当前尝试 / 最大重试次数 |
| 纯文本 diff rate | 用户降重幅度（原文 vs 优化文本的字符差异率），反映用户改了多少 |
| 适配 diff rate | API 适配幅度（原文 vs 适配后 LaTeX 的差异率，仅对比紫色文本部分），应与纯文本 diff 在同一量级 |
| 说明 | 当前状态或最近一次验证错误 |

## 验证与审阅

```
python3 script/xvalidate.py --jobid {jobid}
python3 aigcpass.py diff --csv jobs/{jobid}/result/stage2/疑似AIGC片段_待确认.csv -t 原片段 修改后片段
```

用户可直接编辑 CSV 中"修改后片段"列来修正不满意的行。

## 应用

```
python3 script/apply_stage2.py --jobid {jobid}
```

## 重新处理特定片段

```
python3 -u script/stage2_api.py --jobid {jobid} --start 8 --end 12
```

已通过的片段会被自动跳过（断点续传）。

## 配置与详细文档

API 配置（模型、温度、重试策略、验证开关）在 `config/api.yaml`。
提示词模板（LaTeX 保留规则）在 `prompt/stage2_fitback.md`。

完整使用说明见 [README.md](../../../README.md) Stage 2 章节。
