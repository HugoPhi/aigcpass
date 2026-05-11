# 配置 API

## 创建配置文件

项目根目录需要 `config/api.yaml`。如果不存在，从示例模板创建：

```bash
cp config/api.yaml.example config/api.yaml
```

然后编辑 `config/api.yaml`，修改以下字段：

### 必填项

```yaml
api:
  openai:
    api_key: "你的API密钥"    # 从 DeepSeek 或其他平台获取
```

### 可选项

```yaml
api:
  provider: "openai"              # API 协议: openai 或 anthropic
  model: "deepseek-v4-pro"       # deepseek-v4-pro 效果最好
  temperature: 0.3                # 0-1, 太高不稳定, 太低保守回显
  max_tokens: 8192

retry:
  max_retries: 3                  # 失败重试次数
  temperature_delta: 0.1         # 每次重试升温增量

validation:
  check_paragraph_count: true
  check_latex_braces: true
  check_cite_preserved: true
  check_ref_preserved: true
  check_content_changed: true
```

### DeepSeek API 申请

1. 访问 https://platform.deepseek.com/
2. 注册并充值（最低 10 元）
3. 创建 API key
4. 填入 `config/api.yaml`

### 其他 API 平台

兼容 OpenAI Chat Completions 格式的任意平台均可使用。修改 `openai.base_url` 和 `api_key` 即可。
