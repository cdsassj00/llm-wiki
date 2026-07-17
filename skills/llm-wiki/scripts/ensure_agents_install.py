#!/usr/bin/env python3
"""이 스킬을 ~/.agents/skills/llm-wiki 에 설치(복사)하고
Claude Code용 ~/.claude/skills/llm-wiki 정션/심링크를 만든다.

코딩 에이전트가 스킬 폴더만 첨부받은 경우 이 스크립트를 먼저 실행한다.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_NAME = "llm-wiki"


def skill_src() -> Path:
    # .../skills/llm-wiki/scripts/ensure_agents_install.py → skill root
    return Path(__file__).resolve().parent.parent


def install_copy(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    shutil.copytree(src, dst, dirs_exist_ok=False)
    print(f"copied → {dst}")


def link_or_junction(link: Path, target: Path) -> None:
    if link.exists() or link.is_symlink():
        if link.is_dir() and not link.is_symlink():
            # real dir — replace with junction/symlink
            shutil.rmtree(link)
        else:
            link.unlink()
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"junction → {link} => {target}")
    else:
        os.symlink(target, link, target_is_directory=True)
        print(f"symlink → {link} => {target}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--agents-home",
        default=str(Path.home() / ".agents" / "skills"),
        help="전역 agents skills 폴더",
    )
    ap.add_argument(
        "--claude-home",
        default=str(Path.home() / ".claude" / "skills"),
        help="Claude skills 폴더 (정션 대상)",
    )
    ap.add_argument("--no-claude-link", action="store_true")
    args = ap.parse_args()

    src = skill_src()
    if not (src / "SKILL.md").is_file():
        print(f"SKILL.md 없음: {src}", file=sys.stderr)
        return 1

    agents = Path(args.agents_home).expanduser()
    agents.mkdir(parents=True, exist_ok=True)
    dst = agents / SKILL_NAME
    install_copy(src, dst)

    if not args.no_claude_link:
        claude = Path(args.claude_home).expanduser()
        claude.mkdir(parents=True, exist_ok=True)
        try:
            link_or_junction(claude / SKILL_NAME, dst)
        except Exception as exc:  # noqa: BLE001
            print(f"claude link 실패(무시 가능): {exc}")

    print("install OK — agents can load /llm-wiki from ~/.agents/skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
