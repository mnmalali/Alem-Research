# Feynman Research Agent Bridge

This is an Alem adapter, not a vendored copy of Feynman. It calls an already-installed
`feynman` executable through the provider-neutral `research_agent` capability.

The upstream source was audited at commit
`89b0242919faf89b38dcb6ae8be92f6dbcd77203` (`v0.5.61`). Feynman requires Node.js and
a model-provider setup. Alem does not install it globally, copy its source, inherit its
telemetry settings, or treat its internal Pi extension API as an Alem API.

The bridge defaults `FEYNMAN_TELEMETRY=off`, runs in the plugin data directory, allows only
the declared credentials through, and requires separate Alem installation and execution
approval. The subprocess boundary is not an operating-system sandbox.

Example:

```json
{"topic":"scaling laws in language models","mode":"deepresearch"}
```
