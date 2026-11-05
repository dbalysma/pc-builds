#!/usr/bin/env python3
"""Safety-net audit for everything committed to this repository.

It fails if a tracked file contains anything that must never be published here:
- prices or amounts;
- e-mail addresses, UK phone numbers or UK postcodes;
- order, tracking or invoice numbers;
- serial numbers, UUIDs, MAC, IPv4 or IPv6 addresses;
- home-directory paths or AI session links;
- the private-evidence banner written by the collectors;
- images carrying EXIF, XMP or text metadata;
- file types that aren't allowed, or files over 5 MB.

The collectors' allowlists are the primary control. This audit catches mistakes; it is
not proof that a file is safe.

Usage:
  python3 tools/audit_public.py          # audit files tracked by git
  python3 tools/audit_public.py PATH...  # audit specific files or folders
"""

from __future__ import annotations

import re
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from privacy import find_ipv6  # noqa: E402

# UK numbers: a leading 0 or +44 (optionally "+44 (0)"), then a 9- or 10-digit national number that does
# not start with 0, in groups separated by single spaces or hyphens (area code optionally in brackets). Covers mobiles (07...), London and
# other geographic numbers (020..., 01..., 03...) and freephone (08...).
UK_PHONE_CANDIDATE = re.compile(
    r"(?<![\w+])(\+44[\s-]?(?:\(0\)[\s-]?)?|\(0|0)(\d{2,5}\)?(?:[\s-]?\d{2,4}){1,3})(?!\w)")


def uk_phone_numbers(text: str) -> list[str]:
    found = []
    for m in UK_PHONE_CANDIDATE.finditer(text):
        national = re.sub(r"\D", "", m.group(2))
        if 9 <= len(national) <= 10 and national[0] != "0":
            found.append(m.group(0))
    return found


class _Check:
    """Adapts a function returning matches to the .search() interface used by RULES."""

    def __init__(self, fn):
        self.fn = fn

    def search(self, text: str):
        return self.fn(text) or None


MAX_BYTES = 5 * 1024 * 1024
BLOCKED_SUFFIXES = {
    ".heic", ".heif", ".mov", ".mp4", ".m4v", ".avi", ".mkv", ".zip", ".7z", ".rar", ".gz",
    ".pdf", ".docx", ".xlsx", ".pptx", ".sqlite", ".db", ".pth", ".pt", ".onnx", ".log",
}
TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".sh", ".ps1", ".json", ".csv", ".yml", ".yaml", ".toml", ".cfg",
    ".ini", ".gitignore", ".svg", "",
}

RULES: list[tuple[str, re.Pattern | _Check]] = [
    # "$1"-style shell arguments are allowed; "$12" or "$9.99" are not.
    ("price or amount", re.compile(r"[£€]\s?\d|\$\s?\d{2,}|\$\s?\d+[.,]\d|\b\d[\d,.]*\s?(?:GBP|EUR|USD|pounds?|quid)\b", re.I)),
    ("e-mail address", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("UK phone number", _Check(uk_phone_numbers)),
    ("IPv6 address", _Check(find_ipv6)),
    # Inward codes never use C, I, K, M, O or V; "M2 2TB"-style capacities are not postcodes.
    ("UK postcode", re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s+\d(?!(?:TB|GB|MB|KB)\b)[ABD-HJLNP-UW-Z]{2}\b")),
    ("order, tracking or invoice number",
     re.compile(r"\b(?:order|tracking|invoice|consignment)\s*(?:no\.?|number|ref(?:erence)?|id|#)?\s*[:#]?\s*"
                r"(?=[A-Z0-9-]*\d)[A-Z0-9-]{6,}\b", re.I)),
    ("serial number", re.compile(r"serial\s*(?:number|no\.?)?\s*[:=]\s*(?!<serial>)\S+", re.I)),
    ("UUID", re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b|\bGPU-[0-9a-fA-F]{8}")),
    ("MAC address", re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")),
    ("IP address", re.compile(r"(?<![\d.])(?!127\.0\.0\.1(?!\d|\.\d))(?!0\.0\.0\.0(?!\d|\.\d))(?:\d{1,3}\.){3}\d{1,3}(?!\d|\.\d)")),
    ("home-directory path", re.compile(r"/home/(?!<user>)[^/\s<'\"`]+|[A-Za-z]:\\Users\\(?!<user>)[^\\\s<]+", re.I)),
    ("AI session link", re.compile(r"claude\.ai/(?:code/)?(?:session|chat|share)|chatgpt\.com/(?:c|share|codex)/", re.I)),
    ("private evidence file", re.compile(r"PRIVATE EVIDENCE: review before sharing")),
]

# This file and its tests necessarily contain the patterns they look for.
SELF_EXEMPT = {"tools/audit_public.py", "tests/test_audit_public.py", "tools/privacy.py", "tests/test_privacy.py"}


def jpeg_metadata(data: bytes) -> list[str]:
    found, i = [], 2
    while i + 4 <= len(data) and data[i] == 0xFF:
        marker = data[i + 1]
        if marker in (0xD9, 0xDA):  # end of image / start of scan
            break
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        payload = data[i + 4:i + 2 + length]
        if marker == 0xE1:
            found.append("XMP" if payload.startswith(b"http://ns.adobe.com/xap") else "EXIF (APP1)")
        elif marker == 0xED:
            found.append("Photoshop/IPTC (APP13)")
        elif marker == 0xFE:
            found.append("JPEG comment")
        i += 2 + length
    return found


PNG_TEXT_CHUNKS = {b"eXIf", b"tEXt", b"iTXt", b"zTXt", b"tIME"}


def png_metadata(data: bytes) -> list[str]:
    found, i = [], 8
    while i + 8 <= len(data):
        length, ctype = struct.unpack(">I4s", data[i:i + 8])
        if ctype in PNG_TEXT_CHUNKS:
            found.append(f"PNG {ctype.decode()} chunk")
        if ctype == b"IEND":
            break
        i += 12 + length
    return found


def audit_file(path: Path, rel: str) -> list[str]:
    problems: list[str] = []
    suffix = path.suffix.lower() if path.name != ".gitignore" else ".gitignore"
    if path.is_symlink():
        return [f"{rel}: symlinks are not allowed"]
    size = path.stat().st_size
    if size > MAX_BYTES:
        problems.append(f"{rel}: larger than 5 MB ({size} bytes)")
    if suffix in BLOCKED_SUFFIXES:
        problems.append(f"{rel}: file type {suffix} is not allowed in this repository")
        return problems
    data = path.read_bytes()
    if suffix in (".jpg", ".jpeg"):
        problems += [f"{rel}: image metadata ({m}); strip it before committing" for m in jpeg_metadata(data)]
        return problems
    if suffix == ".png":
        problems += [f"{rel}: image metadata ({m}); strip it before committing" for m in png_metadata(data)]
        return problems
    if suffix not in TEXT_SUFFIXES:
        problems.append(f"{rel}: unrecognised file type {suffix or '(none)'}; add it to the audit deliberately")
        return problems
    if rel in SELF_EXEMPT:
        return problems
    text = data.decode("utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, pattern in RULES:
            if pattern.search(line):
                problems.append(f"{rel}:{lineno}: {name}")
    return problems


def tracked_files(root: Path) -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True)
    return [root / p for p in out.stdout.decode().split("\0") if p]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = Path(__file__).resolve().parent.parent
    if argv:
        files = []
        for a in map(Path, argv):
            files += [p for p in a.rglob("*") if p.is_file() and ".git" not in p.parts] if a.is_dir() else [a]
    else:
        files = tracked_files(root)
    problems = []
    for f in files:
        try:
            rel = f.resolve().relative_to(root).as_posix()
        except ValueError:
            rel = f.as_posix()
        problems += audit_file(f, rel)
    for p in problems:
        print(f"FAIL {p}")
    print(f"{'FAIL' if problems else 'PASS'}: audited {len(files)} files, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
