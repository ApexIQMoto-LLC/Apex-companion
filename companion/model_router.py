"""APEX task-directed model routing across authorized cloud and local providers.

Only configured/approved destinations receive owner content. Non-OpenAI text
adapters have no local tool authority. Local endpoints are strictly loopback.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Route:
    provider: str
    model: str
    task: str


class ProviderFailure(RuntimeError):
    def __init__(self, provider, status, retry_after=None):
        self.provider = provider
        self.status = int(status)
        self.retry_after = retry_after
        super().__init__(f"{provider} API returned HTTP {self.status}")


# Fixed, verified API destinations. Never accept arbitrary remote URLs from
# an AI answer, user prompt, imported content, or a model-generated tool call.
COMPATIBLE_PROVIDERS = {
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY"),
    "huggingface": ("https://router.huggingface.co/v1/chat/completions", "HF_TOKEN"),
    "mistral": ("https://api.mistral.ai/v1/chat/completions", "MISTRAL_API_KEY"),
    "together": ("https://api.together.xyz/v1/chat/completions", "TOGETHER_API_KEY"),
    "fireworks": ("https://api.fireworks.ai/inference/v1/chat/completions", "FIREWORKS_API_KEY"),
    "cerebras": ("https://api.cerebras.ai/v1/chat/completions", "CEREBRAS_API_KEY"),
    "deepinfra": ("https://api.deepinfra.com/v1/openai/chat/completions", "DEEPINFRA_API_KEY"),
}
LOCAL_PROVIDERS = {
    "ollama": ("http://127.0.0.1:11434/v1/chat/completions", "llama3.2:3b"),
    "lmstudio": ("http://127.0.0.1:1234/v1/chat/completions", "local-model"),
    "unfiltered_local": ("http://127.0.0.1:8000/v1/chat/completions", "UnfilteredAI/UNfilteredAI-1B"),
}
CLOUD_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5-5",
    "deepseek": "deepseek-flash",
    "groq": "openai/gpt-oss-20b",
    "huggingface": "openai/gpt-oss-20b:cheapest",
    "mistral": "mistral-small-latest",
}

_CODE = re.compile(r"\b(?:coding|coder|programming|python|javascript|typescript|c\+\+|c#|unity|unreal|compiler?|stack ?trace|exception|function|regex|refactor|shader|repository|git|pull request|api integration|fix the app|write a patch|implement the feature)\b", re.I)
_PLAN = re.compile(r"\b(?:plan|planning|strategy|roadmap|schedule|business|marketing|content|instagram|tiktok|youtube|reel|creator|customer|beta tester|budget|goal|partnership|sales|outreach|campaign|personal|storyboard|caption|video script|post ideas)\b", re.I)
_ANALYSIS = re.compile(r"\b(?:analy[sz]e|analysis|compare|forecast|calculate|report|metrics|performance|conversion|roi|tradeoff|investigate|audit|statistics)\b", re.I)
_FOLLOWUP = re.compile(r"^(?:and |what about |why\??$|continue\b|also\b|okay\b|yes\b|do that\b|go on\b|now\b|can we\b|how about\b)", re.I)


def detect_task(message: str, last_task: str | None = None, deep: bool = False) -> str:
    text = str(message).strip()[:2500]
    # A marketing video script is not source-code programming.
    if _CODE.search(text):
        return "coding"
    if _ANALYSIS.search(text):
        return "analysis"
    if _PLAN.search(text):
        return "planning"
    if _FOLLOWUP.search(text) and last_task in {"coding", "planning", "analysis"}:
        return last_task
    return "analysis" if deep else "conversation"


def _actual_key(provider, env):
    if provider == "openai":
        return env.get("OPENAI_API_KEY", "")
    if provider == "anthropic":
        return env.get("ANTHROPIC_API_KEY", "")
    if provider == "deepseek":
        return env.get("DEEPSEEK_API_KEY", "")
    if provider in COMPATIBLE_PROVIDERS:
        return env.get(COMPATIBLE_PROVIDERS[provider][1], "")
    return ""


def _valid_key(key):
    key = str(key).strip()
    return bool(key) and not key.lower().startswith(("replace_", "your_", "paste_", "<"))


def _enabled(provider, settings):
    if provider == "openai":
        return True
    if provider in LOCAL_PROVIDERS:
        return bool(settings.get("allow_local_ai", False)) and provider in settings.get("enabled_local_ai_providers", [])
    if not settings.get("allow_external_ai_providers", False):
        return False
    providers = settings.get("enabled_ai_providers", [])
    if not providers:  # Preserve previous v0.11 provider opt-in for existing users.
        return provider in {"anthropic", "deepseek"}
    return provider in providers


def _model(provider, settings, task="conversation"):
    models = settings.get("provider_models") or {}
    task_models = settings.get("provider_task_models") or {}
    selection = task_models.get(provider, {}) if isinstance(task_models, dict) else {}
    model = selection.get(task) if isinstance(selection, dict) else None
    if not model:
        model = models.get(provider) if isinstance(models, dict) else None
    if provider in LOCAL_PROVIDERS:
        return str(model or LOCAL_PROVIDERS[provider][1]).strip()
    return str(model or CLOUD_DEFAULT_MODELS.get(provider, "")).strip()


def _local_endpoint(provider, settings):
    # Configurable port, but never arbitrary remote addresses or embedded auth.
    address = str((settings.get("local_ai_urls") or {}).get(provider) or LOCAL_PROVIDERS[provider][0])
    parsed = urlsplit(address)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != "/v1/chat/completions" or not parsed.port):
        raise ValueError("Local AI URL must be an explicit loopback HTTP chat-completions endpoint")
    return address


def _rates(provider, model, settings):
    # A non-local third party without a known/current rate is not silently
    # eligible for spending. The owner must configure per-model rates.
    if provider in LOCAL_PROVIDERS:
        return (0.0, 0.0)
    from .costs import PRICES
    if provider == "openai" and model in PRICES:
        return PRICES[model]
    if provider in {"anthropic", "deepseek"} and model in PRICES:
        return PRICES[model]
    price_map = settings.get("model_rates_usd_per_million") or {}
    rate = price_map.get(f"{provider}:{model}") if isinstance(price_map, dict) else None
    if (isinstance(rate, (list, tuple)) and len(rate) == 2 and
            all(isinstance(v, (int, float)) and 0 <= v <= 1000 for v in rate)):
        return tuple(float(v) for v in rate)
    return None


def provider_ready(provider: str, settings: dict, environ=None) -> bool:
    env = os.environ if environ is None else environ
    if not _enabled(provider, settings):
        return False
    if provider in LOCAL_PROVIDERS:
        try:
            _local_endpoint(provider, settings)
        except (ValueError, TypeError):
            return False
        return True
    if not _valid_key(_actual_key(provider, env)):
        return False
    return True


_TASK_ORDER = {
    "coding": ("openai", "anthropic", "deepseek", "groq", "openrouter", "together", "fireworks", "cerebras", "huggingface", "deepinfra", "mistral", "ollama", "lmstudio", "unfiltered_local"),
    "planning": ("openai", "anthropic", "deepseek", "mistral", "openrouter", "huggingface", "together", "groq", "fireworks", "cerebras", "deepinfra", "ollama", "lmstudio", "unfiltered_local"),
    "analysis": ("openai", "anthropic", "deepseek", "cerebras", "openrouter", "huggingface", "together", "groq", "fireworks", "deepinfra", "mistral", "ollama", "lmstudio", "unfiltered_local"),
    "conversation": ("openai", "groq", "deepseek", "ollama", "lmstudio", "openrouter", "huggingface", "mistral", "together", "fireworks", "deepinfra", "cerebras", "anthropic", "unfiltered_local"),
}


def routes_for(task: str, settings: dict, environ=None, require_tools=False) -> list[Route]:
    task = task if task in _TASK_ORDER else "conversation"
    main = {
        "coding": settings.get("coding_model") or "gpt-6.1-sol",
        "planning": settings.get("chat_model") or "gpt-6-luna",
        "analysis": settings.get("analysis_model") or "gpt-6.1-terra",
        "conversation": settings.get("chat_model") or "gpt-6-luna",
    }
    openai_fallback = settings.get("analysis_model") or "gpt-6.1-terra"
    ordered = ["openai"] + [p for p in _TASK_ORDER[task] if p != "openai"]
    routes = []
    for provider in ordered:
        if require_tools and provider != "openai":
            continue  # Tool call identifiers cannot be replayed across APIs.
        if not provider_ready(provider, settings, environ):
            continue
        model = main[task] if provider == "openai" else _model(provider, settings, task)
        if not model or _rates(provider, model, settings) is None:
            continue
        routes.append(Route(provider, model, task))
    if not require_tools and provider_ready("openai", settings, environ) and openai_fallback != main[task]:
        if _rates("openai", openai_fallback, settings) is not None:
            routes.append(Route("openai", openai_fallback, task))
    return routes


def model_pricing(route: Route, settings: dict):
    return _rates(route.provider, route.model, settings)


def _post_json(url, payload, headers, timeout=45):
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise RuntimeError("Model response exceeded the allowed size")
            return json.loads(raw.decode("utf-8"))
    except HTTPError as error:
        delay = error.headers.get("Retry-After") if error.headers else None
        raise ProviderFailure("External", error.code, retry_after=delay) from None
    except (URLError, TimeoutError):
        raise RuntimeError("AI provider is unreachable") from None


def text_completion(route: Route, instructions: str, messages: list, max_tokens: int, settings=None, environ=None):
    """Text-only conversation adapter: no local file, network, or tool authority."""
    settings = settings or {}
    env = os.environ if environ is None else environ
    provider = route.provider
    if provider in {"openai"}:
        raise ValueError("Use native OpenAI Responses adapter")
    if not provider_ready(provider, settings, env):
        raise ValueError("Provider not enabled or not configured")
    content = [{"role": m["role"], "content": m["content"][:12000]} for m in messages
               if m.get("role") in {"user", "assistant"} and isinstance(m.get("content"), str)]
    while content and content[0]["role"] != "user":
        content.pop(0)
    if not content:
        raise ValueError("Text completion requires a user message")
    if provider == "unfiltered_local":
        # 2,048-token configured context: only send short recent conversation.
        instructions = instructions[:900]
        content = [{"role": m["role"], "content": m["content"][:900]} for m in content[-3:]]
        while content and content[0]["role"] != "user":
            content.pop(0)
        max_tokens = min(max_tokens, 256)
    cap = max(1, min(int(max_tokens), 4096))
    if provider == "anthropic":
        body = {"model": route.model, "max_tokens": cap, "system": instructions, "messages": content}
        data = _post_json("https://api.anthropic.com/v1/messages", body,
                          {"x-api-key": _actual_key(provider, env), "anthropic-version": "2023-06-01", "Content-Type": "application/json"})
        answer = "\n".join(x.get("text", "") for x in data.get("content", []) if x.get("type") == "text")
        usage = data.get("usage") or {}
        incoming = int(usage.get("input_tokens", 0) or 0)
        outgoing = int(usage.get("output_tokens", 0) or 0)
    else:
        body = {"model": route.model, "messages": [{"role": "system", "content": instructions}] + content,
                "max_tokens": cap}
        if provider == "deepseek":
            url = "https://api.deepseek.com/chat/completions"
        elif provider in LOCAL_PROVIDERS:
            url = _local_endpoint(provider, settings)
        else:
            url = COMPATIBLE_PROVIDERS[provider][0]
        headers = {"Content-Type": "application/json"}
        if provider not in LOCAL_PROVIDERS:
            headers["Authorization"] = "Bearer " + _actual_key(provider, env)
        data = _post_json(url, body, headers)
        choices = data.get("choices") or []
        answer = ((choices[0].get("message") or {}).get("content") or "") if choices else ""
        usage = data.get("usage") or {}
        incoming = int(usage.get("prompt_tokens", 0) or 0)
        outgoing = int(usage.get("completion_tokens", 0) or 0)
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("AI provider returned an empty response")
    return SimpleNamespace(status="completed", output_text=answer.strip(), output=[],
                           usage=SimpleNamespace(input_tokens=incoming, output_tokens=outgoing))
