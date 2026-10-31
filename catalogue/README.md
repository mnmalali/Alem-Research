# Alem plugin catalogue

`index.toml` is the foundation-phase catalogue: a reviewable, versioned file
in Git rather than a marketplace or service. Official and community entries
use the same manifest and lifecycle. Official entries are Alem-maintained.
Community entries carry an explicit `verification` value: `verified` means an
Alem maintainer has reviewed and accepted the plugin, while `unverified` means
it is available for inspection but has not received that review. Neither value
replaces execution approval.

Community submissions follow `CONTRIBUTING-PLUGINS.md` and arrive through a
pull request that adds the plugin source (or, in a later API version, a pinned
source archive), catalogue entry, tests, and license information.
