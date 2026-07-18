# llm-wiki

Karpathy-style **LLM Wiki** one-stop skill for coding agents.

문서 폴더 → 온톨로지 합의 → ingest → 위키 컴파일 → **localhost 브릿지 + 3D 그래프 HTML** 원클릭 실행.

## Install (npx skills)

```bash
npx skills add cdsassj00/llm-wiki -g -a '*' -y
```

설치 위치: `~/.agents/skills/llm-wiki` (에이전트 공용)

이 명령은 에이전트가 스킬을 찾도록 **스킬 코드만 설치**합니다. 개인 문서를 읽거나
복사하지 않고, Wiki workspace나 API 키도 만들지 않습니다. `ensure_agents_install.py`
역시 같은 설치 작업입니다. 실제 workspace bootstrap과 AI 설정은 이후 사용자가 지정한
로컬 workspace에서만 수행됩니다.

또는 레포 클론 후:

```bash
python skills/llm-wiki/scripts/ensure_agents_install.py
pip install -r skills/llm-wiki/assets/requirements.txt
```

## Usage (에이전트에게)

- "이 폴더로 LLM 위키 만들어줘"
- "/llm-wiki"
- "문서 정리해서 3D 그래프까지"

에이전트가 경로·온톨로지 프리셋을 물은 뒤 검색 모드를 확인하고 진행합니다.

## 처음 설치부터 실행까지

1. 위 명령으로 공개 스킬을 설치합니다.
2. 에이전트에게 “빈 폴더에 이 문서들로 위키를 만들어줘”라고 요청합니다.
3. 에이전트가 문서 폴더, Wiki workspace, 온톨로지 프리셋을 확인하고 bootstrap합니다.
4. 다음 질문에 답합니다.
   > 로컬 키워드 검색만 사용할까요, 아니면 LLM 기반 AI 검색/질문도 사용할까요?
5. **로컬 검색만** 선택하면 키 설정 없이 `start-llm-wiki.bat`을 실행합니다. 문서는
   외부로 전송되지 않습니다.
6. **AI 검색도 사용**하면 다음 중 하나를 선택합니다.
   - Claude CLI 로그인: 별도 API 키 불필요
   - workspace `.env`: 권장, 해당 workspace에만 적용
   - Windows 사용자 환경변수: 사용자 레지스트리 평문 저장 한계가 있음
7. OpenRouter/OpenAI/Gemini/Anthropic 중 사용할 공급자 하나 이상을 설정합니다. 모든
   키를 요구하지 않으며, 공급자 하나만으로 충분합니다.
8. `start-llm-wiki.bat`을 실행합니다. provider가 없어도 HTML과 로컬 검색은 정상
   실행되며, AI 버튼은 브라우저에서 키를 받는 대신 로컬 설정 방법을 보여줍니다.

기본 실행 화면은 `graph-view.html`입니다. 로컬 검색, 문서 전문 미리보기, 링크·역링크,
AI 채팅(`/ask`)을 한 화면에서 제공합니다. `constellation.html`은 같은 localhost
브릿지에서 계속 제공되는 전체 지식 지형용 보조 시각화이며, 실행 주소의 파일명만
`constellation.html`로 바꿔 열 수 있습니다.

## Manual CLI

```bash
# 1) 빈 폴더에 workspace + tools + 원클릭 런처 생성
python skills/llm-wiki/scripts/bootstrap_wiki.py ./my-wiki --preset lecture --title "My Lectures"

# 2) ingest
python ./my-wiki/tools/ingest.py --root ./my-wiki "/path/to/docs" --link hardlink

# 3) (agent compiles wiki/*.md)

# 4) index + bridge + 기본 graph-view
python ./my-wiki/tools/reindex.py --root ./my-wiki
python ./my-wiki/tools/launch_wiki.py --root ./my-wiki
```

선택적으로 브라우저 AI 답변을 켜려면 Windows에서
`my-wiki/configure-provider.bat`을 먼저 더블클릭합니다. 키는 숨김 입력되며 채팅이나
명령행 인자에 넣지 않습니다. 이후 `my-wiki/start-llm-wiki.bat`을 더블클릭하면
실행됩니다.
PowerShell 실행 정책의 영향을 피하려면 `.bat`을 사용하세요. `.bat`은 Python 런처를
호출하므로 경로에 공백이 있어도 안전하게 인용됩니다.

기존 workspace의 도구와 런처만 업데이트:

```bash
python skills/llm-wiki/scripts/setup_workspace.py ./existing-wiki
```

종료:

```bash
python ./my-wiki/tools/launch_wiki.py --root ./my-wiki --stop
```

## One-click 동작과 보안

- HTML 버튼만으로 로컬 Python 프로세스를 시작할 수는 없습니다. OS 런처
  (`start-llm-wiki.bat`/`.ps1`)가 브릿지를 먼저 시작하고 HTML을 엽니다.
- 브릿지는 `127.0.0.1`에만 바인딩되며 `/health`, `/search`, `/ask`, `/export`와
  `wiki/` 정적 파일만 제공합니다. 임의 shell 명령 endpoint는 없습니다.
- 포트가 다른 프로그램과 충돌하면 다음 빈 포트를 찾고, 같은 workspace 브릿지가 이미
  응답하면 새 프로세스를 만들지 않습니다.
- 브라우저 HTML은 Cursor/Claude/Codex 하네스 세션에 자동 접속할 수 없습니다.
  브릿지는 설치·로그인된 Claude CLI를 고정 인자로 호출하거나, 사용자가 선택한 API를
  직접 호출합니다. CLI 경로는 별도 API 키가 필요 없지만 Claude CLI 로그인이 필요합니다.
- 직접 API는 OpenRouter, OpenAI, Gemini, Anthropic 4개를 모두 지원합니다. 모든 키가
  필요한 것은 아니며 사용할 공급자 하나만 설정하면 됩니다.
- AI는 `LLMWIKI_AI_ENABLED=1`일 때만 동작합니다. 기본 로컬 검색은 외부 전송이 없고,
  AI 질문 때만 검색 상위 5개 문서의 발췌(총 12KiB 이하)가 선택 공급자에 전송됩니다.
- 로그와 PID 상태는 workspace의 `.llmwiki/bridge.log`,
  `.llmwiki/bridge.json`에 저장됩니다.

Bridge API:

- `GET /health` — PID·fingerprint·선택 provider/model·키 설정 여부(`****`만 표시)
- `POST /search` `{"question":"..."}` — LLM 호출 없는 로컬 위키 검색
- `POST /ask` `{"question":"..."}` — 제한된 검색 문맥을 선택한 CLI/API에 전달
- `POST /export` — 질의를 `wiki/queries` 또는 `.llmwiki/handoffs` 아래에만 저장

### AI 공급자 설정

```bash
python ./my-wiki/tools/configure_provider.py --root ./my-wiki
```

환경 변수:

- `LLMWIKI_PROVIDER=auto|claude-cli|openrouter|openai|gemini|anthropic`
- `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`(`GOOGLE_API_KEY` 호환),
  `ANTHROPIC_API_KEY`
- `LLMWIKI_MODEL` 또는 `OPENROUTER_MODEL`, `OPENAI_MODEL`, `GEMINI_MODEL`,
  `ANTHROPIC_MODEL`
- `LLMWIKI_AI_ENABLED=0|1`, `LLMWIKI_ALLOW_PROVIDER_FALLBACK=0|1`

`auto`는 Claude CLI → OpenRouter → OpenAI → Gemini → Anthropic 순으로 처음 설정된
공급자 하나를 선택합니다. 요청 실패 시 다른 공급자로 자동 전송하지 않습니다.
`LLMWIKI_ALLOW_PROVIDER_FALLBACK=1`은 문서 문맥이 다른 공급자로 넘어갈 수 있음을 이해한
사용자만 켜야 합니다.

기본 모델은 비용과 응답 속도를 고려해 OpenRouter `openai/gpt-5.4-mini`, OpenAI
`gpt-5.4-mini`, Gemini `gemini-3.5-flash`, Anthropic `claude-sonnet-5`입니다.
공급자 계정에서 사용할 수 없으면 모델 환경 변수로 변경하며 오류 메시지에 공급자 상태를
확인합니다.

설정 도구의 기본 권장은 workspace `.env`입니다. `.env`는 gitignored되고 런처는
허용된 `KEY=VALUE`만 문자 그대로 읽어 실행·확장하지 않습니다. 그러나 평문 파일이므로
workspace 파일 권한을 제한하세요. Windows 사용자 환경변수도 사용자 레지스트리에
평문으로 저장되어 같은 사용자 프로세스가 읽을 수 있습니다. 이미 열린 앱에는 즉시
반영되지 않을 수 있으며 런처는 레지스트리를 직접 읽어 이를 보완합니다.

#### PowerShell과 키 보안

가장 안전한 기본 흐름은 다음 숨김 입력 도구입니다.

```powershell
.\my-wiki\configure-provider.bat
# 또는
python .\my-wiki\tools\configure_provider.py --root .\my-wiki
```

**API 키를 Cursor/Claude/Codex 채팅창, 브라우저 AI 질문창, URL 또는 명령행 인자에
붙여넣지 마세요.** 에이전트에게 키 값을 알려주지 말고 위 설정 도구의 `getpass` 숨김
입력에 사용자가 직접 입력해야 합니다.

수동 Windows User 환경변수 등록도 가능하지만 아래처럼 **플레이스홀더만** 사용해
작성해야 합니다.

```powershell
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "<YOUR_API_KEY>", "User")
```

실제 키를 위 명령에 직접 쓰면 PowerShell 명령 기록에 남을 수 있습니다. Windows User
환경변수는 동일 사용자 프로세스가 읽을 수 있는 평문 레지스트리 값입니다. 등록 후 새
Cursor, 터미널, 에이전트 프로세스를 시작해야 일반적으로 반영됩니다. 민감 키는 접근
권한을 제한한 workspace `.env` 또는 OS credential store를 고려하세요.

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
  scripts/          # bootstrap, ingest, graph, bridge, launcher
  references/       # ontology + compile checklist
  assets/           # requirements.txt
```

## Privacy / 공개 범위

공개 저장소에는 재사용 가능한 코드, 빈 템플릿, 온톨로지 프리셋만 포함합니다.
사용자의 원문과 추출·컴파일 결과는 해당 workspace에만 저장합니다.

- 로컬 검색은 외부 전송이 없습니다.
- AI 검색은 검색 상위 5개 문서의 제한된 발췌(총 12KiB 이하)만 사용자가 선택한
  공급자로 전송합니다.
- `LLMWIKI_AI_ENABLED=0`으로 AI 전송을 명시적으로 끌 수 있습니다.
- Windows User 환경변수는 동일 사용자 프로세스가 읽을 수 있는 평문 레지스트리
  저장소입니다.

공개 배포에서 제외되는 항목:

- `raw/sources/`, `raw/extracted/`
- 생성된 `wiki/` Markdown/HTML
- `.llmwiki/`의 manifest, config, PID, 로그, handoff
- 개인 절대 경로, 문서 본문, 파일 해시, API key/token

개인 workspace 자료를 공개 스킬 저장소로 복사하지 마세요. 예제가 필요하면
합성 데이터나 공개 샘플만 사용합니다.

## License

MIT
