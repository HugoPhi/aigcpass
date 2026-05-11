# Stage 2 CSV 审查流程

Stage 2 API 适配完成后，你必须审查每个片段的适配质量。

**审查是你的定性判断，不依赖脚本计算比率来决策。** 可以使用 `diff`、`grep`、Python 辅助计算数值，但最终是否通过的判定由你做出。

---

## 审查标准

适配质量的唯一标准：**API 适配的 LaTeX 变化是否忠实反映了用户降重的文本变化。**

### 核心指标：交集覆盖率

对每个片段，有两个"变化集"：

- **Diff A**：用户降重的变化 = `紫色原文` 与 `优化文本` 的字符级差异
- **Diff B**：API 适配的变化 = `原 LaTeX 片段`（去命令后）与 `修改后 LaTeX 片段`（去命令后）的字符级差异

**判定标准**：Diff B 应与 Diff A 高度重叠。用以下公式量化：

```python
import difflib, re

def strip_latex(t):
    t = re.sub(r'\\begin\{.*?\}.*?\\end\{.*?\}', ' ', t, flags=re.DOTALL)
    t = re.sub(r'\\[a-zA-Z]+(\{[^}]*\})*', ' ', t)
    t = re.sub(r'\\[a-zA-Z]+', ' ', t)
    t = re.sub(r'\$[^$]*\$', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

# Diff A 的幅度
diff_a = 1.0 - difflib.SequenceMatcher(None, purple_text, optimized_text).ratio()

# Diff B 的幅度 = 适配后文本与紫色原文的差异
mod_stripped = strip_latex(modified_latex)
diff_b = 1.0 - difflib.SequenceMatcher(None, purple_text, mod_stripped).ratio()

# 交集覆盖率 = Diff B 对 Diff A 的覆盖
coverage = diff_b / max(diff_a, 0.01)
```

### 判定表

| 状况 | 数值特征 | 判定 | 处理 |
|------|---------|------|------|
| 优质适配 | coverage ≥ 0.6 且结构完整 | 通过 | 无需处理 |
| 部分适配 | coverage 0.2–0.6 | 弱适配 | 你的判断：重跑或接受 |
| 无效适配 | coverage < 0.2 或 diff_b < 0.01 | 失败 | 重跑该片段 |
| 过度修改 | diff_b 远超 diff_a | 有问题 | 检查是否破坏了结构 |

**注意：覆盖率数值是参考，最终判定由你阅读后做出。** 覆盖率偏低但如果阅读发现适配质量可接受，仍然可通过。覆盖率偏高但破坏了 LaTeX 结构，必须标记为失败。

---

## 审查流程

### Step 1: 快速验证（收集数据，不做判定）

```bash
python3 script/xvalidate.py --jobid {jobid}      # 展示 diff 数据
python3 script/diagnose_fragments.py              # 展示段落数匹配
```

把输出当作**信息来源**，不盲从其 PASS/FAIL 结论。

### Step 2: 逐段审查

对每个片段（跳过 `<不用改>`），同时检查：

1. **结构完整性** — `\cite`/`\ref` key 是否保留、`\begin`/`\end` 是否配对、段落数是否一致
2. **措辞替换** — 中文是否按优化文本做了替换（diff 覆盖率）
3. **非紫色保留** — 节标题、首尾句等非降重内容是否未被修改

```bash
python3 aigcpass.py diff --csv jobs/{jobid}/result/stage2/疑似AIGC片段_待确认.csv -t 原片段 修改后片段
```

### Step 3: 计算交集覆盖率

对每个片段计算 coverage，记录数值但不自动判定。

### Step 4: 生成审查报告

```
Stage 2 审查报告

总片段: N  通过: N  弱适配: N  失败: N  跳过: 1

失败片段（需重跑）:
  [ID] 覆盖率=XX% — 描述问题

弱适配片段（你的判断）:
  [ID] 覆盖率=XX% — 你的判断：接受 / 建议重跑

建议操作:
  1. 失败片段: python3 -u script/stage2_api.py --jobid {jobid} --start ID --end ID
  2. 弱适配: 用户判断是否接受
  3. 全部通过后: python3 script/apply_stage2.py --jobid {jobid}
```

### Step 5: 报告用户并等待确认

展示报告，询问用户是否接受。用户确认后 apply。
