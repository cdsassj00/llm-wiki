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

당신(코딩 에이전트)이 **컴파일러**다. 인제스트·컴파일은 현재 하네스에서 직접
수행한다. 브라우저 질의용 AI는 별도 localhost 브릿지이며 명시적으로 설정한 경우만 쓴다.

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

bootstrap은 workspace용 `tools/`, `start-llm-wiki.bat`/`.ps1`,
`configure-provider.bat`도 배치한다.
이미 purpose.md/schema.md가 있으면 덮어쓰지 말고 도구만 업데이트한다:

```bash
python $SCRIPTS/setup_workspace.py "<wiki-root>"
```

## 2. 인제스트 (원본 보관 + 텍스트 추출)

```bash
python "<wiki-root>/tools/ingest.py" --root "<wiki-root>" "<문서폴더>" --link hardlink
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

## 4. 색인 + 원클릭 실행

```bash
python "<wiki-root>/tools/reindex.py" --root "<wiki-root>"
python "<wiki-root>/tools/launch_wiki.py" --root "<wiki-root>"
```

Windows에서는 `<wiki-root>/start-llm-wiki.bat`을 더블클릭해도 된다. 런처는:

1. `graph-view.html`/`constellation.html`이 없으면 생성
2. 기존 `/health`와 PID를 확인해 중복 실행 방지
3. 충돌이 없는 포트에서 `127.0.0.1` 전용 브릿지 시작
4. 검색 중심 `constellation.html`을 기본 브라우저로 열기

브라우저 HTML 자체는 보안 제약상 Python 프로세스를 시작할 수 없다. 반드시 workspace
런처를 사용한다. 종료:

```bash
python "<wiki-root>/tools/launch_wiki.py" --root "<wiki-root>" --stop
```

브릿지는 임의 명령 실행 endpoint를 제공하지 않는다. `/search`는 항상 로컬이다.
`/ask`는 `LLMWIKI_AI_ENABLED=1`일 때만 제한된 상위 5개 발췌(총 12KiB 이하)를
선택한 AI에 전달한다.

AI 설정은 사용자의 **로컬 터미널**에서만 한다. 키를 채팅에 요청하거나 코드·문서·URL·
명령행 인자에 넣지 않는다:

```bash
python "<wiki-root>/tools/configure_provider.py"
```

Windows는 `<wiki-root>/configure-provider.bat`을 더블클릭해도 된다. 선택지:

- `claude-cli`: 설치·로그인된 Claude CLI 사용, 별도 API 키 불필요
- `openrouter|openai|gemini|anthropic`: 해당 키 하나만 있어도 사용 가능
- 저장: workspace `.env`(기본 권장), Windows 사용자 환경변수, 저장 없는 1회 실행

`LLMWIKI_PROVIDER=auto|claude-cli|openrouter|openai|gemini|anthropic`. `auto` 우선순위는
Claude CLI → OpenRouter → OpenAI → Gemini → Anthropic이며, 선택 후 오류가 나도 기본은
다른 공급자로 문맥을 보내지 않는다. 공급자 간 fallback은 사용자가
`LLMWIKI_ALLOW_PROVIDER_FALLBACK=1`로 명시한 경우만 허용한다.

`.env`와 Windows 사용자 환경변수는 평문이므로 workspace/OS 계정 접근 권한을 제한한다.
민감 자료는 `LLMWIKI_AI_ENABLED=0`으로 AI 전송을 끄고 로컬 검색만 사용한다.

## 5. 질의 모드

이미 위키가 있으면: `wiki/index.md` → Grep → `[[링크]]` 따라가기. 못 찾으면 솔직히 말하고 catalog/extracted 가능성을 안내.

## 원칙

- `raw/sources/` 불변
- 한국어, 한 페이지 한 주제, 병합(덮어쓰기 금지)
- 불확실 → `> ⚠️ 검토 필요:`
- 다른 에이전트가 같은 위키 작업 중이면 컴파일 중단
- 공개 스킬에는 코드·빈 템플릿·프리셋만 둔다.
- 개인 문서와 생성 데이터(`raw/sources`, `raw/extracted`, `wiki`, `.llmwiki`,
  manifest, 절대 개인 경로)는 사용자 workspace에만 두고 공개 저장소로 복사하지 않는다.

## npx 설치 (사용자용)

```bash
npx skills add cdsassj00/llm-wiki -g -a '*' -y
```
