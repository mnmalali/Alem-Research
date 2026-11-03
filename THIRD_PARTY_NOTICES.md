# Third-party notices

The repository contains a small, explicitly curated set of third-party skill and
catalog assets plus Alem-written adapters. They retain their own licenses and are isolated under
`plugins/community/`; they are not part of Alem's required core runtime. Exact source revisions,
copied paths, and integration decisions are recorded in
[`docs/upstream-register.toml`](docs/upstream-register.toml).

Included notices:

- `plugins/community/orchestra-research-skills/LICENSE-ORCHESTRA`: MIT-licensed skill assets
  copied from Orchestra Research at commit `773a52944ba4747a18bd4ae9ade53fff041adcbc`.
- `plugins/community/wenyu-research-catalog/LICENSE-WENYU`: MIT-licensed catalog metadata copied
  from Wenyu Chiou's AI Research Skills catalog at commit `8547d889612ca624d523f39d20d35a97dbd87802`.
- `plugins/community/awesome-research-tools-catalog/LICENSE-AWESOME`: CC0-1.0 list content copied
  from Awesome AI Research Tools at commit `1369c3c55e17f37a9abbe7f4ddc5ba2b0636a7f1`.
- `plugins/community/feynman-bridge`: an Alem-written adapter only; Feynman remains a separately
  installed MIT-licensed runtime and is not vendored.

The Alem 1.0 runtime directly depends on PyYAML (MIT) for workflow specifications and jsonschema
(MIT) for capability-contract validation. Their transitive Python packages retain their own
licenses and are installed by the package manager. Development tools installed through the
optional `dev` extra retain their own licenses. Plugins may declare separate dependencies; their
licenses must be reviewed before catalogue acceptance and installation remains explicit.

Remote academic metadata returned by OpenAlex or Semantic Scholar is subject to the providers'
terms and the rights attached to the underlying works. A free API is not equivalent to unrestricted
redistribution of full text.
