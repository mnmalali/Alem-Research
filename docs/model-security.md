# Model security and authentication boundaries

Model configuration is workspace-local by default. The model gateway accepts
provider-neutral messages, preserves provider/model/operation metadata in the
capability response, and does not store prompt or response content in logs.

Authentication methods are intentionally distinct:

- API-key providers use documented environment variables first and the local
  fallback store second.
- Local endpoints may use no authentication.
- Cloud credential chains and subscription OAuth are not silently treated as
  API keys.
- Unsupported OAuth is shown as unsupported. No browser automation, session
  cookie scraping, private token exchange, or undocumented endpoint is used.

Remote endpoint validation requires HTTPS. HTTP is accepted only for
`localhost`, `127.0.0.1`, and `::1`. URLs containing userinfo, query strings,
or fragments are refused to avoid accidental credential forwarding.

The `.alem/` directory is runtime state and must remain untracked. API keys are
never accepted as ordinary command-line arguments, and command output redacts
credential values. `alem model test` performs only a bounded endpoint check;
use of a model remains an explicit workflow/provider decision.
