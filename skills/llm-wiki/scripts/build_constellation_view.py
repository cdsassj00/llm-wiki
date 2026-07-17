#!/usr/bin/env python3
"""LLM Wiki를 절차적 심우주 배경의 3D 성좌 그래프로 빌드한다."""
from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path

from wiki_paths import find_wiki_root

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[(.+?)\]\]")
TYPE_LABELS = {
    "concept": "개념",
    "source": "출처",
    "curriculum": "커리큘럼",
    "message": "메시지",
    "method": "방법론",
    "practice": "실습",
    "entity": "개체",
    "project": "프로젝트",
    "purpose": "용도",
    "pattern": "패턴",
    "catalog": "카탈로그",
    "query": "질의",
    "unknown": "기타",
}


def parse_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    frontmatter = match.group(1)
    data: dict[str, str | list[str]] = {}
    for key in ("type", "title"):
        value = re.search(rf"^{key}:\s*(.+)$", frontmatter, re.MULTILINE)
        if value:
            data[key] = value.group(1).strip().strip("\"'")
    for key in ("aliases", "tags", "keywords"):
        block = re.search(
            rf"^{key}:\s*(?:\n((?:[ \t]+-\s*.*(?:\n|$))*))?",
            frontmatter,
            re.MULTILINE,
        )
        if block:
            data[key] = [
                item.strip().strip("\"'")
                for item in re.findall(r"^[ \t]+-\s*(.+)$", block.group(1) or "", re.MULTILINE)
            ]
    return data, text[match.end():]


def split_wikilink(raw: str) -> str:
    target = re.split(r"(?<!\\)\|", raw, maxsplit=1)[0]
    return target.replace("\\|", "|").strip()


def build_data(wiki: Path) -> dict:
    files = sorted(wiki.rglob("*.md"))
    nodes: list[dict] = []
    title_to_id: dict[str, str] = {}

    for file in files:
        text = file.read_text("utf-8", errors="replace")
        frontmatter, body = parse_frontmatter(text)
        relative = file.relative_to(wiki).as_posix()
        title = frontmatter.get("title") or file.stem
        plain_text = re.sub(
            r"\s+", " ", re.sub(r"[#>*`\[\]]", " ", body)
        ).strip()
        nodes.append({
            "id": relative,
            "title": title,
            "type": frontmatter.get("type", "unknown"),
            "path": relative,
            "aliases": frontmatter.get("aliases", []),
            "tags": frontmatter.get("tags", []),
            "keywords": frontmatter.get("keywords", []),
            "snippet": plain_text[:280],
            "body": body.strip(),
            "outlinks": [],
            "backlinks": [],
        })
        title_to_id[title] = relative

    links: list[dict] = []
    seen: set[tuple[str, str]] = set()
    degree: dict[str, int] = {}
    node_by_id = {node["id"]: node for node in nodes}
    for file in files:
        text = file.read_text("utf-8", errors="replace")
        _, body = parse_frontmatter(text)
        source = file.relative_to(wiki).as_posix()
        for match in WIKILINK_RE.finditer(body):
            target = title_to_id.get(split_wikilink(match.group(1)))
            if not target or target == source or (source, target) in seen:
                continue
            seen.add((source, target))
            links.append({"source": source, "target": target})
            node_by_id[source]["outlinks"].append(target)
            node_by_id[target]["backlinks"].append(source)
            degree[source] = degree.get(source, 0) + 1
            degree[target] = degree.get(target, 0) + 1

    counts: dict[str, int] = {}
    for node in nodes:
        node["deg"] = degree.get(node["id"], 0)
        counts[node["type"]] = counts.get(node["type"], 0) + 1

    return {
        "nodes": nodes,
        "links": links,
        "counts": counts,
        "labels": TYPE_LABELS,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    args = parser.parse_args()

    root = find_wiki_root(args.root)
    wiki = root / "wiki"
    output = wiki / "constellation.html"
    template_path = Path(__file__).with_name("constellation_template.html")
    if not template_path.is_file():
        raise SystemExit("constellation_template.html을 찾지 못했습니다.")

    data = build_data(wiki)
    data_json = (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )

    # three-render-objects가 core에 없는 Timer를 bare "three"에서 가져온다.
    shim = (
        "export * from 'three-core';"
        "export { Timer } from "
        "'https://unpkg.com/three@0.170.0/examples/jsm/misc/Timer.js';"
    )
    shim_url = (
        "data:text/javascript;base64,"
        + base64.b64encode(shim.encode("utf-8")).decode("ascii")
    )
    html = (
        template_path.read_text("utf-8")
        .replace("__DATA__", data_json)
        .replace("__THREE_SHIM__", shim_url)
    )
    output.write_text(html, "utf-8")
    print(
        f"생성 완료: {output} "
        f"(노드 {len(data['nodes'])} · 링크 {len(data['links'])})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
