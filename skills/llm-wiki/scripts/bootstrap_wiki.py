#!/usr/bin/env python3
"""빈 폴더에 LLM Wiki workspace를 부트스트랩한다."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from setup_workspace import install_tools

TODAY = date.today().isoformat()

PRESETS = {
    "lecture": {
        "label": "강의안·교육 자료",
        "purpose": """# 이 위키의 목적 (purpose.md)

## 목적
강의안·교재·교육 자료를 검색 가능한 위키로 정리한다.

## 검색 계약 — 반드시 답해야 하는 질문
1. **"이런 주제를 어디서 가르쳤지?"** → `wiki/concepts/` 의 `sources:` + `wiki/curriculum/` + `wiki/catalog/`
2. **"이 개념을 어떻게 설명했지?"** → `wiki/concepts/` 본문 + `wiki/methods/` + `wiki/messages/`
3. **"어떤 기관·과정에서 썼지?"** → `wiki/entities/` + `wiki/sources/` + `wiki/catalog/`

## 강조 / 무시
- 강조: 설명 방식·비유·커리큘럼 구조·원본 경로
- 무시: 계약서류·광고 문구·반복 상용구
""",
        "schema": """# 위키 구조 규칙 (schema.md)

## 폴더
- `wiki/sources/` — 원본 문서 요약 (type: source)
- `wiki/concepts/` — 이론·기법·용어 (type: concept)
- `wiki/curriculum/` — 과정·트랙·모듈 지도 (type: curriculum)
- `wiki/messages/` — 반복 핵심 주장 (type: message)
- `wiki/methods/` — 설명·수업 방법론 (type: method)
- `wiki/practices/` — 실습·과제 패턴 (type: practice)
- `wiki/entities/` — 사람·조직·제품 (type: entity)
- `wiki/catalog/` — 대량 원본의 가벼운 폴더 카탈로그 (type: catalog)
- `wiki/queries/` — 질의 정리 (type: query)

## 작성 규칙
1. frontmatter: type, title, sources, created, updated
2. 페이지 간 참조는 `[[페이지 제목]]` 위키링크 (title 값과 일치)
3. 한 페이지 = 한 주제. 기존 페이지는 덮어쓰지 말고 병합
4. 불확실하면 `> ⚠️ 검토 필요: …`
5. 한국어 작성
""",
        "folders": [
            "sources", "concepts", "curriculum", "messages", "methods",
            "practices", "entities", "catalog", "queries",
        ],
    },
    "research": {
        "label": "연구·논문·노트",
        "purpose": """# 이 위키의 목적 (purpose.md)

## 목적
논문·노트·리서치를 상호 연결된 지식 그래프로 정리한다.

## 검색 계약
1. **"이 개념의 정의·관련 연구는?"** → `wiki/concepts/`
2. **"누가/어느 기관이?"** → `wiki/entities/`
3. **"원문 근거는?"** → `wiki/sources/`

## 강조 / 무시
- 강조: 주장·근거·반례·방법론·인용 경로
- 무시: 포맷팅 잡음
""",
        "schema": """# 위키 구조 규칙 (schema.md)

## 폴더
- `wiki/sources/` — 논문·노트 요약 (type: source)
- `wiki/concepts/` — 이론·용어 (type: concept)
- `wiki/methods/` — 연구·분석 방법 (type: method)
- `wiki/entities/` — 저자·기관·데이터셋 (type: entity)
- `wiki/catalog/` — 폴더/콜렉션 카탈로그 (type: catalog)
- `wiki/queries/` — 질의 정리 (type: query)

## 작성 규칙
1. frontmatter: type, title, sources, created, updated
2. `[[페이지 제목]]` 위키링크
3. 병합(덮어쓰기 금지), 한국어, 검토 항목 표기
""",
        "folders": ["sources", "concepts", "methods", "entities", "catalog", "queries"],
    },
    "project": {
        "label": "코딩 프로젝트·산출물",
        "purpose": """# 이 위키의 목적 (purpose.md)

## 목적
로컬 코딩 프로젝트와 산출물을 스택·용도·패턴으로 찾아쓰게 한다.

## 검색 계약
1. **"이 프로젝트 무슨 스택?"** → `wiki/projects/` 의 **종류/스택:** 줄
2. **"왜 만들었지?"** → `wiki/purpose/`
3. **"어떻게 만들었지?"** → `wiki/pattern/`

## 강조 / 무시
- 강조: 스택, 진입점, 재사용 패턴, 원본 폴더 경로
- 무시: node_modules·빌드 산출물 나열
""",
        "schema": """# 위키 구조 규칙 (schema.md)

## 폴더
- `wiki/projects/` — 프로젝트 1페이지 (type: project). 본문에 **종류/스택:** 필수
- `wiki/purpose/` — 용도·도메인 지도 (type: purpose)
- `wiki/pattern/` — 구현 패턴 지도 (type: pattern)
- `wiki/concepts/` — 공유 기술 개념 (type: concept)
- `wiki/entities/` — 도구·서비스 (type: entity)
- `wiki/sources/` — 문서/README 요약 (type: source)
- `wiki/queries/` — 질의 (type: query)

## 작성 규칙
1. frontmatter: type, title, sources, created, updated
2. `[[페이지 제목]]` 위키링크
3. 병합, 한국어
""",
        "folders": [
            "projects", "purpose", "pattern", "concepts",
            "entities", "sources", "queries",
        ],
    },
    "mixed": {
        "label": "혼합(강의+프로젝트+연구)",
        "purpose": """# 이 위키의 목적 (purpose.md)

## 목적
강의 자료와 코딩 산출물·리서치를 한 위키에서 검색한다.

## 검색 계약
1. 강의 주제 → `concepts/` + `curriculum/` + `catalog/`
2. 프로젝트 스택 → `projects/` (**종류/스택:**)
3. 설명 방식 → `methods/` + `messages/`

## 강조 / 무시
- 강조: 원본 경로, 스택, 설명 방식
- 무시: 계약서류·빌드 잡음
""",
        "schema": """# 위키 구조 규칙 (schema.md)

## 폴더 (3그룹)
### 강의
- sources, concepts, curriculum, messages, methods, practices, catalog
### 세계관
- entities, projects, purpose, pattern
### 대기열
- queries

## 작성 규칙
1. frontmatter: type, title, sources, created, updated
2. `[[페이지 제목]]` 위키링크 (title과 일치)
3. 병합·한국어·검토 항목
""",
        "folders": [
            "sources", "concepts", "curriculum", "messages", "methods",
            "practices", "entities", "projects", "purpose", "pattern",
            "catalog", "queries",
        ],
    },
}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n") if text.startswith("\n") else text, "utf-8")


def bootstrap(root: Path, preset: str, title: str) -> None:
    if preset not in PRESETS:
        raise SystemExit(f"unknown preset: {preset}. choose: {', '.join(PRESETS)}")
    cfg = PRESETS[preset]
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    write(root / "purpose.md", cfg["purpose"])
    write(root / "schema.md", cfg["schema"])
    write(root / ".llmwiki" / "manifest.json", "[]\n")
    write(
        root / ".llmwiki" / "config.json",
        json.dumps(
            {
                "title": title,
                "preset": preset,
                "preset_label": cfg["label"],
                "created": TODAY,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    for name in ("sources", "extracted"):
        (root / "raw" / name).mkdir(parents=True, exist_ok=True)

    wiki = root / "wiki"
    for folder in cfg["folders"]:
        (wiki / folder).mkdir(parents=True, exist_ok=True)

    write(
        wiki / "log.md",
        f"# 작업 로그 (log.md)\n\n- {TODAY} — workspace bootstrap (preset={preset})\n",
    )
    write(
        wiki / "index.md",
        f"# 색인 (Index)\n\n> bootstrap · {TODAY}\n\n_아직 페이지 없음. ingest 후 컴파일하세요._\n",
    )
    write(
        wiki / "overview.md",
        f"# 개요 (Overview)\n\n**{title}** · preset `{preset}` ({cfg['label']})\n",
    )
    installed = install_tools(root)

    print(f"bootstrap OK: {root}")
    print(f"  preset={preset} ({cfg['label']})")
    print(f"  folders={', '.join(cfg['folders'])}")
    print(
        f"  managed tools={len(installed)} + start-llm-wiki.bat/.ps1 "
        "+ configure-provider.bat"
    )
    print("선택: configure-provider.bat으로 AI 공급자를 로컬에서 설정")
    print("다음: python tools/ingest.py --root <wiki> <문서폴더> --link hardlink")


def main() -> int:
    ap = argparse.ArgumentParser(description="LLM Wiki workspace bootstrap")
    ap.add_argument("path", help="새 wiki workspace 경로")
    ap.add_argument(
        "--preset",
        default="mixed",
        choices=list(PRESETS),
        help="온톨로지 프리셋",
    )
    ap.add_argument("--title", default="My LLM Wiki", help="위키 제목")
    ap.add_argument("--list-presets", action="store_true")
    args = ap.parse_args()
    if args.list_presets:
        for k, v in PRESETS.items():
            print(f"{k}: {v['label']}")
        return 0
    bootstrap(Path(args.path), args.preset, args.title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
