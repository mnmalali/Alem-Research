# Model providers and setup

Alem's model subsystem has two layers:

1. `model_completion` is a versioned, contract-validated core capability.
2. Protocol adapters translate provider-neutral messages to an official
   OpenAI-compatible chat endpoint or Anthropic Messages endpoint.

The gateway is separate from `academic_search` and from the candidate Feynman
`research_agent` bridge. Alem does not install Feynman, inherit its auth state,
or infer its model from Alem's selected model.

## Support matrix

The matrix describes the base Python gateway shipped in this repository. A
`catalogued` provider is visible for planning but is not marked usable until a
supported adapter and endpoint are configured. The built-in model IDs are a
static starting catalog; live availability and entitlement remain provider
responsibilities.

| Provider | State | Authentication | Adapter / endpoint |
| --- | --- | --- | --- |
| OpenAI Platform | supported | API key (`OPENAI_API_KEY`) | OpenAI-compatible `/chat/completions` |
| Anthropic API | supported | API key (`ANTHROPIC_API_KEY`) | Anthropic `/messages` |
| OpenRouter | supported | API key (`OPENROUTER_API_KEY`) | OpenAI-compatible |
| DeepSeek | supported | API key (`DEEPSEEK_API_KEY`) | OpenAI-compatible |
| DashScope / Qwen | supported | API key (`DASHSCOPE_API_KEY`) | OpenAI-compatible |
| Zhipu / GLM | supported | API key (`ZHIPUAI_API_KEY`) | OpenAI-compatible |
| Moonshot / Kimi China | supported | API key (`MOONSHOT_API_KEY`) | OpenAI-compatible |
| Ollama | supported | local/no auth | local OpenAI-compatible endpoint |
| LM Studio | supported | local/no auth | local OpenAI-compatible endpoint |
| MiniMax | catalogued | API key (`MINIMAX_API_KEY`) | configure an explicit endpoint |
| Google Gemini | catalogued | API key or cloud credentials | no Gemini adapter in this base gateway |
| OpenAI Codex / ChatGPT subscription | unsupported | OAuth | no private or undocumented flow is implemented |
| Claude subscription | unsupported | OAuth | no private or undocumented flow is implemented |

ChatGPT Plus/Pro access and OpenAI Platform API billing are separate products.
A ChatGPT subscription is not represented as an OpenAI API key. The same rule
applies to Claude subscriptions versus the Anthropic API.

## Select a model

In the interactive terminal, type `/model` or press Ctrl+M. Use left/right to
switch provider, up/down to choose a model, and Enter to save it. A provider
without credentials offers an API-key setup action. Local providers list models
returned by their running `/models` endpoint. The selected model appears in the
workspace panel and status bar.

```powershell
alem model providers
alem model list --provider openai
alem model set openai/gpt-4o-mini
alem model current
alem model status
```

Set an API key through an environment variable, or enter it without placing the
secret in shell history:

```powershell
$env:OPENAI_API_KEY = "..."
alem model set openai/gpt-4o-mini

Get-Content .\openai-key.txt | alem model login openai --api-key-stdin
alem model test
```

`model logout` removes only the workspace-local credential. It does not unset
an environment variable.

## Local and custom endpoints

Local HTTP is allowed only for loopback hosts. Remote endpoints must use HTTPS;
URLs with embedded credentials, query parameters, or fragments are rejected.

```powershell
alem model configure custom-openai `
  --base-url http://127.0.0.1:1234/v1 `
  --model my-local-model
alem model set custom-openai/my-local-model
alem model test
```

The same pattern works with an explicit remote OpenAI-compatible gateway. Use
`--api-key-stdin` for a key; do not put it in the URL or command arguments.

## Connection and troubleshooting

`alem model doctor` is offline and explains credentials, endpoint setup, local
readiness, and unsupported authentication. `alem model test` makes a bounded
`GET /models` request for the selected provider and reports only the provider,
redacted endpoint, and reachability. It does not send a prompt.

Common states:

- `needs-credentials`: set the documented environment variable or run
  `alem model login PROVIDER`.
- `needs-configuration`: provide an endpoint with `alem model configure`.
- `unsupported`: the provider is visible for accuracy but the base gateway will
  not claim support.
- `local`: the endpoint is configured; the service may still be stopped. Run
  `alem model test` to check it.

Transient provider failures (timeouts, rate limits, and common 5xx responses)
follow the ordered list configured with `alem model fallbacks --set
PROVIDER/MODEL`. Authentication, permission, validation, and unsupported-policy
errors stop immediately so a fallback cannot hide a configuration or entitlement
problem. The gateway exposes the selected fallback and classified failures in
response metadata without recording message content.

The Python gateway normalizes complete responses and parses text deltas from
OpenAI-compatible and Anthropic SSE streams. The interactive app can request
cancellation between received events and closes the response when processing
ends. A provider that stalls before its next event remains subject to the
request timeout. Token pricing and tool-call streaming are not implemented.

## Credential and privacy model

The default fallback credential store is
`.alem/state/model-credentials.json`. It is written atomically, marked
user-readable/user-writable where the platform exposes POSIX modes, and on
Windows Alem attempts to remove inherited ACLs and grant the current user
access with `icacls`. It is excluded by the repository's `.gitignore` and never
included in status or telemetry. The workspace-local state is intentionally separate from non-secret
`.alem/state/model-config.json`, which stores model selection, endpoint
overrides, and aliases.

Environment variables take precedence over the local fallback. Alem does not
read credentials from unrelated agent directories, scrape browsers, reproduce
private subscription token exchanges, or send prompts as telemetry.
