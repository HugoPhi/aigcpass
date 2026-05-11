#!/usr/bin/env python3
"""Provider registry for aigcpass Stage 2 API adapters.

Contains metadata and adapter dispatch logic for all supported LLM providers.
To add a new provider, simply add an entry to PROVIDERS dict.
"""

from typing import Dict, Any, List

# ─── Provider Registry ───────────────────────────────────────────────
# Each provider defines:
#   name:       Human-readable display name
#   type:       Adapter type (openai, anthropic, gemini)
#   base_url:   Default API endpoint
#   models:     Suggested models (first = default)
#   key_hint:   Where to get the API key
#   docs_url:   Documentation link
# ─────────────────────────────────────────────────────────────────────

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "deepseek": {
        "name": "DeepSeek (深度求索)",
        "type": "openai",
        "base_url": "https://api.deepseek.com/v1/chat/completions",
        "models": ["deepseek-v4-pro", "deepseek-v4-flash"],
        "key_hint": "https://platform.deepseek.com/",
        "docs_url": "https://api-docs.deepseek.com/",
    },
    "kimi": {
        "name": "Kimi (月之暗面)",
        "type": "openai",
        "base_url": "https://api.moonshot.ai/v1/chat/completions",
        "models": ["kimi-k2.6", "kimi-k2.5", "moonshot-v1-128k"],
        "key_hint": "https://platform.moonshot.cn/ 或 https://platform.kimi.ai/",
        "docs_url": "https://platform.kimi.ai/docs/",
    },
    "qwen": {
        "name": "Qwen (阿里云通义千问)",
        "type": "openai",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "models": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen3.5-plus"],
        "key_hint": "https://dashscope.aliyun.com/",
        "docs_url": "https://help.aliyun.com/zh/dashscope/",
    },
    "glm": {
        "name": "GLM (智谱AI)",
        "type": "openai",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "models": ["glm-5.1", "glm-5", "glm-4-plus", "glm-4-flash"],
        "key_hint": "https://open.bigmodel.cn/ 或 https://z.ai/",
        "docs_url": "https://open.bigmodel.cn/dev/api",
    },
    "openai": {
        "name": "OpenAI",
        "type": "openai",
        "base_url": "https://api.openai.com/v1/chat/completions",
        "models": ["gpt-4.1", "gpt-4o", "gpt-4o-mini"],
        "key_hint": "https://platform.openai.com/api-keys",
        "docs_url": "https://platform.openai.com/docs/",
    },
    "claude": {
        "name": "Claude (Anthropic)",
        "type": "anthropic",
        "base_url": "https://api.anthropic.com/v1/messages",
        "models": ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
        "key_hint": "https://console.anthropic.com/",
        "docs_url": "https://docs.anthropic.com/en/api/messages",
    },
    "gemini": {
        "name": "Gemini (Google)",
        "type": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "models": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"],
        "key_hint": "https://aistudio.google.com/app/apikey",
        "docs_url": "https://ai.google.dev/gemini-api/docs",
    },
}


def list_providers() -> List[str]:
    """Return ordered list of provider keys."""
    return list(PROVIDERS.keys())


def get_provider(key: str) -> Dict[str, Any]:
    """Get provider metadata by key. Raises KeyError if unknown."""
    if key not in PROVIDERS:
        raise KeyError(f"Unknown provider: {key}. Available: {', '.join(PROVIDERS.keys())}")
    return PROVIDERS[key]


def get_provider_by_type(adapter_type: str) -> List[str]:
    """Return all provider keys matching a given adapter type."""
    return [k for k, v in PROVIDERS.items() if v["type"] == adapter_type]


# ─── API Call Dispatch ───────────────────────────────────────────────

def call_api(cfg: Dict[str, Any], system_prompt: str, user_prompt: str, temperature: float = None):
    """Dispatch API call based on provider type in config.

    cfg structure (from api.yaml):
      api:
        provider: "deepseek"
        type: "openai"
        base_url: "..."
        api_key: "..."
        model: "..."
        max_tokens: 8192
        temperature: 0.3
    """
    import json, urllib.request, urllib.error, time, re

    api_cfg = cfg.get("api", {})
    provider_type = api_cfg.get("type", "openai")
    base_url = api_cfg["base_url"]
    api_key = api_cfg["api_key"]
    model = api_cfg["model"]
    max_tok = api_cfg.get("max_tokens", 8192)
    temp = temperature if temperature is not None else api_cfg.get("temperature", 0.3)

    if provider_type == "openai":
        return _call_openai(base_url, api_key, model, max_tok, temp, system_prompt, user_prompt)
    elif provider_type == "anthropic":
        return _call_anthropic(base_url, api_key, model, max_tok, temp, system_prompt, user_prompt)
    elif provider_type == "gemini":
        return _call_gemini(base_url, api_key, model, max_tok, temp, system_prompt, user_prompt)
    else:
        raise ValueError(f"Unsupported provider type: {provider_type}")


def _call_openai(base_url, api_key, model, max_tokens, temperature, system_prompt, user_prompt):
    import json, urllib.request, urllib.error, time

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = urllib.request.Request(base_url, data=json.dumps(body).encode("utf-8"), headers=headers)

    for delay in [1, 2, 4, 8, 16]:
        try:
            resp = urllib.request.urlopen(req, timeout=300)
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(delay)
                continue
            raise
    raise RuntimeError("429 retries exhausted")


def _call_anthropic(base_url, api_key, model, max_tokens, temperature, system_prompt, user_prompt):
    import json, urllib.request, urllib.error, time

    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    req = urllib.request.Request(base_url, data=json.dumps(body).encode("utf-8"), headers=headers)

    for delay in [1, 2, 4, 8, 16]:
        try:
            resp = urllib.request.urlopen(req, timeout=300)
            data = json.loads(resp.read())
            return data["content"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(delay)
                continue
            raise
    raise RuntimeError("429 retries exhausted")


def _call_gemini(base_url, api_key, model, max_tokens, temperature, system_prompt, user_prompt):
    import json, urllib.request, urllib.error, time

    # Gemini uses :generateContent appended to model path
    url = f"{base_url}/{model}:generateContent?key={api_key}"

    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": f"{system_prompt}\n\n{user_prompt}"},
                ],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)

    for delay in [1, 2, 4, 8, 16]:
        try:
            resp = urllib.request.urlopen(req, timeout=300)
            data = json.loads(resp.read())
            # Gemini response structure
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini returned no candidates")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise RuntimeError("Gemini returned empty content parts")
            return parts[0].get("text", "")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(delay)
                continue
            raise
    raise RuntimeError("429 retries exhausted")
