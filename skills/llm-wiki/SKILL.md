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
이 설치는 **에이전트가 스킬을 찾게 하는 작업**일 뿐이다. 개인 문서를 가져가거나 Wiki
workspace를 만들거나 API 키를 생성·설정하지 않는다. workspace bootstrap과 공급자
설정은 사용자가 지정한 workspace 안에서 별도로 수행한다.

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

### 1-D. 검색 모드 온보딩 게이트 (bootstrap 직후 반드시 질문)

다음 단계로 넘어가기 전에 반드시 묻는다:

> 로컬 키워드 검색만 사용할까요, 아니면 LLM 기반 AI 검색/질문도 사용할까요?

- **로컬 검색만**: API 키가 필요 없고 문서가 외부로 전송되지 않는다. 키 설정을
  요구하지 말고 `start-llm-wiki.bat` 실행을 안내한다.
- **AI 검색도 사용**: 로그인된 Claude CLI 또는 아래 API 공급자 키가 1개 이상
  필요하다. 검색 상위 문맥만 선택 공급자로 전송됨을 먼저 알린다.
- 사용자가 선택하지 않았거나 로컬 검색을 골랐다면 AI 키 설정을 강제하지 않는다.

AI 검색을 선택한 경우 다음 중 하나를 고르게 한다:

A. **Claude CLI 로그인 사용** — 별도 API 키 불필요
B. **workspace `.env`에 저장** — 기본 권장, 해당 workspace에만 적용
C. **Windows 사용자 환경변수에 저장** — 사용자 레지스트리 평문이며 동일 사용자
프로세스가 읽을 수 있음을 고지

API 공급자는 OpenRouter/OpenAI/Gemini/Anthropic 중 필요한 것 하나 또는 여러 개를
설정할 수 있다. 여러 키를 요구하지 않는다. 기본 설정 방법:

```bash
"<wiki-root>/configure-provider.bat"
# 또는
python "<wiki-root>/tools/configure_provider.py" --root "<wiki-root>"
```

`getpass` 숨김 입력을 쓰는 위 방법을 우선 안내한다. **API 키를 채팅창에 절대
붙여넣지 말라고 명확히 말한다. 에이전트는 키 값을 요청하거나 읽지 않고, 파일 읽기·
환경 출력·도구 출력으로 키를 노출하지 않는다.** 사용자가 직접 로컬 설정 도구에 입력한다.

PowerShell 수동 등록은 요청받은 경우에만 플레이스홀더로 안내한다:

```powershell
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "<YOUR_API_KEY>", "User")
```

이 방식은 실제 키가 PowerShell 명령 기록에 남을 수 있고 Windows User 환경변수도
평문 레지스트리에 저장된다. 실제 키를 대화나 예시 명령에 넣지 않는다. 등록 후에는
새 값이 반영되도록 Cursor, 터미널, 에이전트 프로세스를 재시작하도록 안내한다.
민감 키는 workspace `.env`의 접근 권한을 제한하거나 OS credential store 사용을
고려하게 한다.

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
4. 로컬 검색·전문 미리보기·링크/역링크·AI 채팅이 있는 `graph-view.html`을 기본 브라우저로 열기

`constellation.html`은 전체 지식 지형을 둘러보는 보조 시각화로 계속 생성·서빙한다.
실행 중인 localhost 주소에서 파일명만 `constellation.html`로 바꿔 접근할 수 있다.

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
python "<wiki-root>/tools/configure_provider.py" --root "<wiki-root>"
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
특히 Windows User 환경변수는 동일 사용자 프로세스가 읽을 수 있는 평문 레지스트리에
저장된다. 민감 자료는 `LLMWIKI_AI_ENABLED=0`으로 AI 전송을 끄고 로컬 검색만 사용한다.

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
