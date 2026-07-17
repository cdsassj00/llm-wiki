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
