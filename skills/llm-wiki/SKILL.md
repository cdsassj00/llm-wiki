---
name: llm-wiki
description: >
  Karpathy 스타일 LLM Wiki 원스톱 스킬. 문서 폴더를 받아 온톨로지(분류 체계)를
  사용자와 합의하고, ingest→위키 컴파일→index/overview→3D 그래프 HTML까지
  한 번에 만든다. "위키 만들어", "문서 정리해서 위키", "LLM Wiki", "지식 그래프",
  "3D 그래프뷰", "이 폴더 위키로", "카탈로그/컴파일" 요청 시 사용. 스킬이 첨부만
  된 경우 ~/.agents/skills 에 자동 설치한 뒤 워크플로를 진행한다.
---

# LLM Wiki 원스톱

당신(에이전트)이 **컴파일러**다. 외부 LLM API를 부르지 말고 직접 정리한다.

## 0. 설치 보장 (첨부만 받은 경우 필수)

스킬 경로에 `SKILL.md`가 보이면, **본 작업 전에** 전역 설치를 확인한다.

```bash
python "<이-스킬>/scripts/ensure_agents_install.py"
```

결과: `~/.agents/skills/llm-wiki/` 복사 + (가능하면) `~/.claude/skills/llm-wiki` 정션.

이미 `npx skills add cdsassj00/llm-wiki -g -y` 로 설치된 경우 이 단계는 스킵 가능.

의존성(최초 1회):

```bash
pip install -r "<이-스킬>/assets/requirements.txt"
```

스크립트 기준 경로: 스킬 루트의 `scripts/` (아래 명령의 `$SCRIPTS`).

## 1. 사용자에게 묻기 (반드시 순서대로)

### 1-A. 문서 폴더
> 어떤 폴더의 문서를 위키로 만들까요? 절대 경로를 알려 주세요.

경로를 받으면 존재·하위 문서 대략 개수(지원 확장자)를 짧게 보고한다.

### 1-B. Wiki workspace 위치
> 위키 저장소를 어디에 둘까요? (예: `C:\wiki\my-topic` 또는 현재 프로젝트 하위 `./llmwiki`)

없으면 bootstrap으로 새로 만든다.

### 1-C. 온톨로지 프리셋 (추천 후 승인)
`references/ontology-presets.md` 를 읽고, 폴더 이름·샘플 파일명으로 **추천 1개**를 고른 뒤 사용자에게 확인한다.

| preset | 언제 |
|--------|------|
| `lecture` | 강의안·교재·교육 |
| `research` | 논문·노트·리서치 |
| `project` | 코딩 프로젝트 폴더들 |
| `mixed` | 섞여 있음 (기본 추천) |

승인된 preset으로:

```bash
python $SCRIPTS/bootstrap_wiki.py "<wiki-root>" --preset <preset> --title "<제목>"
```

이미 purpose.md/schema.md 가 있으면 bootstrap 생략, 기존 규칙을 따른다.

## 2. 인제스트 (원본 보관 + 텍스트 추출)

```bash
python $SCRIPTS/ingest.py --root "<wiki-root>" "<문서폴더>" --link hardlink
```

- 중복은 sha256 스킵
- 결과는 `raw/extracted/*.md`, 상태는 `.llmwiki/manifest.json` 의 `extracted`
- 대량이면 배치·우선순위(pptx/pdf 우선, 계약서류 제외)를 제안하고 사용자 확인

## 3. 위키 컴파일 (당신이 직접)

`purpose.md` + `schema.md` 를 읽는다. `status: extracted` 항목을 처리한다.

각 문서:
1. `raw/extracted/...` 읽고 개념·개체·요약·기존 페이지 연결점 정리
2. `schema.md` 폴더 규칙대로 페이지 생성/병합 (`[[title]]` 링크)
3. `wiki/log.md` 한 줄 추가
4. manifest → `compiled` + `compiled_at`

대량이면:
- 상위 폴더당 `wiki/catalog/` 가벼운 표 먼저
- 핵심 문서만 `wiki/sources/` + `concepts/` 심화
- 나머지는 extracted 대기열로 두고 log에 명시

상세 체크리스트: `references/compile-checklist.md`

## 4. 색인 + 3D 그래프 + 실행

```bash
python $SCRIPTS/reindex.py --root "<wiki-root>"
python $SCRIPTS/build_graph_view.py --root "<wiki-root>"
python $SCRIPTS/open_graph.py --root "<wiki-root>"
```

`wiki/graph-view.html` 이 브라우저로 열린다. 사용자에게 경로를 알려 준다.

## 5. 질의 모드

이미 위키가 있으면: `wiki/index.md` → Grep → `[[링크]]` 따라가기. 못 찾으면 솔직히 말하고 catalog/extracted 가능성을 안내.

## 원칙

- `raw/sources/` 불변
- 한국어, 한 페이지 한 주제, 병합(덮어쓰기 금지)
- 불확실 → `> ⚠️ 검토 필요:`
- 다른 에이전트가 같은 위키 작업 중이면 컴파일 중단

## npx 설치 (사용자용)

```bash
npx skills add cdsassj00/llm-wiki -g -a '*' -y
```
