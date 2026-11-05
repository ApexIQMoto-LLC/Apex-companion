# APEX v0.11.0 - Automatic multi-provider AI router

**What it does:** Detects conversational, planning, analytics, and coding tasks locally,
without spending a token on a separate classifier. APEX chooses an eligible model
and falls back during 429 or 5xx errors. Luna remains preferred for conversation/
planning, Sol for coding, and Terra for analytics. Provider/model used is shown
in responses. This does not grant model-generated tools or shell commands.

## Supported cloud providers

| Provider | `.env` key | Endpoint type |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | Native Responses API |
| Anthropic Claude | `ANTHROPIC_API_KEY` | Native Messages API |
| DeepSeek | `DEEPSEEK_API_KEY` | Chat Completions API |
| OpenRouter | `OPENROUTER_API_KEY` | OpenAI-compatible |
| Groq | `GROQ_API_KEY` | OpenAI-compatible |
| Hugging Face Inference Providers | `HF_TOKEN` | OpenAI-compatible router |
| Mistral | `MISTRAL_API_KEY` | OpenAI-compatible |
| Together AI | `TOGETHER_API_KEY` | OpenAI-compatible |
| Fireworks AI | `FIREWORKS_API_KEY` | OpenAI-compatible |
| Cerebras | `CEREBRAS_API_KEY` | OpenAI-compatible |
| DeepInfra | `DEEPINFRA_API_KEY` | OpenAI-compatible |

GitHub Models' standalone inference API was retired; GitHub Copilot is a separate
integration. Do not use an obsolete GitHub Models URL.

### One-time cloud provider setup

1. Obtain only the API keys you need from official provider accounts. Save them
   in your installed APEX `.env` file. Do not send them through chat or Git.
2. In the installed APEX `config.json`, **merge** (do not erase other settings)
   fields like the example below. Example rates below are **ILLUSTRATIVE**, not
   a claim about current provider pricing: REPLACE WITH CURRENT DOCUMENTED RATES.
3. Enable a provider only after accepting that relevant conversation context
   may be sent to that service. Actual services may bill separately from OpenAI.
4. Open APEX > CHECK AI for a zero-cost router preview. It does not test live
   network access, key validity, or model quota. Ask an ordinary question to test.

```json
{
  "allow_external_ai_providers": true,
  "enabled_ai_providers": ["groq", "openrouter"],
  "provider_models": {
    "groq": "openai/gpt-oss-20b",
    "openrouter": "YOUR_SELECTED_CURRENT_MODEL_SLUG"
  },
  "provider_task_models": {
    "groq": {"coding": "openai/gpt-oss-120b"}
  },
  "model_rates_usd_per_million": {
    "groq:openai/gpt-oss-20b": [0.10, 0.50],
    "groq:openai/gpt-oss-120b": [0.15, 0.75],
    "openrouter:YOUR_SELECTED_CURRENT_MODEL_SLUG": [0.0, 0.0]
  },
  "max_model_attempts": 5
}
```

**The numeric rates above are examples and MUST be verified and replaced.**
Zero rates are appropriate only for explicitly free model endpoints; otherwise
using a zero estimate can understate costs. The router does not attempt to
purchase credits or alter account limits. Models with no known/configured rate
are skipped (fail-closed). Cross-provider credential failures are never repaired
by brute force retries. Request rate-limit headers are respected where supplied.

For standard models (OpenAI, current listed Claude/DeepSeek IDs) APEX retains
its internal cost table. For any provider or model outside that table,
set a rate per million *input* and *output* tokens. This is an **estimated**
local spend ledger, not a replacement for provider billing statements. Some
providers may have additional charges (cache, tools, context, etc.).

### Additional model families

OpenRouter and Hugging Face make many less-known and open-weight model families
available through one integration, including Qwen, Llama, Gemma, Nemotron,
Kimi, and community fine-tunes when hosted. Select exact supported slugs
from their current catalogs; no specific model is universally available.

## Local models (free inference after setup)

Local inference is **opt-in** and sends text only to a loopback endpoint.
No model download is performed during the APEX app update.

- **Ollama:** install Ollama, pull a suitable model, and let it serve
  `http://127.0.0.1:11434/v1/chat/completions`. Default local model example:
  `llama3.2:3b` (pull it first, or replace with your installed model).
- **LM Studio:** start its local OpenAI-compatible server on port 1234 and set
  `provider_models.lmstudio` to your loaded model's API identifier.
- **UnfilteredAI/UNfilteredAI-1B:** see the next section. APEX expects a local
  OpenAI-compatible serving process on port 8000. It **does not** download or
  run the 2.1GB model automatically.

Example installed `config.json` additions:

```json
{
  "allow_local_ai": true,
  "enabled_local_ai_providers": ["ollama", "unfiltered_local"],
  "provider_models": {
    "ollama": "llama3.2:3b",
    "unfiltered_local": "UnfilteredAI/UNfilteredAI-1B"
  }
}
```

Local endpoints must be plain HTTP on `localhost`, `127.0.0.1` or `::1`,
with the exact path `/v1/chat/completions`. Arbitrary remote URLs are rejected.
This prevents redirecting private context to an attacker-controlled API from
configuration mistakes or malicious imported text. Keep local model servers
bound to loopback, not `0.0.0.0` or your public network address.

### UnfilteredAI/UNfilteredAI-1B notes

Source: https://huggingface.co/UnfilteredAI/UNfilteredAI-1B

- ~1B parameters, 2,048 token configured context, ~2.1 GB F16 weights.
- Hugging Face currently shows no deployed Inference Provider for this model.
- It has a **custom/other license**. Verify its legal terms and commercial-use
  rights before any commercial deployment or redistribution.
- The Hugging Face model card documents compatible local servers. Example
  using a supported Linux/WSL2 vLLM environment (after reviewing license):

```bash
pip install vllm
vllm serve UnfilteredAI/UNfilteredAI-1B --host 127.0.0.1 --port 8000
```

Host setup requirements vary with GPU/runtime; vLLM support is not guaranteed
on native Windows. WSL2/containers may require port forwarding to Windows.
You can alternatively use a compatible Docker Model Runner or GGUF service
and configure the appropriate existing local adapter. No commercial or
quality guarantees are made for this community model.

'Unfiltered' is a community model description, not a guarantee of correctness,
trustworthiness, privacy or legal permission. Keep model-produced content under
normal APEX action permissions; the model never gets shell/PC/cloud write access.
Small local models should generally not be trusted with financial, security,
or consequential business decisions without verification.

## Confidentiality and tasks

- **Everyday conversation and planning:** Luna first; fast alternatives next.
- **Coding/Unity:** Sol first; suitable enabled alternatives after failures.
- **Business analytics:** Terra first; permitted analytics alternatives next.
- **Private or live-data tools:** native OpenAI only for now, because its
  read-only tool-call references cannot simply be handed to other providers.
- **Fallback:** Only explicitly authorized provider names are eligible.
  External providers are not silently authorized by entering an API key alone.

CHECK AI shows the routes that would be attempted. If an endpoint returns 429,
APEX cools down that specific model and tries another allowed route. Some
provider API features differ: certain open-weight models don't support system
messages, reasoning fields, structured output or tools. This v0.11 release
provides text-only chat compatibility and does not validate every model.

## Verification

Offline unittest suite: `python -m unittest discover -s tests -q`.
Actual third-party accounts, model availability, local GPU inference, and
cost rates must be tested on the owner's PC with approved credentials.
