---
name: aigcpass
description: |
  End-to-end automated pipeline for processing AIGC detection reports.
  The Agent orchestrates the flow: checks prerequisites, runs batch scripts,
  validates outputs, reviews results.  Interactive commands (setup wizard,
  live dashboard) are guided by the Agent but executed by the user.
  Trigger on any mention of: aigcpass, AIGC detection, AIGC 检测, 降重,
  stage1, stage2, processing AIGC reports, extracting AIGC fragments,
  adapting text back to LaTeX.
---

# aigcpass — 全自动 AIGC 检测报告处理

你是流程的**编排者**，不是所有命令的执行者。区分清楚什么你来跑、什么让用户跑。

## 谁会跑什么命令

| 类型 | 谁来跑 | 例子 |
|------|--------|------|
| 交互式命令（需要终端输入/实时面板） | **用户跑** | `stage2_api.py`（带面板） |
| 批处理命令（无交互、可后台运行） | **你跑** | `extract_aigc.py`、`apply_stage2.py`、`xvalidate.py` |
| 文件检查（grep/ls/diff） | **你跑** | 所有前置检查和验证 |

**规则**：如果一个命令会 `os.execv` 接管终端、或需要用户输入、或启动 TUI（如 `less`/`icdiff`），你必须**引导用户执行**而不是自己跑。其他纯批处理脚本你直接跑。

## 路径约定

aigcpass 默认安装在 `~/.claude/skills/aigcpass/`。以下所有命令均基于该路径。
如果用户告知了其他安装路径，请使用用户提供的绝对路径。

首次使用时检测路径是否存在：

```bash
[ -d ~/.claude/skills/aigcpass ] && echo "FOUND" || echo "NOT FOUND"
```

如果不存在，询问用户安装位置并记住该路径用于后续所有步骤。

脚本路径：`~/.claude/skills/aigcpass/script/`。所有脚本支持 `--jobid`，默认 `default`。

对于需要读取的参考文档（如 `~/.claude/skills/aigcpass/doc/check_fragments.md`），其完整路径为 `~/.claude/skills/aigcpass/doc/check_fragments.md`。

---

## Step 1: 确认 job 和配置

### 1.1 检查必要文件

你自己跑这些检查：

```bash
ls ~/.claude/skills/aigcpass/jobs/{jobid}/main.tex && ls ~/.claude/skills/aigcpass/jobs/{jobid}/report/*.html
```

如果文件缺失，停下来告诉用户缺什么、如何补充。

### 1.2 检查/创建 api.yaml

检查 `~/.claude/skills/aigcpass/jobs/{jobid}/api.yaml` 是否存在且包含有效的 `api_key`。

如果已存在且有效，询问用户是否重新配置。如果不存在或无效，直接进入询问流程。

**按以下顺序询问用户：**

**问题 1：选择服务商**

向用户展示以下服务商列表，让用户选择：

| 服务商 | 协议 | 默认 endpoint | 推荐模型 |
|--------|------|---------------|---------|
| **DeepSeek** | openai | `https://api.deepseek.com/v1/chat/completions` | `deepseek-v4-pro` |
| **Kimi (月之暗面)** | openai | `https://api.moonshot.cn/v1/chat/completions` | `kimi-k2.6` |
| **Qwen (阿里云)** | openai | `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions` | `qwen-plus` |
| **GLM (智谱AI)** | openai | `https://open.bigmodel.cn/api/paas/v4/chat/completions` | `glm-5.1` |
| **OpenAI** | openai | `https://api.openai.com/v1/chat/completions` | `gpt-4.1` |
| **Claude (Anthropic)** | anthropic | `https://api.anthropic.com/v1/messages` | `claude-opus-4-7` |
| **Gemini (Google)** | gemini | `https://generativelanguage.googleapis.com/v1beta/models` | `gemini-2.5-pro` |
| **自定义** | - | 手动输入 | 手动输入 |

**问题 2：选择模型**

从该服务商的推荐模型中让用户选择，或让用户手动输入模型 ID。

**问题 3：输入 API key**

请用户提供 API key。获得 key 后**不要在对话中回显或保存**，只用于写入文件。

**问题 4：确认 endpoint**

使用上表中的默认 endpoint。询问用户是否需要修改为自定义 endpoint。

**问题 5：调整生成参数（可选）**

- temperature（默认 0.3，建议范围 0.2–0.5）
- max_tokens（默认 8192）

如果用户不指定，使用默认值。

如果用户选择了"自定义"服务商，额外询问：
- 适配器类型（`openai` / `anthropic` / `gemini`）
- 厂商名称（用于显示）
- API endpoint
- 模型 ID

### 1.3 写入 api.yaml

根据用户回答，使用 Write 工具直接写入 `~/.claude/skills/aigcpass/jobs/{jobid}/api.yaml`：

```yaml
api:
  provider: "{provider_key}"
  type: "{adapter_type}"
  base_url: "{base_url}"
  api_key: "{api_key}"
  model: "{model}"
  temperature: {temperature}
  max_tokens: {max_tokens}

retry:
  max_retries: 3
  temperature_delta: 0.1

validation:
  check_paragraph_count: true
  check_latex_braces: true
  check_cite_preserved: true
  check_ref_preserved: true
  check_content_changed: true
```

**重要**：
- API key 只写入文件，不要在对话中展示、保存到 memory 或保留在上下文中
- 如果用户选择环境变量方式（`${VAR_NAME}`），在 `api_key` 字段写入该语法，并提醒用户设置对应环境变量
- 写入完成后告诉用户配置已保存

详细配置指导见 `~/.claude/skills/aigcpass/doc/configure.md`。

---

## Step 2: Stage 1 — 提取标记

全部由**你执行**。

### 前置检查

```bash
ls ~/.claude/skills/aigcpass/jobs/{jobid}/main.tex && ls ~/.claude/skills/aigcpass/jobs/{jobid}/report/*.html
```

### 跳过条件

```bash
grep -c 'AIGC_BEGIN_' ~/.claude/skills/aigcpass/jobs/{jobid}/main.tex   # > 0 → 已完成，跳到 Step 3
```

### 执行

```bash
cd ~/.claude/skills/aigcpass && python3 script/extract_aigc.py --jobid {jobid}
```

### 验证

- 输出含 `[verify] All N marker IDs present`
- 无 `[MISS]` 行（若有，添加位置到 `MANUAL_POSITIONS`，恢复 main.tex 重新运行）

### 片段完整性审查

标记插入后，读取 `~/.claude/skills/aigcpass/doc/check_fragments.md`，按其中的流程审查每个提取的紫色片段：

1. 是否跨段落边界（跨空行 = 异常）
2. 头尾是否完整（句子截断可接受，跨段不可接受）
3. 是否混入了非紫色内容（节标题、图表标题等）

生成审查报告展示给用户。如有跨段落渗入，需调整标记边界并重新运行。

### 引导降重

**停下来**告诉用户：

```
Stage 1 完成。产物在 ~/.claude/skills/aigcpass/jobs/{jobid}/result/stage1/。

请将 input_fragments.txt 送降重工具处理（推荐 https://kuaipaper.com/）。
降重结果保存为：
  ~/.claude/skills/aigcpass/jobs/{jobid}/report/AIGC片段优化.txt

完成后告诉我，我继续。
```

---

## Step 2.5: 降重文本审查

用户把 `AIGC片段优化.txt` 放入后，**在 Stage 2 前**你必须审查降重文本质量。

读取 `~/.claude/skills/aigcpass/doc/check_optimization.md`，按其中的 6 类检查逐段审查：
1. "十分xxx"类程度副词
2. 堆叠的形容词/副词
3. 顿号连接的近义形容词
4. 语气词"吧"
5. "自然""妥帖""毋庸"等文学化词语
6. 小括号补充说明（例子可接受）

生成审查报告展示给用户，**停下来等用户修改**。用户确认后进入 Step 3。

---

## Step 3: Stage 2 — API 适配

前置检查和污染检查由**你执行**。适配脚本本身**让用户跑**（需要终端显示实时面板）。

### 3.1 前置检查（你执行）

```bash
grep -c 'AIGC_BEGIN_' ~/.claude/skills/aigcpass/jobs/{jobid}/main.tex
ls ~/.claude/skills/aigcpass/jobs/{jobid}/result/stage1/疑似AIGC片段.csv
ls ~/.claude/skills/aigcpass/jobs/{jobid}/report/AIGC片段优化.txt
```

缺什么停什么。

### 3.2 污染检查（你执行）

```bash
diff ~/.claude/skills/aigcpass/jobs/{jobid}/main.tex ~/.claude/skills/aigcpass/jobs/{jobid}/result/stage2/main.tex.bak 2>/dev/null
```

若不同，告知用户恢复后再继续。

### 3.3 执行（引导用户跑）

**告诉用户自己执行**（这个命令需要终端显示 rich 实时面板）：

```
前置检查通过。请运行以下命令启动 Stage 2 适配：

  cd ~/.claude/skills/aigcpass && python3 -u script/stage2_api.py --jobid {jobid} --concurrency 3

运行完成后告诉我，我来审查结果。
```

### 3.4 审查（你执行）

审查是**你的定性判断**——脚本提供数据，你做出判定。不要调用脚本自动化决策。

读取 `~/.claude/skills/aigcpass/doc/check_stage2_csv.md`，按其中的流程：

1. 运行 `xvalidate.py` 和 `diagnose_fragments.py` 获取数据（不做判定）
2. 对每个片段计算**交集覆盖率**：`Diff B（紫色原文 vs 适配后文本）/ Diff A（紫色原文 vs 优化文本）`。覆盖率 ≥ 0.6 且结构完整为优质适配
3. 用 `icdiff` 逐段对比原片段和修改后片段
4. 生成审查报告展示给用户

**审查原则**：覆盖率是参考，最终判定由你阅读后做出。过度修改比修改不足更危险。

### 3.5 重新适配（引导用户跑）

如果有失败或弱适配片段：

```
以下片段需要重新适配：
  [ID] 原因

请运行：
  cd ~/.claude/skills/aigcpass && python3 -u script/stage2_api.py --jobid {jobid} --start N --end N
```

### 3.6 应用（你执行）

用户确认后：

```bash
cd ~/.claude/skills/aigcpass && python3 script/apply_stage2.py --jobid {jobid}
```

---

## 恢复（你执行）

```bash
cp ~/.claude/skills/aigcpass/jobs/{jobid}/result/stage1/main.tex.bak ~/.claude/skills/aigcpass/jobs/{jobid}/main.tex   # 回 Stage 1 前
cp ~/.claude/skills/aigcpass/jobs/{jobid}/result/stage2/main.tex.bak ~/.claude/skills/aigcpass/jobs/{jobid}/main.tex   # 回 Stage 2 前
```

## 参考文档

| 文档 | 何时阅读 |
|------|---------|
| `~/.claude/skills/aigcpass/doc/scripts.md` | 所有脚本的参数说明和用法示例 |
| `~/.claude/skills/aigcpass/doc/check_fragments.md` | Stage 1 后审查紫色片段完整性 |
| `~/.claude/skills/aigcpass/doc/check_optimization.md` | 降重后审查优化文本的不规范用语 |
| `~/.claude/skills/aigcpass/doc/check_stage2_csv.md` | Stage 2 后审查适配质量（交集覆盖率标准） |
| `~/.claude/skills/aigcpass/doc/configure.md` | API 配置详细指导 |
| `~/.claude/skills/aigcpass/template/api.yaml.example` | 每 job 的 API 配置模板 |
| `~/.claude/skills/aigcpass/prompt/stage2_fitback.md` | LLM 适配提示词模板（LaTeX 保留规则） |
