---
name: aigcpass
description: |
  End-to-end pipeline for processing AIGC detection reports: extracting
  suspected AIGC fragments from HTML, inserting location markers into LaTeX,
  and adapting optimized text back into LaTeX via LLM API.  Use this skill
  whenever the user wants to run the AIGC detection pipeline, mentions
  "aigcpass", "AIGC 检测", "降重", "执行 stage1", "执行 stage2",
  or asks to process AIGC reports end-to-end.  The skill handles the full
  flow and only pauses to ask the user for missing files.
---

# aigcpass — AIGC 检测报告处理流水线

端到端处理 AIGC 检测报告：提取标记 → 送降重 → 还原到 LaTeX。

## 执行原则

- **自动推进**：每一步完成后自动进入下一步，只在缺少必要文件时停下来引导用户
- **不要跳过检查**：每步的前置条件必须验证通过才能执行
- **失败即停**：脚本返回非零退出码时，读取错误信息报告用户，不要盲目重试
- **jobid 默认 `default`**：除非用户明确指定其他 jobid

## 流程总览

```
  init (创建job) → stage1 (提取标记) → 用户降重 → stage2 (API适配) → 审阅 → apply (应用)
```

---

## Step 0: 确认 job

询问用户 jobid（默认 `default`），检查 `jobs/{jobid}/` 是否存在。

若不存在，引导用户创建：
```bash
python3 aigcpass.py init --jobid {jobid}
```
然后指导用户放入文件：
- `jobs/{jobid}/main.tex` ← LaTeX 源文件
- `jobs/{jobid}/report/*.html` ← AIGC 检测报告

若用户刚执行完 `init`，提醒他们放入文件后再继续。

---

## Step 1: Stage 1 — 提取标记

### 前置检查

```
ls jobs/{jobid}/main.tex            # 必须存在且非空
ls jobs/{jobid}/report/*.html       # 至少一个 .html 文件
```

任一缺失时，告诉用户缺什么、应该放在哪里，然后**停止**。

### 执行

```bash
python3 aigcpass.py stage1 --jobid {jobid}
```

等价于 `python3 script/extract_aigc.py --jobid {jobid}`。

检查输出：
- 所有 23 个标记 ID 连续无缺失（`[verify] All N marker IDs present`）
- 若出现 `[MISS]`，告知用户需要手动添加位置到 `MANUAL_POSITIONS`

### 引导降重

Stage 1 成功后，告诉用户：

```
Stage 1 完成。产物在 result/stage1/。

下一步：将 input_fragments.txt 送降重工具处理（推荐 https://kuaipaper.com/），
降重结果保存为：
  jobs/{jobid}/report/AIGC片段优化.txt

保存后告诉我，我继续执行 Stage 2。
```

---

## Step 2: Stage 2 — API 适配

### 前置检查

```bash
grep -c 'AIGC_BEGIN_' jobs/{jobid}/main.tex    # > 0
ls jobs/{jobid}/result/stage1/疑似AIGC片段.csv   # 存在
ls jobs/{jobid}/report/AIGC片段优化.txt          # 存在（用户刚放入）
```

检查 `result/stage2/main.tex.bak`：若存在且与当前 `main.tex` 不同，**这是污染**——告知用户先恢复：
```bash
cp jobs/{jobid}/result/stage2/main.tex.bak jobs/{jobid}/main.tex
```

### 执行

```bash
python3 aigcpass.py stage2 --jobid {jobid} --concurrency 3
```

脚本自动完成：备份 → API 逐段适配 → 即时验证 → 失败重试 → 输出 CSV。

面板显示每段的 纯文本 diff rate（用户降重幅度）和 适配 diff rate（API 适配幅度）。

### 审阅

```bash
python3 aigcpass.py xvalidate --jobid {jobid}
python3 aigcpass.py diff --csv jobs/{jobid}/result/stage2/疑似AIGC片段_待确认.csv -t 原片段 修改后片段
```

告知用户可以：
- 直接编辑 CSV 中"修改后片段"列来修正不满意的行
- 对单个片段重试：`python3 aigcpass.py stage2 --jobid {jobid} --start N --end N`

### 应用

用户确认后：
```bash
python3 aigcpass.py apply --jobid {jobid}
```

---

## 恢复

任何时候出错需要回退：
```bash
# 恢复到 Stage 1 之前
cp jobs/{jobid}/result/stage1/main.tex.bak jobs/{jobid}/main.tex

# 恢复到 Stage 2 之前
cp jobs/{jobid}/result/stage2/main.tex.bak jobs/{jobid}/main.tex
```

## 配置参考

- API 配置：`config/api.yaml`（需用户自行填写 API key，参考 `config/api.yaml.example`）
- 提示词模板：`prompt/stage2_fitback.md`（LaTeX 保留规则）
- 详细文档：`README.md`
