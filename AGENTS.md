# Agent notes

This repository publishes the **llm-wiki** skill for the [skills](https://skills.sh/) CLI.

```bash
npx skills add cdsassj00/llm-wiki -g -a '*' -y
```

When the skill is attached as a folder (not yet installed), run:

```bash
python skills/llm-wiki/scripts/ensure_agents_install.py
```

Follow `skills/llm-wiki/SKILL.md` end-to-end: ask for doc path → ontology preset → bootstrap → ingest → compile → 3D graph.

For a blank folder, `bootstrap_wiki.py` must also install the managed workspace tools and
`start-llm-wiki.bat`/`.ps1` and `configure-provider.bat`. For an existing workspace, use
`setup_workspace.py`; do not run bootstrap over existing `purpose.md` or `schema.md`.

The browser cannot launch Python. The OS/Python launcher starts the bridge, verifies `/health`,
builds missing HTML, and opens the browser. Keep the bridge bound to `127.0.0.1`; never add a
generic command-execution endpoint or wildcard CORS.

Never ask users to paste API keys into chat. Provider setup must run through
`configure-provider.bat`/`tools/configure_provider.py` with hidden input. Local search stays
offline; `/ask` may send only capped top-ranked excerpts to the explicitly selected provider.
Cross-provider fallback must remain opt-in.

## Public-package boundary

Only reusable code, empty templates, and synthetic/public examples belong in this repository.
Never copy user workspace data into the package, including `raw/sources`, `raw/extracted`,
generated `wiki` content/HTML, `.llmwiki` manifests/logs/state, document hashes, personal
absolute paths, organization-specific names, API keys, or tokens.
