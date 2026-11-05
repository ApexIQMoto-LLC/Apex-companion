# APEX Companion v0.11.0 - Multi-Provider Automatic AI Routing

- Intelligent local intent detection: planning/conversation prefers Luna, coding
  prefers Sol, business analytics prefers Terra.
- Opt-in DeepSeek, Anthropic, Groq, Mistral, OpenRouter, Hugging Face,
  Together, Fireworks, Cerebras, DeepInfra connectors.
- Optional loopback-only Ollama, LM Studio and UnfilteredAI-1B local servers.
- Models are selected by task and recent context, not manually per request.
- Model-specific cooldown after rate-limit or transient server failures.
- Hosted fallback requires provider opt-in, a key and a known/configured price;
  local servers require separate opt-in. No secret is included in the ZIP.
- No external AI agents receive shell, PC, cloud write or publishing authority.
- One bounded additional OpenAI attempt for truncated output restored.
- Changed CHECK AI to show a local/no-cost model routing preview.
- 194 offline tests passed. Real API availability and Windows integration are
  not confirmed; configure providers before attempting real inference.

Instructions: `docs/MODEL_ROUTING_v0_11.md`.
