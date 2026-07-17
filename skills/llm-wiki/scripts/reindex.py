#!/usr/bin/env python3
"""wiki/ 파일 트리로부터 index.md 와 overview.md 를 결정론적으로 재생성한다.

LLM 토큰을 쓰지 않는다. 컴파일 후 또는 페이지를 수동 편집한 뒤 실행한다.

사용법
  python tools/reindex.py
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from wiki_paths import find_wiki_root

ROOT: Path = Path()
WIKI: Path = Path()


def _bind_root(root: Path) -> None:
    global ROOT, WIKI
    ROOT = root
    WIKI = ROOT / "wiki"


def title_of(md: Path) -> str:
    text = md.read_text("utf-8", errors="replace")
    m = re.search(r"^---\n(.*?)\n---", text, re.DOTALL)
    if m:
        t = re.search(r"^title:\s*(.+)$", m.group(1), re.MULTILINE)
        if t:
            return t.group(1).strip().strip("\"'")
    h = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return h.group(1).strip() if h else md.stem


def pages(sub: str) -> list[tuple[str, Path]]:
    d = WIKI / sub
    if not d.is_dir():
        return []
    items = [(title_of(f), f) for f in d.glob("*.md")]
    return sorted(items, key=lambda x: x[0].lower())


SECTIONS = [
    ("curriculum", "강의 구조 (Curriculum)"),
    ("concepts", "개념 (Concepts)"),
    ("messages", "핵심 메시지 (Messages)"),
    ("methods", "방법론 (Methods)"),
    ("practices", "실습 (Practices)"),
    ("entities", "개체 (Entities)"),
    ("projects", "프로젝트 (Projects)"),
    ("purpose", "프로젝트 용도 (Purpose)"),
    ("pattern", "프로젝트 구현 패턴 (Pattern)"),
    ("sources", "출처 (Sources)"),
    ("catalog", "카탈로그 (Catalog)"),
    ("queries", "질의 (Queries)"),
]


def collect_sections() -> list[tuple[str, str, list[tuple[str, Path]]]]:
    return [(sub, label, pages(sub)) for sub, label in SECTIONS]


def write_index() -> None:
    sections = collect_sections()
    lines = ["# 색인 (Index)", "", f"> 자동 생성 · {datetime.now():%Y-%m-%d %H:%M}", ""]

    def section(label: str, items: list[tuple[str, Path]]) -> None:
        lines.append(f"## {label} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_없음_")
        else:
            lines.extend(f"- [[{t}]]" for t, _ in items)
        lines.append("")

    for _, label, items in sections:
        section(label, items)
    (WIKI / "index.md").write_text("\n".join(lines), "utf-8")


def write_overview() -> None:
    sections = collect_sections()
    counts = {sub: len(items) for sub, _, items in sections}
    concept_lines = [f"- [[{t}]]" for t, _ in pages("concepts")[:20]] or ["_없음_"]
    message_lines = [f"- [[{t}]]" for t, _ in pages("messages")[:20]] or ["_없음_"]
    method_lines = [f"- [[{t}]]" for t, _ in pages("methods")[:20]] or ["_없음_"]
    lines = [
        "# 개요 (Overview)", "",
        f"> 자동 갱신 · {datetime.now():%Y-%m-%d %H:%M}", "",
        " · ".join(
            [
                f"강의 구조 **{counts.get('curriculum', 0)}**",
                f"개념 **{counts.get('concepts', 0)}**",
                f"메시지 **{counts.get('messages', 0)}**",
                f"방법론 **{counts.get('methods', 0)}**",
                f"실습 **{counts.get('practices', 0)}**",
                f"개체 **{counts.get('entities', 0)}**",
                f"출처 **{counts.get('sources', 0)}**",
                f"프로젝트 **{counts.get('projects', 0)}**",
                f"카탈로그 **{counts.get('catalog', 0)}**",
                f"질의 **{counts.get('queries', 0)}**",
            ]
        ) + " 페이지.",
        "", "## 주요 개념", *concept_lines,
        "", "## 핵심 메시지", *message_lines,
        "", "## 주요 방법론", *method_lines,
        "",
    ]
    (WIKI / "overview.md").write_text("\n".join(lines), "utf-8")


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="wiki index/overview 재생성")
    ap.add_argument("--root", default=None, help="Wiki workspace 루트")
    args = ap.parse_args()
    _bind_root(find_wiki_root(args.root))
    WIKI.mkdir(exist_ok=True)
    write_index()
    write_overview()
    print("index.md / overview.md regenerated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
