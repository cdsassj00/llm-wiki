# Agent notes

This repository publishes the **llm-wiki** skill for the [skills](https://skills.sh/) CLI.

```bash
npx skills add cdsassj00/llm-wiki -g -a '*' -y
```

When the skill is attached as a folder (not yet installed), run:

```bash
python skills/llm-wiki/scripts/ensure_agents_install.py
```

Skill installation and workspace bootstrap are separate operations. `npx skills add` and
`ensure_agents_install.py` only install reusable skill files; they must not read personal documents,
create a user workspace, or configure API keys.

Follow `skills/llm-wiki/SKILL.md` end-to-end:

1. Ask for the document path and Wiki workspace path.
2. Recommend and confirm an ontology preset.
3. Bootstrap the blank workspace.
4. Ask the onboarding gate exactly in substance: local keyword search only, or LLM-based AI
   search/questions too?
5. If local-only, do not request provider setup. Continue through ingest → compile → index and tell
   the user to run `start-llm-wiki.bat`.
6. If AI is selected, explain the choices: logged-in Claude CLI (no key), workspace `.env`
   (recommended), or Windows User environment variables (plaintext registry). OpenRouter, OpenAI,
   Gemini, or Anthropic may be used; one provider is enough.
7. Tell the user to run `configure-provider.bat` or
   `python tools/configure_provider.py --root <workspace>`, then `start-llm-wiki.bat`.

For a blank folder, `bootstrap_wiki.py` must also install the managed workspace tools and
`start-llm-wiki.bat`/`.ps1` and `configure-provider.bat`. For an existing workspace, use
`setup_workspace.py`; do not run bootstrap over existing `purpose.md` or `schema.md`.

The browser cannot launch Python. The OS/Python launcher starts the bridge, verifies `/health`,
builds missing HTML, and opens the browser. Keep the bridge bound to `127.0.0.1`; never add a
generic command-execution endpoint or wildcard CORS.

The launcher default must be `graph-view.html`, which combines local search, full-document preview,
links/backlinks, and `/ask` AI chat. Continue building and serving `constellation.html` as an
optional visual-exploration view, reachable by replacing the filename in the localhost URL.

Never ask users to paste API keys into chat. Provider setup must run through
`configure-provider.bat`/`tools/configure_provider.py` with hidden input. Local search stays
offline; `/ask` may send only capped top-ranked excerpts to the explicitly selected provider.
Cross-provider fallback must remain opt-in.

Do not read key values from `.env`, environment dumps, registry output, or tool output while guiding
setup, and never expose a key in agent output. The HTML must not collect keys. If AI is unconfigured,
keep HTML and local search working and show the local setup commands instead.

For manual PowerShell guidance, use placeholders only:

```powershell
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "<YOUR_API_KEY>", "User")
```

Warn that this form can leave the real key in PowerShell history and that Windows User environment
variables are plaintext registry values readable by same-user processes. Prefer the hidden-input
configurator. After User env changes, advise restarting Cursor, terminals, and agent processes.
For sensitive keys, suggest a permission-restricted workspace `.env` or an OS credential store.
`LLMWIKI_AI_ENABLED=0` must remain available to force local-only operation.

## Public-package boundary

Only reusable code, empty templates, and synthetic/public examples belong in this repository.
Never copy user workspace data into the package, including `raw/sources`, `raw/extracted`,
generated `wiki` content/HTML, `.llmwiki` manifests/logs/state, document hashes, personal
absolute paths, organization-specific names, API keys, or tokens.
