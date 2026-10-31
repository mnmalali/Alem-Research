# Community static-search example

This deliberately small third-party-style plugin imports only public symbols
from `alem.extensions.api`. It requires no network, credentials, filesystem
access, or Python dependencies. Its one record is synthetic and must never be
cited; the plugin exists solely to exercise the complete lifecycle.

```powershell
alem plugin validate examples/plugins/community-static-search
alem plugin install examples/plugins/community-static-search --approve
alem plugin enable dev.community.static-search --approve
```

The non-interactive CLI requires separate explicit `--approve` flags for
installation and execution. Omitting the install flag prints the review plan
and exits without installing code.
