# Alem CLI dashboard

Running `alem` with no arguments opens the persistent owl-branded Textual
interface when both stdin and stdout are terminals. Type into the composer and
press Enter. `/exit` or Ctrl+Q closes the app; Ctrl+C requests cancellation,
Ctrl+M opens the model picker, F1 shows help, and Page Up/Down scrolls activity. Redirected and CI invocations
receive ordinary argparse help text.

The header uses the supplied purple/amber owl palette. The panel shows the
workspace, selected model, provider, agents, and workflow shortcuts. The main
area displays actual model response chunks and provider errors; the status bar
reports the active operation. `/model` opens a keyboard-driven picker. Left and
right switch providers; up and down highlight models; Enter selects and saves
the active model; Esc closes the picker. Providers without credentials offer an
Enter-to-setup action that opens a hidden API-key composer and returns to the
picker after setup. `/model PROVIDER/MODEL` also selects directly, `/model login
PROVIDER` opens the same setup flow, and `/provider` shows auth readiness. Esc
cancels key entry without storing anything.

For Ollama and LM Studio, the picker requests `GET /models` from the local
endpoint and offers only advertised installed IDs. If the endpoint is stopped,
it shows a connection hint. Cloud providers use Alem's configured model catalog;
the presence of an API key does not verify model entitlement. The picker does
not send a prompt. Model changes are blocked while a response is active.

`/lit PROJECT` and `/deepresearch PROJECT` start the existing literature review
and full lifecycle workflows respectively, preserving their human approval
gates. `/summarize TEXT` sends supplied text through the model gateway. Other
research shortcuts explicitly report that no direct interactive workflow is
configured and point to `alem workflow list`.

## Output modes

- `alem --no-color`, `NO_COLOR=1`, and `TERM=dumb` suppress brand colors. The
  interactive layout still needs terminal control sequences.
- JSON commands never include ANSI escape sequences.
- Legacy encodings fall back from half-block Unicode to ASCII `#` cells.

The terminal uses the existing `model_completion` capability contract and
gateway. A configured model and API key or running local endpoint are required
for natural-language questions. When no model is selected, `/model` opens the
picker with setup guidance. Connection errors appear in the activity
area. Natural-language questions use model completion; they do not perform a
live literature search unless a research workflow is explicitly started.

Windows verification: a PowerShell PTY session was used to confirm that `alem`
stays open and emits all five owl colors with `TERM=xterm-256color`,
`COLORTERM=truecolor`, and `NO_COLOR` unset. This is not a native Windows
Terminal screenshot. Native Windows Terminal visual verification and live
provider responses remain outstanding.

The picker follows the provider navigation and selection flow in the archived
[OpenCode model dialog](https://github.com/opencode-ai/opencode/blob/73ee493265acf15fcd8caab2bc8cd3bd375b63cb/internal/tui/components/dialog/models.go).
Alem uses its own Textual implementation and workspace model gateway.

## Useful commands

```text
alem --help
alem model providers
alem model list
alem model status
alem model doctor
alem health
```

The owl source artwork is maintained in
[`docs/assets/brand/`](assets/brand/), while the terminal renderer is packaged
as `alem.terminal.mascot`.
