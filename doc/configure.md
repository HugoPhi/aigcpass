# API 配置指南

aigcpass 的 Stage 2 需要调用 LLM API 将降重后的纯文本适配回 LaTeX。本文档说明如何配置 API。

## 快速配置（Agent 模式）

使用 aigcpass Skill 时，Agent 会在 Step 1 直接询问你以下信息并自动生成 `api.yaml`：

1. **选择服务商** — 从列表中选择（DeepSeek / Kimi / Qwen / GLM / OpenAI / Claude / Gemini / 自定义）
2. **选择模型** — 从该服务商的推荐模型中选择，或手动输入
3. **输入 API key** — Agent 获得后直接写入文件，不在对话中展示
4. **确认 endpoint** — 默认已填好，通常不需要改
5. **调整生成参数** — temperature（默认 0.3）、max_tokens（默认 8192）

完成后配置自动写入 `jobs/{jobid}/api.yaml`（相对于 skill 根目录）。

## 手动配置（纯 CLI 模式）

如果你不使用 Agent，手动复制模板并编辑：

```bash
cp ~/.claude/skills/aigcpass/template/api.yaml.example ~/.claude/skills/aigcpass/jobs/{jobid}/api.yaml
# 编辑 api.yaml 填入 provider、type、base_url、api_key、model 等参数
```

---

## 支持的服务商

### 国产平台

| 服务商 | 适配协议 | 默认 endpoint | 推荐模型 |
|--------|---------|---------------|---------|
| **DeepSeek** | OpenAI-compatible | `https://api.deepseek.com/v1/chat/completions` | `deepseek-v4-pro` |
| **Kimi (月之暗面)** | OpenAI-compatible | `https://api.moonshot.ai/v1/chat/completions` | `kimi-k2.6` |
| **Qwen (阿里云)** | OpenAI-compatible | `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions` | `qwen-plus` |
| **GLM (智谱AI)** | OpenAI-compatible | `https://open.bigmodel.cn/api/paas/v4/chat/completions` | `glm-5.1` |

### 国际平台

| 服务商 | 适配协议 | 默认 endpoint | 推荐模型 |
|--------|---------|---------------|---------|
| **OpenAI** | Native OpenAI | `https://api.openai.com/v1/chat/completions` | `gpt-4.1` |
| **Claude (Anthropic)** | Native Anthropic | `https://api.anthropic.com/v1/messages` | `claude-opus-4-7` |
| **Gemini (Google)** | Native Gemini | `https://generativelanguage.googleapis.com/v1beta/models` | `gemini-2.5-pro` |

### 自定义平台

任何兼容 OpenAI Chat Completions 格式的第三方平台均可使用。在向导中选择"自定义 / Other"，手动输入：
- 适配器类型（`openai` / `anthropic` / `gemini`）
- API endpoint
- 模型 ID

---

## 手动编辑 api.yaml

如果向导无法满足需求，可手动编辑 `jobs/{jobid}/api.yaml`（位于 skill 根目录下）：

```yaml
api:
  provider: "deepseek"           # 厂商标识（用于显示）
  type: "openai"                 # 适配器类型：openai | anthropic | gemini
  base_url: "https://api.deepseek.com/v1/chat/completions"
  api_key: "sk-xxx"
  model: "deepseek-v4-pro"
  temperature: 0.3
  max_tokens: 8192

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

### 字段说明

| 字段 | 说明 |
|------|------|
| `provider` | 厂商标识字符串，仅用于日志和显示 |
| `type` | **关键字段**，决定请求体格式和响应解析方式。必须是 `openai`、`anthropic` 或 `gemini` 之一 |
| `base_url` | 完整的 API endpoint（包含路径） |
| `api_key` | API 密钥 |
| `model` | 模型 ID |
| `temperature` | 生成温度，建议 0.2–0.5 |
| `max_tokens` | 单次生成最大 token 数 |

### 各类型 endpoint 完整示例

**OpenAI-compatible:**
```yaml
base_url: "https://api.moonshot.ai/v1/chat/completions"
```

**Anthropic native:**
```yaml
base_url: "https://api.anthropic.com/v1/messages"
```

**Gemini native:**
```yaml
base_url: "https://generativelanguage.googleapis.com/v1beta/models"
```
> Gemini 的 URL 不需要包含模型名和 `:generateContent`，适配器会自动拼接。

---

## API Key 获取地址

| 服务商 | 地址 |
|--------|------|
| DeepSeek | https://platform.deepseek.com/ |
| Kimi | https://platform.moonshot.cn/ |
| Qwen | https://dashscope.aliyun.com/ |
| GLM | https://open.bigmodel.cn/ |
| OpenAI | https://platform.openai.com/api-keys |
| Claude | https://console.anthropic.com/ |
| Gemini | https://aistudio.google.com/app/apikey |

---

## 环境变量替代

api.yaml 支持 `${VAR_NAME}` 语法引用环境变量：

```yaml
api:
  api_key: "${DEEPSEEK_API_KEY}"
```

这在避免将 key 写入版本控制时很有用。可以将 key 放入 `.bashrc` / `.zshrc`：

```bash
export DEEPSEEK_API_KEY="sk-xxx"
```

---

## 常见问题

**Q: 是否支持同时配置多个厂商？**
A: 每个 job 的 `api.yaml` 只能指定一个活跃厂商。如需切换，让 Agent 重新配置或手动编辑 `api.yaml`。

**Q: 使用国内厂商时连接超时？**
A: 确保网络可访问对应 endpoint。部分校园网/企业网可能需要代理。timeout 固定在 300 秒，通常足够。

**Q: Gemini 返回空内容？**
A: Gemini 对 system prompt 的处理方式不同（适配器会将 system + user 合并为单条 user message）。如遇到内容安全拦截，请检查提示词中是否包含敏感内容。

**Q: 如何测试 API 是否通？**
A: 直接运行 Stage 2 的 `--dry-run` 模式：
```bash
cd ~/.claude/skills/aigcpass && python3 -u script/stage2_api.py --jobid mypaper --dry-run
```
此模式不调用真实 API，只模拟面板展示。
