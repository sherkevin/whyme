# DeepSeek Local Environment

This project can use DeepSeek through OpenAI-compatible and Anthropic-compatible base URLs during local development.

Do not commit secrets. The actual API key is stored in `.env.local`, which is ignored by git.

## Local Values

- OpenAI-compatible base URL: `https://api.deepseek.com`
- Anthropic-compatible base URL: `https://api.deepseek.com/anthropic`
- Model: `deepseek-v4-flash`

## Deprecated Models

- `deepseek-chat` is scheduled for deprecation on 2026-07-24.
- `deepseek-reasoner` is scheduled for deprecation on 2026-07-24.

## Runtime Notes

`agent_os.core.config` loads `.env` first and `.env.local` second, with local values taking precedence. `LLMConfig` and `LiteLLMProvider` read `API_KEY`, `LITELLM_API_KEY`, `DEEPSEEK_API_KEY`, `BASE_URL`, `API_BASE`, and `DEEPSEEK_OPENAI_BASE_URL`.

For OpenAI-compatible calls through LiteLLM, the provider keeps the configured model as `deepseek-v4-flash` and internally routes it through the generic OpenAI-compatible adapter when an API base URL is present.
