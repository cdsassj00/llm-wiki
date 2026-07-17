#!/usr/bin/env python3
"""공개 스킬의 관리 도구와 원클릭 런처를 Wiki workspace에 배치한다."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

MANAGED_TOOLS = (
    "agent_bridge.py",
    "build_constellation_view.py",
    "build_graph_view.py",
    "constellation_template.html",
    "configure_provider.py",
    "ingest.py",
    "launch_wiki.py",
    "reindex.py",
    "wiki_paths.py",
)

BAT_LAUNCHER = r"""@echo off
setlocal
python "%~dp0tools\launch_wiki.py" --root "%~dp0." %*
if errorlevel 1 pause
"""

POWERSHELL_LAUNCHER = r"""param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Arguments
)

$ErrorActionPreference = "Stop"
$launcher = Join-Path $PSScriptRoot "tools\launch_wiki.py"
& python $launcher --root $PSScriptRoot @Arguments
exit $LASTEXITCODE
"""

BAT_CONFIGURATOR = r"""@echo off
setlocal
cd /d "%~dp0"
python "%~dp0tools\configure_provider.py"
if errorlevel 1 pause
"""


def write_if_changed(path: Path, content: str) -> None:
    if path.is_file() and path.read_text("utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, "utf-8")


def install_tools(root: Path) -> list[Path]:
    source_dir = Path(__file__).resolve().parent
    target_dir = root / "tools"
    target_dir.mkdir(parents=True, exist_ok=True)
    installed: list[Path] = []
    for name in MANAGED_TOOLS:
        source = source_dir / name
        if not source.is_file():
            raise RuntimeError(f"공개 스킬 도구가 없습니다: {source}")
        target = target_dir / name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        installed.append(target)
    write_if_changed(root / "start-llm-wiki.bat", BAT_LAUNCHER)
    write_if_changed(root / "start-llm-wiki.ps1", POWERSHELL_LAUNCHER)
    write_if_changed(root / "configure-provider.bat", BAT_CONFIGURATOR)
    return installed


def main() -> int:
    parser = argparse.ArgumentParser(description="Install/update LLM Wiki workspace tools")
    parser.add_argument("root", help="기존 또는 새 Wiki workspace root")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    if not (root / "purpose.md").is_file() or not (root / "schema.md").is_file():
        parser.error(
            "purpose.md/schema.md가 없습니다. 새 workspace는 bootstrap_wiki.py로 먼저 만드세요."
        )
    try:
        installed = install_tools(root)
    except RuntimeError as exc:
        parser.error(str(exc))
    print(f"workspace tools OK: {root}")
    print(f"  managed tools: {len(installed)}")
    print(f"  Windows: {root / 'start-llm-wiki.bat'}")
    print(f"  Provider setup: {root / 'configure-provider.bat'}")
    print(
        "  Cross-platform: "
        f'python "{root / "tools" / "launch_wiki.py"}" --root "{root}"'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
