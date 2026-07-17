#!/usr/bin/env python3
"""wiki/ 전체를 훑어 3D 그래프뷰 단일 HTML 파일(wiki/graph-view.html)을 생성한다.

- 모든 wiki/**/*.md 의 frontmatter(type/title)와 본문, [[위키링크]] 관계, 그리고
  실제 원본 폴더 경로(있으면)를 JSON으로 추출해 HTML 안에 그대로 박아 넣는다.
  → 결과 HTML은 서버 없이 더블클릭으로 바로 열리는 완전한 단일 파일이다.
- 그래프 라이브러리(3d-force-graph)와 마크다운 렌더러(marked)는 CDN에서 로드한다
  (사용자 브라우저에는 인터넷이 있으므로 문제 없음. claude.ai Artifact가 아니라
  로컬 데스크톱용 파일이라 외부 CDN 제약이 없다).
- wiki/ 는 .gitignore 로 통째로 제외되어 있으므로 이 산출물도 자동으로 커밋 대상에서 빠진다.

사용법
  python tools/build_graph_view.py
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from pathlib import Path

from wiki_paths import find_wiki_root

ROOT: Path = Path()
WIKI: Path = Path()
OUT: Path = Path()


def _bind_root(root: Path) -> None:
    global ROOT, WIKI, OUT
    ROOT = root
    WIKI = ROOT / "wiki"
    OUT = WIKI / "graph-view.html"

PROJECT_PARENTS = [
    "_antigravity", "_clawd", "_codex", "_cursor_project", "_snsautomation",
    "_visual_studio", "_독립프로그램테스트", "_claudecode", "_claudeCowork",
]

TOOL_HINT = {
    "_claudecode": "claude",
    "_claudeCowork": "claude",
    "_codex": "codex",
    "_cursor_project": "cursor .   (Cursor 앱)",
    "_antigravity": "(Antigravity 앱에서 폴더 열기)",
    "_visual_studio": "code .   (또는 Visual Studio)",
    "_독립프로그램테스트": "code .",
    "_snsautomation": "code .",
    "_clawd": "claude",
}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[(.+?)\]\]")
BACKTICK_PATH_RE = re.compile(r"`([A-Za-z]:\\[^`]+)`")
FILE_URI_RE = re.compile(r"file:///([^)\s\]]+)")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text = m.group(1)
    body = text[m.end():]
    fm = {}
    for key in ("type", "title"):
        km = re.search(rf"^{key}:\s*(.+)$", fm_text, re.MULTILINE)
        if km:
            fm[key] = km.group(1).strip().strip("\"'")
    return fm, body


def split_wikilink(raw: str) -> tuple[str, str]:
    parts = re.split(r"(?<!\\)\|", raw, maxsplit=1)
    target = parts[0].replace("\\|", "|").strip()
    display = parts[1].replace("\\|", "|").strip() if len(parts) > 1 else target
    return target, display


def find_folder_path(body: str) -> str | None:
    m = BACKTICK_PATH_RE.search(body[:1500])
    if m:
        return m.group(1)
    m = FILE_URI_RE.search(body[:1500])
    if m:
        raw = urllib.parse.unquote(m.group(1))
        return raw.replace("/", "\\")
    return None


def tool_hint_for(folder_path: str) -> tuple[str | None, bool]:
    for parent in PROJECT_PARENTS:
        if f"\\{parent}\\" in folder_path or folder_path.rstrip("\\").endswith(f"\\{parent}"):
            return TOOL_HINT.get(parent), True
    return None, False


def main() -> int:
    ap = argparse.ArgumentParser(description="3D 그래프뷰 HTML 생성")
    ap.add_argument("--root", default=None, help="Wiki workspace 루트")
    args = ap.parse_args()
    _bind_root(find_wiki_root(args.root))

    files = sorted(WIKI.rglob("*.md"))
    nodes = []
    title_to_id: dict[str, str] = {}

    for f in files:
        text = f.read_text("utf-8", errors="replace")
        fm, body = parse_frontmatter(text)
        rel = f.relative_to(WIKI).as_posix()
        title = fm.get("title") or f.stem
        node = {
            "id": rel,
            "title": title,
            "type": fm.get("type", "unknown"),
            "file": rel,
            "body": body.strip(),
        }
        folder = find_folder_path(body)
        if folder:
            node["folder"] = folder
            hint, is_code = tool_hint_for(folder)
            if hint:
                node["toolHint"] = hint
            node["isCodeFolder"] = is_code
        nodes.append(node)
        title_to_id[title] = rel

    links = []
    seen_pairs = set()
    undirected_seen = set()
    incoming: dict[str, list[str]] = {}
    for node in nodes:
        for m in WIKILINK_RE.finditer(node["body"]):
            target_title, _display = split_wikilink(m.group(1))
            target_id = title_to_id.get(target_title)
            if not target_id or target_id == node["id"]:
                continue
            pair = (node["id"], target_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            undirected_seen.add(frozenset((node["id"], target_id)))
            links.append({"source": node["id"], "target": target_id, "kind": "wikilink"})
            incoming.setdefault(target_id, []).append(node["id"])

    # "형제" 보조선: 같은 허브 하나를 같이 가리키는 노드끼리 얇은 링크로 연결해
    # 허브-스포크 구조에서도 또래끼리 관계가 있다는 느낌을 준다. 허브가 너무 크면
    # (예: 전역 색인처럼 거의 모든 페이지가 링크하는 곳) 완전 그래프로 만들면 링크가
    # 폭발하므로 2~20명 규모의 허브에만, 그것도 전부 잇지 않고 원형으로만 연결한다.
    sibling_count = 0
    for hub_id, sources in incoming.items():
        if not (2 <= len(sources) <= 20):
            continue
        ordered = sorted(sources)
        for i, src in enumerate(ordered):
            dst = ordered[(i + 1) % len(ordered)]
            key = frozenset((src, dst))
            if key in undirected_seen:
                continue
            undirected_seen.add(key)
            links.append({"source": src, "target": dst, "kind": "sibling"})
            sibling_count += 1

    type_counts: dict[str, int] = {}
    for n in nodes:
        type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1

    data = {"nodes": nodes, "links": links, "typeCounts": type_counts}
    # <script> 안에 그대로 박아 넣으므로, 본문에 우연히 "</script>"가 들어있으면 브라우저가
    # 거기서 태그를 닫아버린다(HTML 파서는 JS 문자열 안인지 모름) — 그 시퀀스와 라인구분자를 이스케이프.
    data_json = (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )

    html = HTML_TEMPLATE.replace("__GRAPH_DATA__", data_json)
    OUT.write_text(html, "utf-8")
    print(
        f"생성 완료: {OUT}  (노드 {len(nodes)}개, 링크 {len(links)}개 "
        f"= 위키링크 {len(links) - sibling_count} + 형제보조선 {sibling_count})"
    )
    return 0


HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>LLM Wiki — 3D 그래프뷰</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<!-- Google Fonts CSS는 요청 User-Agent별로 다른 @font-face를 내려주는 동적 리소스라
     바이트가 고정되지 않음 — SRI 무결성 해시를 붙일 수 없는 몇 안 되는 정당한 예외. -->
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"
        integrity="sha384-qOkzR5Ke/XkQxuGVJ9hpFEpDlcoLtWwVYhnJf06cLIZa2vaIptSqaubivErzmD5O"
        crossorigin="anonymous"></script>
<script src="https://unpkg.com/3d-force-graph@1.73.4/dist/3d-force-graph.min.js"
        integrity="sha384-GNPicn8pBA2/PGSyPTpxIlPurgLUYcNYJ2zskIq782dE9+gp5E32WSyuxZqA7J+u"
        crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"
        integrity="sha384-/TQbtLCAerC3jgaim+N78RZSDYV7ryeoBCVqTuzRrFec2akfBkHS7ACQ3PQhvMVi"
        crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js"
        integrity="sha384-PCSoOZTpbkikBEtd/+uV3WNdc676i9KUf01KOA8CnJotvlx8rRrETbDuwdjqTYvt"
        crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.1.6/dist/purify.min.js"
        integrity="sha384-+VfUPEb0PdtChMwmBcBmykRMDd+v6D/oFmB3rZM/puCMDYcIvF968OimRh4KQY9a"
        crossorigin="anonymous"></script>
<style>
  :root { color-scheme: dark; }
  html, body { margin: 0; padding: 0; height: 100%; background: #0b0e14; color: #dfe6ee; font-family: "Noto Sans KR", "Segoe UI", "Malgun Gothic", sans-serif; overflow: hidden; }
  #graph { position: fixed; inset: 0; }
  #panel {
    position: fixed; top: 0; right: 0; width: var(--panel-width, 420px); max-width: 92vw; height: 100%;
    background: rgba(15, 18, 26, 0.96); border-left: 1px solid #2a3140;
    box-shadow: -8px 0 24px rgba(0,0,0,.4); transform: translateX(100%);
    transition: transform .25s ease; overflow-y: auto; padding: 20px 22px 20px 28px; box-sizing: border-box; z-index: 20;
  }
  #panel.open { transform: translateX(0); }
  #panel.resizing { transition: none; }
  #panelResizer {
    position: absolute; top: 0; left: 0; width: 8px; height: 100%; cursor: col-resize;
    z-index: 21; touch-action: none;
  }
  #panelResizer:hover, #panelResizer.active { background: rgba(125, 184, 255, 0.25); }
  #panel h2 { margin-top: 0; font-size: 1.25em; color: #fff; }
  #panel .meta { font-size: .8em; color: #8b96a8; margin-bottom: 14px; }
  #panel .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
  #panel .actions a, #panel .actions button {
    background: #1e2735; color: #cfe0ff; border: 1px solid #33415a; border-radius: 6px;
    padding: 6px 10px; font-size: .82em; text-decoration: none; cursor: pointer;
  }
  #panel .actions a:hover, #panel .actions button:hover { background: #29354a; }
  #panel .content { font-size: .92em; line-height: 1.55; }
  #panel .content a { color: #7db8ff; }
  #panel .content code { background: #1a212e; padding: 1px 5px; border-radius: 4px; }
  #panel .content pre { background: #1a212e; padding: 10px; border-radius: 6px; overflow-x: auto; }
  #panel .content table { border-collapse: collapse; font-size: .85em; }
  #panel .content td, #panel .content th { border: 1px solid #2a3140; padding: 4px 8px; }
  #closeBtn { position: absolute; top: 12px; right: 14px; background: none; border: none; color: #8b96a8; font-size: 1.3em; cursor: pointer; }
  #hud { position: fixed; top: 14px; left: 14px; z-index: 15; display: flex; flex-direction: column; gap: 8px; max-width: 340px; }
  #hud input {
    background: #131722; border: 1px solid #2a3140; color: #dfe6ee; border-radius: 6px;
    padding: 8px 10px; font-size: .9em; width: 260px;
  }
  #legend { background: rgba(19,23,34,.85); border: 1px solid #2a3140; border-radius: 8px; padding: 10px 12px; font-size: .78em; }
  #legend .item { display: flex; align-items: center; gap: 6px; margin: 3px 0; cursor: pointer; }
  #legend .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex: none; }
  #title { font-size: .82em; color: #6d7788; }
  #suggestList { position: fixed; top: 62px; left: 14px; z-index: 16; background: #131722; border: 1px solid #2a3140; border-radius: 6px; max-height: 260px; overflow-y: auto; width: 260px; display: none; }
  #suggestList div { padding: 6px 10px; font-size: .85em; cursor: pointer; }
  #suggestList div:hover { background: #202838; }
  #suggestList div .snippet { color: #8b96a8; font-size: .85em; margin-top: 2px; }
  #hud .row { display: flex; gap: 6px; }
  #hud .row button {
    background: #131722; border: 1px solid #2a3140; color: #cfe0ff; border-radius: 6px;
    padding: 7px 10px; font-size: .82em; cursor: pointer; white-space: nowrap;
  }
  #hud .row button:hover { background: #1c2534; }
  #hud .row button.active { background: #2a3f66; border-color: #4a6fa5; }
  #filterChip {
    display: none; align-items: center; gap: 6px; background: #1e2735; border: 1px solid #33415a;
    border-radius: 14px; padding: 4px 6px 4px 12px; font-size: .8em; width: fit-content;
  }
  #filterChip button { background: none; border: none; color: #8b96a8; cursor: pointer; font-size: 1em; padding: 0 4px; }
  #listPanel {
    position: fixed; inset: 0; background: #0b0e14; z-index: 12; display: none;
    padding: 100px 24px 24px; box-sizing: border-box; overflow-y: auto;
  }
  #listPanel.open { display: block; }
  #listPanel table { border-collapse: collapse; width: 100%; max-width: 980px; margin: 0 auto; }
  #listPanel th { text-align: left; font-size: .78em; color: #8b96a8; padding: 6px 10px; border-bottom: 1px solid #2a3140; position: sticky; top: 0; background: #0b0e14; }
  #listPanel td { padding: 8px 10px; border-bottom: 1px solid #1a212e; font-size: .88em; cursor: pointer; }
  #listPanel tr:hover td { background: #151b26; }
  #listPanel .type-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; margin-right: 8px; }
  #listPanel .snippet { color: #75809a; font-size: .85em; }
  #listCount { max-width: 980px; margin: 0 auto 10px; color: #8b96a8; font-size: .85em; }
  #chatPanel {
    position: fixed; left: 50%; bottom: 22px; transform: translateX(-50%);
    width: 600px; max-width: 94vw; max-height: 60vh;
    background: rgba(22, 26, 38, 0.55); backdrop-filter: blur(20px) saturate(160%);
    -webkit-backdrop-filter: blur(20px) saturate(160%);
    border: 1px solid rgba(255,255,255,0.09); border-radius: 18px;
    box-shadow: 0 16px 44px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,0.06);
    display: none; flex-direction: column; z-index: 25; overflow: hidden;
  }
  #chatPanel.open { display: flex; }
  #chatHeader {
    padding: 12px 16px; border-bottom: 1px solid rgba(255,255,255,0.08); font-size: .85em; color: #cfe0ff;
    display: flex; justify-content: space-between; align-items: center; flex: none;
    background: rgba(255,255,255,0.03);
  }
  #chatHeader button { background: none; border: none; color: #8b96a8; cursor: pointer; font-size: 1.1em; }
  #chatMessages { flex: 0 1 auto; overflow-y: auto; max-height: 38vh; padding: 12px 14px; font-size: .88em; line-height: 1.5; }
  #chatMessages:empty { padding: 0; }
  #chatMessages .msg { margin-bottom: 14px; }
  #chatMessages .msg.user { color: #cfe0ff; }
  #chatMessages .msg.user .bubble { background: rgba(43, 58, 82, 0.65); border-radius: 10px; padding: 8px 12px; display: inline-block; }
  #chatMessages .msg.assistant .bubble { color: #dfe6ee; }
  #chatMessages .msg .refs { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 6px; }
  #chatMessages .msg .refs button {
    background: #1a2a3f; border: 1px solid #2f4c70; color: #9cc4f0; border-radius: 12px;
    padding: 3px 10px; font-size: .78em; cursor: pointer;
  }
  #chatMessages .msg .refs button:hover { background: #23385a; }
  #chatMessages .msg.error .bubble { color: #ff8b8b; }
  #chatMessages .msg .bubble p:first-child { margin-top: 0; }
  #chatMessages .msg .bubble p:last-child { margin-bottom: 0; }
  #chatMessages .export-row { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
  #chatMessages .export-row button {
    background: #1e2735; border: 1px solid #33415a; color: #cfe0ff; border-radius: 12px;
    padding: 3px 10px; font-size: .78em; cursor: pointer;
  }
  #chatMessages .export-row button:hover { background: #29354a; }
  #chatMessages .export-row button:disabled { opacity: .5; cursor: default; }
  #chatMessages .export-result { margin-top: 4px; font-size: .8em; color: #8fd19e; }
  #chatMessages .export-result a { color: #8fd19e; }
  #chatInputRow {
    border-top: 1px solid rgba(255,255,255,0.08); padding: 12px; display: flex; gap: 8px; flex: none;
    background: rgba(255,255,255,0.03);
  }
  #chatInputRow input {
    flex: 1; background: rgba(10,13,20,0.55); border: 1px solid rgba(255,255,255,0.12); color: #dfe6ee;
    border-radius: 20px; padding: 9px 16px; font-size: .88em;
  }
  #chatInputRow button {
    background: rgba(74, 111, 165, 0.5); border: 1px solid rgba(154, 190, 235, 0.5); color: #eaf2ff;
    border-radius: 20px; padding: 8px 16px; font-size: .85em; cursor: pointer;
  }
  #chatInputRow button:disabled { opacity: .5; cursor: default; }
  #chatToggleBtn.pulse { animation: chatPulse 1.4s ease-in-out infinite; }
  @keyframes chatPulse { 0%,100% { opacity: 1; } 50% { opacity: .55; } }
</style>
</head>
<body>
<div id="graph"></div>
<div id="hud">
  <div id="title">LLM Wiki 그래프 · <span id="countLabel"></span></div>
  <input id="search" placeholder="제목·본문 검색... (Enter로 이동)">
  <div id="suggestList"></div>
  <div id="filterChip"><span id="filterChipLabel"></span><button id="filterChipClear">✕</button></div>
  <div class="row">
    <button id="homeBtn" title="처음 화면으로">⌂ 처음으로</button>
    <button id="listToggleBtn" title="목록으로 보기">☰ 목록 보기</button>
    <button id="chatToggleBtn" class="pulse" title="AI에게 물어보기">🤖 AI에게 묻기</button>
  </div>
  <div id="legend"></div>
</div>
<div id="panel">
  <div id="panelResizer"></div>
  <button id="closeBtn" onclick="closePanel()">✕</button>
  <div id="panelBody"></div>
</div>
<div id="listPanel">
  <div id="listCount"></div>
  <table>
    <thead><tr><th>제목</th><th>타입</th><th style="width:40%">본문 스니펫</th></tr></thead>
    <tbody id="listBody"></tbody>
  </table>
</div>
<div id="chatPanel">
  <div id="chatHeader">
    <span>🤖 위키에게 물어보기 (로컬, agent_bridge.py 필요)</span>
    <button id="chatCloseBtn">✕</button>
  </div>
  <div id="chatMessages"></div>
  <div id="chatInputRow">
    <input id="chatInput" placeholder="예: 민첩한 AI 8가지 기술이 뭐야?" maxlength="2000">
    <button id="chatSendBtn">보내기</button>
  </div>
</div>

<script>
const DATA = __GRAPH_DATA__;

const TYPE_COLORS = {
  concept: "#4C9AFF", entity: "#36B37E", message: "#FF8B00", method: "#6554C0",
  practice: "#00B8D9", curriculum: "#8993A4", purpose: "#FF5630", pattern: "#00875A",
  source: "#5243AA", catalog: "#97A0AF", query: "#DE350B", project: "#FFC400",
  unknown: "#5b6577",
};
function colorFor(type) { return TYPE_COLORS[type] || TYPE_COLORS.unknown; }

const byId = {};
DATA.nodes.forEach(n => byId[n.id] = n);

// 노드 크기는 진짜 위키링크 연결 수만 반영한다(형제 보조선까지 포함하면 크기가 왜곡됨).
const degree = {};
DATA.links.filter(l => l.kind !== "sibling").forEach(l => {
  degree[l.source] = (degree[l.source] || 0) + 1;
  degree[l.target] = (degree[l.target] || 0) + 1;
});

// 허브(연결이 많은) 상위 노드에만 상시 라벨을 붙인다 — 전체 노드에 다 붙이면
// 글자가 서로 겹쳐 오히려 안 읽히고, 캔버스 텍스처가 349장 생겨 무거워진다.
const HUB_LABEL_COUNT = 18;
const hubIds = new Set(
  Object.entries(degree).sort((a, b) => b[1] - a[1]).slice(0, HUB_LABEL_COUNT).map(([id]) => id)
);

const wikilinkCount = DATA.links.filter(l => l.kind !== "sibling").length;
const siblingCount = DATA.links.length - wikilinkCount;
document.getElementById("countLabel").textContent =
  `노드 ${DATA.nodes.length} · 링크 ${wikilinkCount}(+형제 ${siblingCount})`;

const legend = document.getElementById("legend");
Object.entries(DATA.typeCounts).sort((a,b)=>b[1]-a[1]).forEach(([type, count]) => {
  const row = document.createElement("div");
  row.className = "item";
  row.innerHTML = `<span class="dot" style="background:${colorFor(type)}"></span>${type} (${count})`;
  row.onclick = () => filterByType(type);
  legend.appendChild(row);
});

const filterChip = document.getElementById("filterChip");
const filterChipLabel = document.getElementById("filterChipLabel");
document.getElementById("filterChipClear").addEventListener("click", () => filterByType(null));
const listPanel = document.getElementById("listPanel");
const listBody = document.getElementById("listBody");
const listCount = document.getElementById("listCount");

let activeTypeFilter = null;
function filterByType(type) {
  activeTypeFilter = (activeTypeFilter === type) ? null : type;
  if (activeTypeFilter) {
    filterChip.style.display = "flex";
    filterChipLabel.textContent = `필터: ${activeTypeFilter}`;
  } else {
    filterChip.style.display = "none";
  }
  refreshNodeVisuals();
  if (listPanel.classList.contains("open")) renderList();
}

let highlightNodes = new Set();
let highlightLinks = new Set();
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// 부드러운 원형 그라디언트 텍스처 1장을 만들어 모든 노드의 글로우(halo)에 재사용한다.
const glowTexture = (() => {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.35, "rgba(255,255,255,0.45)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
})();

const nodeObjById = {};

// 노드마다 새 SphereGeometry를 만들면(예전 방식) 349개면 349개의 GPU 버퍼가 생긴다.
// 반지름 1짜리 지오메트리 하나를 모든 노드가 공유하고 mesh.scale로만 크기를 다르게 준다.
const UNIT_SPHERE_GEO = new THREE.SphereGeometry(1, 10, 10);

// 허브 라벨용 캔버스 텍스트 스프라이트. 18개뿐이라 노드마다 만들어도 부담 없다.
function buildLabelSprite(text) {
  const fontPx = 42;
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  ctx.font = `600 ${fontPx}px system-ui, sans-serif`;
  const padX = 16, padY = 10;
  canvas.width = Math.ceil(ctx.measureText(text).width) + padX * 2;
  canvas.height = fontPx + padY * 2;
  ctx.font = `600 ${fontPx}px system-ui, sans-serif`; // 캔버스 크기 변경 시 컨텍스트가 리셋됨
  ctx.fillStyle = "rgba(9,12,20,0.55)";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#eaf2ff";
  ctx.textBaseline = "middle";
  ctx.fillText(text, padX, canvas.height / 2 + 2);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: new THREE.CanvasTexture(canvas), transparent: true, depthWrite: false,
  }));
  const labelH = 6.5;
  sprite.scale.set((canvas.width / canvas.height) * labelH, labelH, 1);
  return sprite;
}

function buildNodeObject(n) {
  const group = new THREE.Group();
  const r = 2.4 + Math.sqrt(degree[n.id] || 0) * 1.05;
  const color = new THREE.Color(colorFor(n.type));

  // 네온 사인처럼 항상 100% 밝게 — 조명(lit) 재질을 쓰면 카메라 반대쪽이 그림자로 어두워져
  // "빛나는 느낌"이 죽는다. MeshBasicMaterial은 조명 계산 자체가 없어 늘 균일하게 밝고,
  // 광원 연산이 없어 342개를 그려도 더 가볍다.
  const core = new THREE.Mesh(
    UNIT_SPHERE_GEO,
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 1 })
  );
  core.scale.setScalar(r);
  group.add(core);

  const halo = new THREE.Sprite(new THREE.SpriteMaterial({
    map: glowTexture, color, transparent: true, opacity: 0.62,
    blending: THREE.AdditiveBlending, depthWrite: false,
  }));
  halo.scale.set(r * 3.2, r * 3.2, 1);
  group.add(halo);

  let label = null;
  if (hubIds.has(n.id)) {
    label = buildLabelSprite(n.title);
    label.position.set(0, r + 6, 0);
    group.add(label);
  }

  nodeObjById[n.id] = { group, core, halo, label, r, phase: Math.random() * Math.PI * 2 };
  return group;
}

function isDimmed(n) {
  return (activeTypeFilter && n.type !== activeTypeFilter) ||
    (highlightNodes.size > 0 && !highlightNodes.has(n.id));
}

// 활성 필터/하이라이트 상태에 맞춰 이미 그려진 노드들의 밝기·불투명도만 갱신한다
// (nodeThreeObject를 쓰면 accessor 재호출만으론 다시 안 그려지므로 직접 material을 만진다).
function refreshNodeVisuals() {
  DATA.nodes.forEach(n => {
    const obj = nodeObjById[n.id];
    if (!obj) return;
    const dimmed = isDimmed(n);
    obj.core.material.opacity = dimmed ? 0.18 : 1;
    obj.halo.material.opacity = dimmed ? 0.05 : 0.62;
    if (obj.label) obj.label.material.opacity = dimmed ? 0.12 : 0.95;
  });
}

// 은은한 네온 호흡 애니메이션 — 노드마다 위상(phase)을 다르게 줘서 동시에 깜빡이지 않게 한다.
// 필터로 어두워진 노드는 refreshNodeVisuals가 정한 값(0.05)을 그대로 두고 건드리지 않는다.
if (!reducedMotion) {
  function pulseHalos(ts) {
    const t = ts / 1000;
    DATA.nodes.forEach(n => {
      const obj = nodeObjById[n.id];
      if (!obj || isDimmed(n)) return;
      obj.halo.material.opacity = 0.62 + Math.sin(t * 1.1 + obj.phase) * 0.08;
    });
    requestAnimationFrame(pulseHalos);
  }
  requestAnimationFrame(pulseHalos);
}

const Graph = ForceGraph3D()(document.getElementById("graph"))
  .graphData(DATA)
  .nodeId("id")
  .backgroundColor("#0b0e14")
  .nodeLabel(n => `${n.title} [${n.type}]`)
  .nodeVal(n => 1 + Math.sqrt(degree[n.id] || 0))
  .nodeThreeObject(buildNodeObject)
  .nodeThreeObjectExtend(false)
  // 위키링크(실제 본문에서 [[링크]]로 참조된 것)는 기본 상태에서도 잘 보이게 밝고 굵게,
  // 형제 보조선(같은 허브를 같이 가리켜서 생긴 것)은 존재는 느껴지되 튀지 않게 얇고 흐리게.
  .linkColor(l => highlightLinks.has(l) ? "#ffffff" : (l.kind === "sibling" ? "rgba(120,130,145,0.16)" : "rgba(170,195,235,0.45)"))
  .linkWidth(l => highlightLinks.has(l) ? 2.2 : (l.kind === "sibling" ? 0.25 : 0.7))
  .linkCurvature(l => l.kind === "sibling" ? 0.3 : 0.12)
  .linkDirectionalParticles(l => highlightLinks.has(l) ? 2 : 0)
  .onNodeClick(n => { focusNode(n.id, true); });

// 고해상도(레티나/4K) 화면은 devicePixelRatio가 2~3이라 기본값 그대로면 프레그먼트 셰이더가
// 4~9배 더 일한다 — 화면상 체감 차이는 거의 없는데 느려지기만 하므로 2배로 상한을 둔다.
Graph.renderer().setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

// 노드가 중앙에 뭉쳐 겹쳐 보이면 342개라는 규모감이 안 산다 — 더 넓게 퍼지도록 힘 조정.
Graph.d3Force("charge").strength(-110);
if (Graph.d3Force("link")) Graph.d3Force("link").distance(60);

// 깊이감: 배경 파티클 별자리 (노드는 MeshBasicMaterial이라 조명 영향을 안 받음)
// (FogExp2를 넣었더니 이 그래프 규모(노드 반경 ~300)엔 밀도가 너무 세서
//  노드들이 배경색으로 뭉개져 "블러 blob"처럼 보였다 — 실측 후 제거함)
const scene = Graph.scene();

(() => {
  const STAR_COUNT = 2400;
  const positions = new Float32Array(STAR_COUNT * 3);
  for (let i = 0; i < STAR_COUNT; i++) {
    const radius = 700 + Math.random() * 900;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
    positions[i * 3 + 2] = radius * Math.cos(phi);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const mat = new THREE.PointsMaterial({
    size: 1.7, color: 0xaad0ff, transparent: true, opacity: 0.55,
    sizeAttenuation: true, depthWrite: false,
  });
  scene.add(new THREE.Points(geo, mat));
})();

// 유휴 상태일 때 카메라가 천천히 공전 — 사용자가 드래그/클릭하면 잠시 멈췄다가 재개
const controls = Graph.controls();
let idleTimer = null;
function pauseAutoRotate() {
  if (reducedMotion) return;
  controls.autoRotate = false;
  clearTimeout(idleTimer);
  idleTimer = setTimeout(() => { controls.autoRotate = true; }, 6000);
}
if (!reducedMotion) {
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.35;
  controls.addEventListener("start", pauseAutoRotate);
}
// 회전/줌 반응 속도 — 기본값이 굼떠 보인다는 피드백으로 상향
controls.zoomSpeed = 2.2;
controls.rotateSpeed = 1.3;
controls.dampingFactor = 0.18;

Graph.onEngineStop(() => Graph.zoomToFit(400, 60));

function focusNode(id, moveCamera) {
  const n = byId[id];
  if (!n) return;
  highlightNodes = new Set([id]);
  highlightLinks = new Set(DATA.links.filter(l => {
    const s = l.source.id !== undefined ? l.source.id : l.source;
    const t = l.target.id !== undefined ? l.target.id : l.target;
    if (s === id) { highlightNodes.add(t); return true; }
    if (t === id) { highlightNodes.add(s); return true; }
    return false;
  }));
  refreshNodeVisuals();
  Graph.linkColor(Graph.linkColor());
  Graph.linkWidth(Graph.linkWidth());
  Graph.linkDirectionalParticles(Graph.linkDirectionalParticles());

  if (moveCamera) {
    const distance = 120;
    const graphNode = Graph.graphData().nodes.find(x => x.id === id);
    if (graphNode && graphNode.x !== undefined) {
      const ratio = 1 + distance / Math.hypot(graphNode.x, graphNode.y, graphNode.z || 1);
      Graph.cameraPosition(
        { x: graphNode.x * ratio, y: graphNode.y * ratio, z: (graphNode.z || 0) * ratio },
        graphNode, 400
      );
    }
  }
  openPanel(n);
}

function wikilinksToMd(body) {
  return body.replace(/\[\[(.+?)\]\]/g, (m, inner) => {
    const parts = inner.split(/(?<!\\)\|/);
    const target = parts[0].replace(/\\\|/g, "|").trim();
    const display = (parts[1] !== undefined ? parts[1] : target).replace(/\\\|/g, "|").trim();
    const targetNode = DATA.nodes.find(n => n.title === target);
    if (!targetNode) return display;
    return `[${display}](#node:${encodeURIComponent(targetNode.id)})`;
  });
}

// 오른쪽 패널 너비 드래그 리사이즈 — localStorage에 저장해 다음에 열어도 유지.
(() => {
  const panelEl = document.getElementById("panel");
  const resizer = document.getElementById("panelResizer");
  const saved = parseInt(localStorage.getItem("graphViewPanelWidth") || "", 10);
  if (saved) panelEl.style.setProperty("--panel-width", saved + "px");

  let dragging = false;
  resizer.addEventListener("pointerdown", (ev) => {
    dragging = true;
    resizer.classList.add("active");
    panelEl.classList.add("resizing");
    resizer.setPointerCapture(ev.pointerId);
  });
  resizer.addEventListener("pointermove", (ev) => {
    if (!dragging) return;
    const width = Math.min(window.innerWidth * 0.92, Math.max(300, window.innerWidth - ev.clientX));
    panelEl.style.setProperty("--panel-width", width + "px");
  });
  function endDrag() {
    if (!dragging) return;
    dragging = false;
    resizer.classList.remove("active");
    panelEl.classList.remove("resizing");
    const width = parseInt(panelEl.style.getPropertyValue("--panel-width"), 10);
    if (width) localStorage.setItem("graphViewPanelWidth", String(width));
  }
  resizer.addEventListener("pointerup", endDrag);
  resizer.addEventListener("pointercancel", endDrag);
})();

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function openPanel(n) {
  const body = document.getElementById("panelBody");
  const mdSource = wikilinksToMd(n.body);
  // 이 위키는 내가 직접 쓰지만, marked는 원문 안의 raw HTML을 그대로 통과시키므로
  // 방어적으로 살균한다(강의안 원문을 인용하다 보면 임의 HTML이 섞여 들어올 수 있음).
  const rendered = DOMPurify.sanitize(marked.parse(mdSource));

  let actions = `<a href="#" onclick="return false;" style="border-color:${colorFor(n.type)}">${n.type}</a>`;
  let cmdForCopy = null;
  if (n.folder) {
    const fileUri = "file:///" + n.folder.replace(/\\/g, "/");
    actions += `<a href="${escapeHtml(fileUri)}" target="_blank">📂 탐색기에서 열기</a>`;
    if (n.isCodeFolder) {
      const vscodeUri = "vscode://file/" + n.folder.replace(/\\/g, "/");
      actions += `<a href="${escapeHtml(vscodeUri)}">🖥 VSCode로 열기</a>`;
      if (n.toolHint) {
        cmdForCopy = `cd /d "${n.folder}" && ${n.toolHint}`;
        actions += `<button class="copy-cmd-btn">📋 실행 명령 복사</button>`;
      }
    }
  }

  document.getElementById("panel").classList.add("open");
  body.innerHTML = `
    <h2>${escapeHtml(n.title)}</h2>
    <div class="meta">${escapeHtml(n.file)}</div>
    <div class="actions">${actions}</div>
    <div class="content">${rendered}</div>
  `;
  body.querySelectorAll('a[href^="#node:"]').forEach(a => {
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      const id = decodeURIComponent(a.getAttribute("href").slice("#node:".length));
      focusNode(id, true);
    });
  });
  const copyBtn = body.querySelector(".copy-cmd-btn");
  if (copyBtn && cmdForCopy) {
    copyBtn.addEventListener("click", () => copyCmd(copyBtn, cmdForCopy));
  }
}

function closePanel() {
  document.getElementById("panel").classList.remove("open");
  highlightNodes = new Set();
  highlightLinks = new Set();
  refreshNodeVisuals();
  Graph.linkColor(Graph.linkColor());
  Graph.linkWidth(Graph.linkWidth());
  Graph.linkDirectionalParticles(Graph.linkDirectionalParticles());
}

function copyCmd(btn, cmd) {
  navigator.clipboard.writeText(cmd).then(() => {
    const old = btn.textContent;
    btn.textContent = "복사됨!";
    setTimeout(() => btn.textContent = old, 1200);
  });
}

// Fuse.js 기반 오타 허용 검색(제목 가중치 높게, 본문도 포함) — 활성 타입 필터가 있으면 그 안에서만.
const fuse = new Fuse(DATA.nodes, {
  keys: [
    { name: "title", weight: 0.7 },
    { name: "body", weight: 0.3 },
  ],
  threshold: 0.35,
  ignoreLocation: true,
  minMatchCharLength: 2,
  includeMatches: true,
});

function snippetFromMatch(body, match) {
  if (!match || !match.indices || !match.indices.length) return "";
  const [s, e] = match.indices[0];
  const start = Math.max(0, s - 25);
  const end = Math.min(body.length, e + 46);
  return (start > 0 ? "…" : "") + body.slice(start, end).replace(/\s+/g, " ") + (end < body.length ? "…" : "");
}

function searchMatches(q, limit) {
  if (!q) return [];
  let results = fuse.search(q);
  if (activeTypeFilter) results = results.filter(r => r.item.type === activeTypeFilter);
  if (limit) results = results.slice(0, limit);
  return results.map(r => {
    const titleMatch = (r.matches || []).find(m => m.key === "title");
    const bodyMatch = (r.matches || []).find(m => m.key === "body");
    return {
      n: r.item,
      kind: titleMatch ? "title" : "body",
      snippet: bodyMatch ? snippetFromMatch(r.item.body, bodyMatch) : "",
    };
  });
}

const searchInput = document.getElementById("search");
const suggestList = document.getElementById("suggestList");
searchInput.addEventListener("input", () => {
  const q = searchInput.value.trim().toLowerCase();
  suggestList.innerHTML = "";
  if (!q) { suggestList.style.display = "none"; if (listPanel.classList.contains("open")) renderList(); return; }
  const matches = searchMatches(q, 15);
  matches.forEach(({ n, kind, snippet }) => {
    const row = document.createElement("div");
    if (kind === "title") {
      row.textContent = `${n.title} [${n.type}]`;
    } else {
      row.innerHTML = `${escapeHtml(n.title)} [${n.type}]<div class="snippet">${escapeHtml(snippet)}</div>`;
    }
    row.onclick = () => { focusNode(n.id, true); suggestList.style.display = "none"; };
    suggestList.appendChild(row);
  });
  suggestList.style.display = matches.length ? "block" : "none";
  if (listPanel.classList.contains("open")) renderList();
});
searchInput.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") {
    const q = searchInput.value.trim().toLowerCase();
    const hit = searchMatches(q, 1)[0];
    if (hit) { focusNode(hit.n.id, true); suggestList.style.display = "none"; }
  }
});

// 처음 화면으로: 필터·검색·하이라이트 다 지우고 전체 그래프가 보이게 리셋
document.getElementById("homeBtn").addEventListener("click", () => {
  activeTypeFilter = null;
  filterChip.style.display = "none";
  searchInput.value = "";
  suggestList.style.display = "none";
  closePanel();
  Graph.zoomToFit(500, 60);
});

// 3D 조작이 낯선 사람을 위한 목록(테이블) 뷰 — 같은 검색·타입 필터를 그대로 씀
const listToggleBtn = document.getElementById("listToggleBtn");
listToggleBtn.addEventListener("click", () => {
  const willOpen = !listPanel.classList.contains("open");
  listPanel.classList.toggle("open", willOpen);
  listToggleBtn.classList.toggle("active", willOpen);
  listToggleBtn.textContent = willOpen ? "🌐 그래프로 보기" : "☰ 목록 보기";
  if (willOpen) renderList();
});

function renderList() {
  const q = searchInput.value.trim();
  // 검색 중이면 Fuse 결과(관련도순) 그대로, 아니면 필터만 적용해 제목순 정렬.
  const rows = q
    ? searchMatches(q).map(r => ({ n: r.n, snippet: r.snippet }))
    : (activeTypeFilter ? DATA.nodes.filter(n => n.type === activeTypeFilter) : DATA.nodes)
        .map(n => ({ n, snippet: "" }))
        .sort((a, b) => a.n.title.localeCompare(b.n.title, "ko"));
  listCount.textContent = `${rows.length}개 문서${activeTypeFilter ? ` · 타입: ${activeTypeFilter}` : ""}${q ? ` · 검색: "${q}"` : ""}`;
  listBody.innerHTML = "";
  rows.forEach(({ n, snippet }) => {
    const shown = snippet || n.body.slice(0, 80).replace(/\s+/g, " ");
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(n.title)}</td>
      <td><span class="type-dot" style="background:${colorFor(n.type)}"></span>${n.type}</td>
      <td class="snippet">${escapeHtml(shown)}</td>
    `;
    tr.addEventListener("click", () => focusNode(n.id, true));
    listBody.appendChild(tr);
  });
}

// AI 채팅 — tools/agent_bridge.py 로컬 서버가 켜져 있을 때만 동작한다(없으면 안내만 뜸).
// 서버가 그래프뷰 HTML도 같이 서빙하므로 /ask 는 같은 출처(origin)로 상대경로 호출한다.
const chatPanel = document.getElementById("chatPanel");
const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const chatSendBtn = document.getElementById("chatSendBtn");
const chatToggleBtn = document.getElementById("chatToggleBtn");

chatToggleBtn.addEventListener("click", () => {
  chatPanel.classList.toggle("open");
  chatToggleBtn.classList.remove("pulse");
  if (chatPanel.classList.contains("open")) chatInput.focus();
});
document.getElementById("chatCloseBtn").addEventListener("click", () => chatPanel.classList.remove("open"));

function appendChatMessage(role, html) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = `<div class="bubble">${html}</div>`;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

// 답변을 그냥 보여주고 끝내지 않고, 다음 작업(코딩 에이전트에게 이어주기)의 재료로
// 내보낼 수 있게 한다 — (a) wiki/queries/ 에 질의 기록으로 저장, (b) 새 "프로젝트"
// 폴더(핸드오프 시드)로 내보내기. 둘 다 같은 브리핑 내용(질문+답변+원문 경로)을 쓴다.
function appendExportRow(msgDiv, question, answer, referenced) {
  const row = document.createElement("div");
  row.className = "export-row";

  const saveBtn = document.createElement("button");
  saveBtn.textContent = "📝 질의로 저장";
  saveBtn.addEventListener("click", () => doExport({ question, answer, referenced, mode: "query" }, row));

  const projectBtn = document.createElement("button");
  projectBtn.textContent = "📁 프로젝트로 내보내기";
  projectBtn.addEventListener("click", () => {
    const name = window.prompt("새 프로젝트 폴더 이름 (비워두면 질문에서 자동 생성):", "");
    if (name === null) return; // 취소
    doExport({ question, answer, referenced, mode: "project", projectName: name || undefined }, row);
  });

  row.appendChild(saveBtn);
  row.appendChild(projectBtn);
  msgDiv.appendChild(row);
}

async function doExport(payload, row) {
  row.querySelectorAll("button").forEach(b => b.disabled = true);
  try {
    const res = await fetch("/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    const result = document.createElement("div");
    result.className = "export-result";
    if (!res.ok) {
      result.textContent = "❌ " + (data.error || "내보내기 실패");
    } else {
      const fileUri = "file:///" + data.path.replace(/\\/g, "/");
      const label = data.kind === "project" ? "📁 프로젝트 생성됨" : "📝 질의 저장됨";
      result.innerHTML = `${label}: <a href="${fileUri}" target="_blank">${escapeHtml(data.path)}</a>`;
    }
    row.parentElement.appendChild(result); // row.after()는 여러 번 누르면 순서가 뒤집힘
  } catch (err) {
    const result = document.createElement("div");
    result.className = "export-result";
    result.textContent = "❌ 브릿지 서버에 연결할 수 없습니다.";
    row.parentElement.appendChild(result);
  } finally {
    row.querySelectorAll("button").forEach(b => b.disabled = false);
  }
}

async function sendChat() {
  const q = chatInput.value.trim();
  if (!q) return;
  appendChatMessage("user", escapeHtml(q));
  chatInput.value = "";
  chatInput.disabled = true;
  chatSendBtn.disabled = true;
  const thinking = appendChatMessage("assistant", "생각 중... (첫 질문은 캐시가 없어 특히 오래 걸릴 수 있음)");
  try {
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    const data = await res.json();
    thinking.remove();
    if (!res.ok) {
      appendChatMessage("error", escapeHtml(data.error || "오류가 발생했습니다"));
      return;
    }
    const div = appendChatMessage("assistant", DOMPurify.sanitize(marked.parse(data.answer || "")));
    if (data.referenced && data.referenced.length) {
      const refsDiv = document.createElement("div");
      refsDiv.className = "refs";
      data.referenced.forEach(r => {
        const btn = document.createElement("button");
        btn.textContent = "📄 " + r.title;
        btn.addEventListener("click", () => focusNode(r.id, true));
        refsDiv.appendChild(btn);
      });
      div.appendChild(refsDiv);
    }
    appendExportRow(div, q, data.answer || "", data.referenced || []);
  } catch (err) {
    thinking.remove();
    appendChatMessage(
      "error",
      "AI 브릿지 서버에 연결할 수 없습니다. 터미널에서 <code>python tools/agent_bridge.py</code>를 " +
      "실행한 뒤 <code>http://127.0.0.1:8787/graph-view.html</code> 로 다시 열어주세요."
    );
  } finally {
    chatInput.disabled = false;
    chatSendBtn.disabled = false;
    chatInput.focus();
  }
}
chatSendBtn.addEventListener("click", sendChat);
chatInput.addEventListener("keydown", (ev) => { if (ev.key === "Enter") sendChat(); });
</script>
</body>
</html>
"""

if __name__ == "__main__":
    raise SystemExit(main())
