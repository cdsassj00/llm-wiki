#!/usr/bin/env python3
"""그래프를 빌드하고 localhost 브릿지를 중복 없이 시작한 뒤 브라우저를 연다."""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from agent_bridge import HOST, root_fingerprint
from wiki_paths import find_wiki_root

PORT_SCAN_COUNT = 20
START_TIMEOUT_SECONDS = 12
ENV_NAMES = {
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "ANTHROPIC_API_KEY",
    "LLMWIKI_PROVIDER",
    "LLMWIKI_MODEL",
    "OPENROUTER_MODEL",
    "OPENAI_MODEL",
    "GEMINI_MODEL",
    "ANTHROPIC_MODEL",
    "LLMWIKI_AI_ENABLED",
    "LLMWIKI_ALLOW_PROVIDER_FALLBACK",
}


def load_workspace_env(root: Path) -> None:
    """Load literal KEY=VALUE lines only; never execute or expand content."""
    path = root / ".env"
    if not path.is_file():
        return
    for number, raw_line in enumerate(path.read_text("utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise RuntimeError(f".env {number}행은 KEY=VALUE 형식이어야 합니다.")
        name, value = line.split("=", 1)
        name = name.strip()
        if name not in ENV_NAMES:
            continue
        if "\x00" in value:
            raise RuntimeError(f".env {number}행에 허용되지 않은 문자가 있습니다.")
        os.environ.setdefault(name, value.strip())


def load_windows_user_env() -> None:
    """Make freshly saved user variables visible before Explorer restarts."""
    if os.name != "nt":
        return
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            for name in ENV_NAMES:
                if name in os.environ:
                    continue
                try:
                    value, _ = winreg.QueryValueEx(key, name)
                except FileNotFoundError:
                    continue
                if isinstance(value, str):
                    os.environ[name] = value
    except OSError:
        return


def health(port: int, timeout: float = 0.7) -> dict | None:
    try:
        with urllib.request.urlopen(
            f"http://{HOST}:{port}/health",
            timeout=timeout,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return None
    return payload if payload.get("service") == "llm-wiki-bridge" else None


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    return True


def run_builder(script_dir: Path, root: Path, name: str) -> None:
    script = script_dir / name
    if not script.is_file():
        raise RuntimeError(f"필수 빌더가 없습니다: {script}")
    completed = subprocess.run(
        [sys.executable, str(script), "--root", str(root)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"{name} 실행 실패(exit {completed.returncode}): {detail[:500]}"
        )


def ensure_views(script_dir: Path, root: Path, rebuild: bool) -> None:
    graph = root / "wiki" / "graph-view.html"
    constellation = root / "wiki" / "constellation.html"
    if rebuild or not graph.is_file():
        run_builder(script_dir, root, "build_graph_view.py")
    if rebuild or not constellation.is_file():
        run_builder(script_dir, root, "build_constellation_view.py")


def read_state(root: Path) -> dict | None:
    state_path = root / ".llmwiki" / "bridge.json"
    try:
        payload = json.loads(state_path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def write_state(root: Path, pid: int, port: int) -> None:
    state_dir = root / ".llmwiki"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "bridge.json").write_text(
        json.dumps(
            {
                "pid": pid,
                "port": port,
                "rootFingerprint": root_fingerprint(root),
            },
            indent=2,
        )
        + "\n",
        "utf-8",
    )


def remove_state(root: Path) -> None:
    try:
        (root / ".llmwiki" / "bridge.json").unlink()
    except FileNotFoundError:
        pass


def choose_port(root: Path, first_port: int) -> tuple[int, bool]:
    fingerprint = root_fingerprint(root)
    state = read_state(root)
    candidates: list[int] = []
    if state:
        try:
            candidates.append(int(state["port"]))
        except (KeyError, TypeError, ValueError):
            pass
    candidates.extend(range(first_port, first_port + PORT_SCAN_COUNT))

    checked: set[int] = set()
    for port in candidates:
        if port in checked or not 1 <= port <= 65535:
            continue
        checked.add(port)
        status = health(port)
        if status and status.get("rootFingerprint") == fingerprint:
            return port, True
    for port in range(first_port, min(65536, first_port + PORT_SCAN_COUNT)):
        if port_is_free(port):
            return port, False
    raise RuntimeError(
        f"{first_port}부터 {PORT_SCAN_COUNT}개 포트가 모두 사용 중입니다."
    )


def start_bridge(
    script_dir: Path,
    root: Path,
    port: int,
    view: str,
) -> int:
    state_dir = root / ".llmwiki"
    state_dir.mkdir(parents=True, exist_ok=True)
    log_handle = (state_dir / "bridge.log").open("a", encoding="utf-8")
    command = [
        sys.executable,
        str(script_dir / "agent_bridge.py"),
        "--root",
        str(root),
        "--port",
        str(port),
        "--view",
        view,
    ]
    kwargs: dict = {
        "cwd": root,
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
        "shell": False,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    else:
        kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(command, **kwargs)
    finally:
        log_handle.close()

    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    fingerprint = root_fingerprint(root)
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"브릿지가 시작 직후 종료되었습니다(exit {process.returncode}). "
                f"로그: {state_dir / 'bridge.log'}"
            )
        status = health(port)
        if status and status.get("rootFingerprint") == fingerprint:
            write_state(root, process.pid, port)
            return process.pid
        time.sleep(0.2)
    process.terminate()
    raise RuntimeError(
        f"브릿지가 {START_TIMEOUT_SECONDS}초 안에 응답하지 않았습니다. "
        f"로그: {state_dir / 'bridge.log'}"
    )


def stop_bridge(root: Path) -> int:
    state = read_state(root)
    if not state:
        print("기록된 브릿지 프로세스가 없습니다.")
        return 0
    try:
        pid = int(state["pid"])
        port = int(state["port"])
    except (KeyError, TypeError, ValueError):
        remove_state(root)
        print("손상된 브릿지 상태 파일을 정리했습니다.")
        return 0
    status = health(port)
    if not status or status.get("rootFingerprint") != root_fingerprint(root):
        remove_state(root)
        print("해당 workspace의 실행 중인 브릿지를 찾지 못했습니다.")
        return 0
    if status.get("pid") != pid:
        remove_state(root)
        print("브릿지 PID가 상태 파일과 달라 안전을 위해 종료하지 않았습니다.")
        return 1
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                check=False,
                shell=False,
            )
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        print(f"프로세스 종료 실패: {exc}", file=sys.stderr)
        return 1
    remove_state(root)
    print(f"브릿지를 종료했습니다(pid={pid}, port={port}).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM Wiki one-click launcher")
    parser.add_argument("--root", default=None, help="Wiki workspace root")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--view",
        choices=("constellation.html", "graph-view.html"),
        default="constellation.html",
    )
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port는 1~65535 범위여야 합니다.")

    root = find_wiki_root(args.root)
    try:
        load_workspace_env(root)
        load_windows_user_env()
    except RuntimeError as exc:
        print(f"환경 설정 오류: {exc}", file=sys.stderr)
        return 1
    if args.stop:
        return stop_bridge(root)
    script_dir = Path(__file__).resolve().parent
    try:
        ensure_views(script_dir, root, args.rebuild)
        port, already_running = choose_port(root, args.port)
        pid = None if already_running else start_bridge(
            script_dir,
            root,
            port,
            args.view,
        )
    except RuntimeError as exc:
        print(f"실행 실패: {exc}", file=sys.stderr)
        return 1

    url = f"http://{HOST}:{port}/{args.view}"
    result = {
        "url": url,
        "port": port,
        "alreadyRunning": already_running,
        "pid": pid,
        "log": str(root / ".llmwiki" / "bridge.log"),
        "stopCommand": (
            f'"{sys.executable}" "{script_dir / "launch_wiki.py"}" '
            f'--root "{root}" --stop'
        ),
    }
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False))
    else:
        state = "기존 브릿지 사용" if already_running else f"브릿지 시작(pid={pid})"
        print(f"{state}: {url}")
        print(f"로그: {result['log']}")
        print(f"종료: {result['stopCommand']}")
    if not args.no_browser:
        webbrowser.open(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
