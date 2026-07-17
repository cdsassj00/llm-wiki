#!/usr/bin/env python3
"""문서를 LLM Wiki 워크스페이스로 인제스트한다.

원본을 raw/sources/ 에 보관하고(불변), 마크다운 텍스트로 변환해
raw/extracted/<이름>.md 에 저장한다. 변환된 마크다운을 에이전트(Claude Code)가
읽고 wiki/ 페이지로 컴파일한다.

변환 전략
  - markitdown: pdf, docx, pptx, xlsx, xls, csv, json, html, txt, md, epub …
  - LibreOffice 헤드리스: hwp, hwpx, ppt(구형), doc(구형) → pdf 로 변환 후 markitdown
  - hwpx 가 LibreOffice 로 안 되면 pyhwpx 폴백(설치 시)

사용법
  python tools/ingest.py <파일_또는_폴더> [...]
  python tools/ingest.py ~/Downloads/논문.pdf ~/문서/회의록.hwp
  python tools/ingest.py ~/Downloads            # 폴더 전체 스캔
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

from wiki_paths import find_wiki_root

ROOT: Path = Path()  # main()에서 설정
SOURCES: Path = Path()
EXTRACTED: Path = Path()
MANIFEST: Path = Path()


def _bind_root(root: Path) -> None:
    global ROOT, SOURCES, EXTRACTED, MANIFEST
    ROOT = root
    SOURCES = ROOT / "raw" / "sources"
    EXTRACTED = ROOT / "raw" / "extracted"
    MANIFEST = ROOT / ".llmwiki" / "manifest.json"

# 그냥 읽으면 되는 텍스트 형식 (무거운 의존성 불필요)
PLAIN_EXT = {".txt", ".md", ".markdown", ".csv", ".json", ".xml", ".log"}
HTML_EXT = {".html", ".htm"}
# markitdown 이 처리하는 바이너리 형식
MARKITDOWN_EXT = {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".epub"}
# LibreOffice 변환이 필요한 형식 (구형/한컴)
LIBREOFFICE_EXT = {".hwp", ".hwpx", ".ppt", ".doc", ".odt", ".rtf"}

SUPPORTED_EXT = PLAIN_EXT | HTML_EXT | MARKITDOWN_EXT | LIBREOFFICE_EXT


def log(msg: str) -> None:
    # Windows cp949 환경에서도 이모지·한글이 깨지지 않도록 utf-8 출력 강제
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="backslashreplace"))
        sys.stdout.buffer.flush()


def slugify(name: str) -> str:
    stem = Path(name).stem.lower()
    stem = re.sub(r"[^\w가-힣]+", "-", stem, flags=re.UNICODE)
    stem = stem.strip("-")
    return (stem or "untitled")[:80]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> list[dict]:
    try:
        return json.loads(MANIFEST.read_text("utf-8"))
    except Exception:
        return []


def save_manifest(entries: list[dict]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(entries, ensure_ascii=False, indent=2), "utf-8")


# ── 변환기 ─────────────────────────────────────────────────────

def _markitdown(path: Path) -> str:
    try:
        from markitdown import MarkItDown
    except ImportError:
        raise RuntimeError(
            "markitdown 미설치. `pip install -r tools/requirements.txt` 를 실행하세요."
        )
    result = MarkItDown().convert(str(path))
    return result.text_content or ""


def _pptx_fallback(path: Path) -> str:
    """MarkItDown 이 손상된 이미지 등으로 실패할 때 PPTX 슬라이드 XML에서 텍스트만 추출."""
    slide_re = re.compile(r"ppt/slides/slide(\d+)\.xml$")
    lines: list[str] = []
    with zipfile.ZipFile(path) as zf:
        slides = []
        for name in zf.namelist():
            match = slide_re.match(name)
            if match:
                slides.append((int(match.group(1)), name))
        for number, name in sorted(slides):
            root = ElementTree.fromstring(zf.read(name))
            parts = [
                html.unescape(node.text)
                for node in root.iter()
                if node.tag.endswith("}t") and node.text
            ]
            text = "\n".join(part.strip() for part in parts if part.strip()).strip()
            if text:
                lines.append(f"## Slide {number}\n\n{text}")
    if not lines:
        raise RuntimeError(f"PPTX 텍스트 폴백 실패: {path.name}")
    return "\n\n".join(lines)


def _find_soffice() -> str | None:
    for cand in ("soffice", "libreoffice", "soffice.exe"):
        if shutil.which(cand):
            return cand
    # PATH에 없을 때 흔한 설치 경로 직접 확인
    candidates = [
        # Windows (기본 설치 시 PATH 미등록)
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        # macOS
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
        # Linux
        Path("/usr/bin/soffice"),
        Path("/usr/bin/libreoffice"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _libreoffice_to_pdf(path: Path) -> Path:
    soffice = _find_soffice()
    if not soffice:
        raise RuntimeError(
            f"{path.suffix} 변환에는 LibreOffice가 필요합니다. "
            "설치: https://www.libreoffice.org (mac: `brew install --cask libreoffice`)"
        )
    tmp = Path(tempfile.mkdtemp(prefix="llmwiki_"))
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(path)],
        check=True, capture_output=True, timeout=180,
    )
    pdfs = list(tmp.glob("*.pdf"))
    if not pdfs:
        raise RuntimeError(f"LibreOffice 변환 실패: {path.name}")
    return pdfs[0]


def _hwpx_fallback(path: Path) -> str:
    """LibreOffice 로 hwpx 가 안 될 때 pyhwpx 또는 HWPX ZIP 텍스트 폴백."""
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            if "Preview/PrvText.txt" in names:
                raw = zf.read("Preview/PrvText.txt")
                text = raw.decode("utf-8", errors="replace").strip()
                if text:
                    return text
            lines: list[str] = []
            for name in sorted(n for n in names if n.startswith("Contents/section") and n.endswith(".xml")):
                root = ElementTree.fromstring(zf.read(name))
                for para in root.iter():
                    if not para.tag.endswith("}p"):
                        continue
                    parts = [
                        html.unescape(node.text)
                        for node in para.iter()
                        if node.tag.endswith("}t") and node.text
                    ]
                    line = "".join(parts).strip()
                    if line:
                        lines.append(line)
            text = "\n".join(lines).strip()
            if text:
                return text
    except zipfile.BadZipFile:
        pass
    except ElementTree.ParseError:
        pass

    try:
        import pyhwpx  # type: ignore
    except ImportError:
        raise RuntimeError(
            "hwpx 변환 실패. LibreOffice 최신 버전 또는 `pip install pyhwpx` 가 필요합니다."
        )
    doc = pyhwpx.Hwp(visible=False)
    doc.open(str(path))
    text = doc.get_text()
    doc.quit()
    return text if isinstance(text, str) else "\n".join(text)


def _html_to_text(path: Path) -> str:
    raw = path.read_text("utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</(p|div|h[1-6]|li|tr)>", "\n", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in PLAIN_EXT:
        return path.read_text("utf-8", errors="replace")
    if ext in HTML_EXT:
        return _html_to_text(path)
    if ext in MARKITDOWN_EXT:
        try:
            return _markitdown(path)
        except Exception as e:
            if ext == ".pptx":
                return _pptx_fallback(path)
            raise e
    if ext in LIBREOFFICE_EXT:
        try:
            pdf = _libreoffice_to_pdf(path)
            return _markitdown(pdf)
        except Exception as e:
            if ext == ".hwpx":
                return _hwpx_fallback(path)
            raise e
    # 알 수 없는 형식: 텍스트로 시도
    return path.read_text("utf-8", errors="replace")


def link_or_copy(src: Path, dest: Path, mode: str) -> str:
    """원본 src 를 dest 에 보관한다. 실제로 사용된 방식 문자열을 반환.

    mode:
      copy     - 항상 복사
      symlink  - 심볼릭 링크 (실패 시 OSError 전파)
      hardlink - 하드 링크 (실패 시 OSError 전파)
      auto     - symlink → hardlink → copy 순으로 시도, 첫 성공 방식을 반환
    """
    target = src.resolve()

    def _symlink() -> None:
        dest.unlink(missing_ok=True)
        os.symlink(target, dest)

    def _hardlink() -> None:
        dest.unlink(missing_ok=True)
        os.link(target, dest)

    def _copy() -> None:
        dest.unlink(missing_ok=True)
        shutil.copy2(src, dest)

    if mode == "copy":
        _copy()
        return "copy"
    if mode == "symlink":
        _symlink()
        return "symlink"
    if mode == "hardlink":
        _hardlink()
        return "hardlink"
    if mode == "auto":
        for name, fn in (("symlink", _symlink), ("hardlink", _hardlink), ("copy", _copy)):
            try:
                fn()
                return name
            except OSError:
                continue
        raise RuntimeError(f"보관 실패(모든 방식 실패): {src}")
    raise ValueError(f"알 수 없는 link 모드: {mode}")


# ── 메인 ───────────────────────────────────────────────────────

def collect_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        path = Path(p).expanduser()
        if path.is_dir():
            files += [f for f in sorted(path.rglob("*")) if f.suffix.lower() in SUPPORTED_EXT]
        elif path.is_file():
            files.append(path)
        else:
            log(f"⚠️  경로 없음: {p}")
    return files


def ingest_one(path: Path, manifest: list[dict], link_mode: str = "copy") -> dict | None:
    digest = sha256(path)
    if any(m["sha256"] == digest for m in manifest):
        log(f"⏭  중복 건너뜀: {path.name}")
        return None

    slug = f"{slugify(path.name)}-{digest[:8]}"
    dest = SOURCES / f"{slug}{path.suffix.lower()}"
    SOURCES.mkdir(parents=True, exist_ok=True)
    EXTRACTED.mkdir(parents=True, exist_ok=True)

    storage = link_or_copy(path, dest, link_mode)
    icon = "🔗" if storage in ("symlink", "hardlink") else "📄"
    note = " — 링크 불가하여 복사함" if (link_mode == "auto" and storage == "copy") else ""
    log(f"{icon} 보관: {dest.relative_to(ROOT)} ({storage}{note})")

    log(f"📄 {path.name} → 텍스트 추출 중…")
    text = extract_text(path)
    if not text.strip():
        log(f"⚠️  텍스트 비어 있음: {path.name}")

    out_md = EXTRACTED / f"{slug}.md"
    header = (
        f"<!-- 원본: {path.name} | 형식: {path.suffix.lower()} "
        f"| 추출: {datetime.now().isoformat(timespec='seconds')} -->\n\n"
    )
    out_md.write_text(header + text, "utf-8")

    entry = {
        "id": digest[:12],
        "original_name": path.name,
        "source_path": str(dest.relative_to(ROOT)),
        "extracted_path": str(out_md.relative_to(ROOT)),
        "sha256": digest,
        "char_count": len(text),
        "storage": storage,
        "origin_path": str(path.resolve()),
        "status": "extracted",  # extracted → (에이전트가 컴파일하면) compiled
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    log(f"✅ 추출 완료: {out_md.relative_to(ROOT)} ({len(text):,}자)")
    return entry


def main() -> int:
    ap = argparse.ArgumentParser(description="문서를 LLM Wiki로 인제스트")
    ap.add_argument("paths", nargs="+", help="파일 또는 폴더 경로")
    ap.add_argument("--root", default=None, help="Wiki workspace 루트")
    ap.add_argument(
        "--link",
        nargs="?",
        const="auto",
        default="copy",
        choices=["auto", "symlink", "hardlink", "copy"],
        help="원본 보관 방식: 옵션 생략=copy, --link=auto(심링크→하드링크→복사 폴백), "
             "또는 symlink/hardlink/copy 강제. auto/심링크로 디스크 절약.",
    )
    args = ap.parse_args()
    _bind_root(find_wiki_root(args.root))

    files = collect_files(args.paths)
    if not files:
        log("처리할 지원 문서가 없습니다. 지원 형식: " + ", ".join(sorted(SUPPORTED_EXT)))
        return 1

    manifest = load_manifest()
    added: list[dict] = []
    for f in files:
        try:
            entry = ingest_one(f, manifest, args.link)
            if entry:
                manifest.append(entry)
                added.append(entry)
        except Exception as e:  # noqa: BLE001
            log(f"❌ 실패: {f.name} — {e}")

    save_manifest(manifest)
    log("")
    log(f"── 완료: {len(added)}개 신규 추출, 전체 {len(manifest)}개 ──")
    if added:
        log("다음 단계: Claude Code에게 '새 추출 문서를 위키로 컴파일해줘' 라고 요청하세요.")
        for e in added:
            log(f"  • {e['extracted_path']}  ({e['original_name']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
