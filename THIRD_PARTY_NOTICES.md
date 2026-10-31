# Third-party notices

The foundation repository does not vendor code, skill text, or documentation from the five upstream
projects in the source audit. They are referenced for architectural comparison and retain their own
licenses. Exact source revisions and decisions are recorded in
[`docs/upstream-register.toml`](docs/upstream-register.toml).

The Alem runtime uses only the Python standard library. Development tools installed through the
optional `dev` extra retain their own licenses. Plugins may declare separate dependencies; their
licenses must be reviewed before catalogue acceptance and installation remains explicit.

Remote academic metadata returned by OpenAlex or Semantic Scholar is subject to the providers'
terms and the rights attached to the underlying works. A free API is not equivalent to unrestricted
redistribution of full text.
