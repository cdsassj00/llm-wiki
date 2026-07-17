#!/usr/bin/env python3
"""Interactively configure an LLM Wiki provider without echoing API keys."""
from __future__ import annotations

import getpass
import os
import subprocess
import sys
from pathlib import Path

from wiki_paths import find_wiki_root

PROVIDERS = {
    "1": ("claude-cli", None),
    "2": ("openrouter", "OPENROUTER_API_KEY"),
    "3": ("openai", "OPENAI_API_KEY"),
    "4": ("gemini", "GEMINI_API_KEY"),
    "5": ("anthropic", "ANTHROPIC_API_KEY"),
}
def update_dotenv(path: Path, values: dict[str, str]) -> None:
    existing: list[str] = []
    if path.is_file():
        existing = path.read_text("utf-8").splitlines()
    kept = [
        line
        for line in existing
        if not any(line.startswith(f"{key}=") for key in values)
    ]
    lines = [*kept, *[f"{key}={value}" for key, value in values.items()]]
    path.write_text("\n".join(lines).rstrip() + "\n", "utf-8")
    if os.name != "nt":
        path.chmod(0o600)


def set_windows_user(values: dict[str, str]) -> None:
    if os.name != "nt":
        raise RuntimeError("Windows 사용자 환경변수 저장은 Windows에서만 지원합니다.")
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Environment",
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        for name, value in values.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def choose(prompt: str, allowed: set[str]) -> str:
    while True:
        value = input(prompt).strip()
        if value in allowed:
            return value
        print(f"다음 중 하나를 입력하세요: {', '.join(sorted(allowed))}")


def main() -> int:
    root = find_wiki_root(None)
    print("LLM Wiki AI 공급자 설정")
    print("키를 채팅, 명령행 인자, URL에 붙여넣지 마세요. 아래 입력은 화면에 표시되지 않습니다.")
    print("1) Claude CLI (기존 로그인 사용, API 키 불필요)")
    print("2) OpenRouter  3) OpenAI  4) Gemini  5) Anthropic")
    provider, key_name = PROVIDERS[choose("공급자 [1-5]: ", set(PROVIDERS))]

    values = {
        "LLMWIKI_PROVIDER": provider,
        "LLMWIKI_AI_ENABLED": "1",
        "LLMWIKI_ALLOW_PROVIDER_FALLBACK": "0",
    }
    if key_name:
        key = getpass.getpass(f"{key_name} (숨김 입력): ").strip()
        if not key or "\n" in key or "\r" in key:
            print("유효한 키가 필요합니다.", file=sys.stderr)
            return 1
        values[key_name] = key

    print("저장 위치:")
    print("1) workspace .env (권장, 이 workspace에만 적용)")
    if os.name == "nt":
        print("2) Windows 사용자 환경변수 (동일 사용자 프로세스가 읽을 수 있는 평문)")
    print("3) 현재 설정 프로세스에서 브릿지를 바로 실행 (저장 안 함)")
    allowed = {"1", "3"} | ({"2"} if os.name == "nt" else set())
    storage = choose("선택: ", allowed)

    os.environ.update(values)
    if storage == "1":
        env_path = root / ".env"
        update_dotenv(env_path, values)
        print(f"저장 완료: {env_path}")
        if os.name == "nt":
            print("주의: Windows의 .env도 평문입니다. workspace 접근 권한을 제한하세요.")
        else:
            print("파일 권한을 현재 사용자 전용(0600)으로 설정했습니다.")
    elif storage == "2":
        set_windows_user(values)
        print("Windows 사용자 환경변수에 저장했습니다.")
        print(
            "주의: 사용자 레지스트리에 평문으로 저장되어 동일 사용자 프로세스가 읽을 수 있습니다. "
            "이미 열린 앱은 재시작해야 새 값을 볼 수 있습니다."
        )
    else:
        launcher = root / "tools" / "launch_wiki.py"
        print("저장하지 않고 현재 설정으로 브릿지를 시작합니다.")
        return subprocess.run(
            [sys.executable, str(launcher), "--root", str(root)],
            cwd=root,
            env=os.environ.copy(),
            shell=False,
            check=False,
        ).returncode

    print("설정된 키 값은 출력하지 않았습니다.")
    launcher = root / "tools" / "launch_wiki.py"
    subprocess.run(
        [sys.executable, str(launcher), "--root", str(root), "--stop"],
        cwd=root,
        env=os.environ.copy(),
        shell=False,
        check=False,
    )
    print("실행 중이던 브릿지가 있으면 새 설정 적용을 위해 종료했습니다.")
    print("다음: start-llm-wiki.bat을 더블클릭하거나 python tools/launch_wiki.py --root .")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
