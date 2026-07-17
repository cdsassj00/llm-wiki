# llm-wiki

Karpathy-style **LLM Wiki** one-stop skill for coding agents.

문서 폴더 → 온톨로지 합의 → ingest → 위키 컴파일 → **3D 그래프 HTML** 실행.

## Install (npx skills)

```bash
npx skills add cdsassj00/llm-wiki -g -a '*' -y
```

설치 위치: `~/.agents/skills/llm-wiki` (에이전트 공용)

또는 레포 클론 후:

```bash
python skills/llm-wiki/scripts/ensure_agents_install.py
pip install -r skills/llm-wiki/assets/requirements.txt
```

## Usage (에이전트에게)

- "이 폴더로 LLM 위키 만들어줘"
- "/llm-wiki"
- "문서 정리해서 3D 그래프까지"

에이전트가 경로·온톨로지 프리셋을 물은 뒤 자동으로 진행한다.

## Manual CLI

```bash
# 1) workspace
python skills/llm-wiki/scripts/bootstrap_wiki.py ./my-wiki --preset lecture --title "My Lectures"

# 2) ingest
python skills/llm-wiki/scripts/ingest.py --root ./my-wiki "/path/to/docs" --link hardlink

# 3) (agent compiles wiki/*.md)

# 4) index + 3D graph
python skills/llm-wiki/scripts/reindex.py --root ./my-wiki
python skills/llm-wiki/scripts/open_graph.py --root ./my-wiki --build
```

### Presets

| preset | 용도 |
|--------|------|
| `lecture` | 강의안·교재 |
| `research` | 논문·노트 |
| `project` | 코딩 프로젝트 |
| `mixed` | 혼합 (default) |

## Requirements

- Python 3.10+
- `pip install -r skills/llm-wiki/assets/requirements.txt` (markitdown)
- Optional: LibreOffice for `.hwp` / `.hwpx` / legacy Office

## Layout

```
skills/llm-wiki/
  SKILL.md          # agent instructions
  scripts/          # bootstrap, ingest, reindex, graph
  references/       # ontology + compile checklist
  assets/           # requirements.txt
```

## License

MIT
