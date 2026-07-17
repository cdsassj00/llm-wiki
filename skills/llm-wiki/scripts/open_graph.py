#!/usr/bin/env python3
"""wiki/graph-view.html 을 기본 브라우저로 연다."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

from wiki_paths import find_wiki_root


def main() -> int:
    ap = argparse.ArgumentParser(description="Open 3D graph view")
    ap.add_argument("--root", default=None)
    ap.add_argument("--build", action="store_true", help="열기 전 build_graph_view 실행")
    args = ap.parse_args()
    root = find_wiki_root(args.root)
    out = root / "wiki" / "graph-view.html"

    if args.build or not out.exists():
        script = Path(__file__).with_name("build_graph_view.py")
        rc = subprocess.call([sys.executable, str(script), "--root", str(root)])
        if rc != 0:
            return rc

    if not out.exists():
        print(f"없음: {out}")
        return 1

    uri = out.resolve().as_uri()
    print(f"open: {uri}")
    if os.name == "nt":
        os.startfile(str(out.resolve()))  # type: ignore[attr-defined]
    else:
        webbrowser.open(uri)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
