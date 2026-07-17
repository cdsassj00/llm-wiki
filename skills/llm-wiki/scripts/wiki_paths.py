#!/usr/bin/env python3
"""Wiki workspace root 탐지.

우선순위:
1. --root CLI (호출 측에서 처리)
2. 환경변수 LLMWIKI_ROOT
3. cwd부터 위로 purpose.md + schema.md 가 있는 폴더
4. cwd (bootstrap 직후)
"""
from __future__ import annotations

import os
from pathlib import Path


def looks_like_wiki(path: Path) -> bool:
    return (path / "purpose.md").is_file() and (path / "schema.md").is_file()


def find_wiki_root(explicit: str | Path | None = None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not looks_like_wiki(root):
            raise SystemExit(
                f"Wiki root 아님 (purpose.md/schema.md 없음): {root}\n"
                "먼저 bootstrap_wiki.py 를 실행하세요."
            )
        return root

    env = os.environ.get("LLMWIKI_ROOT")
    if env:
        root = Path(env).expanduser().resolve()
        if looks_like_wiki(root):
            return root
        raise SystemExit(f"LLMWIKI_ROOT 가 wiki가 아님: {root}")

    cur = Path.cwd().resolve()
    for cand in [cur, *cur.parents]:
        if looks_like_wiki(cand):
            return cand

    raise SystemExit(
        "Wiki workspace를 찾지 못했습니다.\n"
        "  - 작업 폴더에서 실행하거나\n"
        "  - LLMWIKI_ROOT 를 설정하거나\n"
        "  - --root <경로> 를 주세요.\n"
        "없으면: python scripts/bootstrap_wiki.py <새폴더>"
    )
