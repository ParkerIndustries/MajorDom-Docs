#!/usr/bin/env python3
"""Pack each repo in ``llms_sources.yml`` into a single text file for the docs' unindexed llms
endpoints.

For every entry it shallow-clones the repo at its branch, concatenates the text source (sensible
excludes, no binaries/lockfiles) into ``docs/llms/<name>.txt``, and records the built commit SHAs
in ``docs/llms/manifest.json``. The MkDocs hook (``majordom_docs/llms_hook.py``) then links these
from ``llms.txt`` and appends them to ``llms-full.txt`` at build time.

Run by ``.github/workflows/llms-refresh.yml`` (weekly) and manually:  ``python scripts/build_llms.py``
"""

from __future__ import annotations

import datetime
import json
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "llms_sources.yml"
OUT_DIR = ROOT / "docs" / "llms"

# Pack text source only; skip binaries, lockfiles, caches, and vendored/build output.
TEXT_SUFFIXES = {
    ".py", ".pyi", ".md", ".txt", ".rst", ".toml", ".yml", ".yaml", ".cfg", ".ini",
    ".sh", ".json", ".env", ".dockerfile",
}
INCLUDE_NAMES = {"Dockerfile", "README", "LICENSE", "Makefile", ".gitignore", ".dockerignore"}
EXCLUDE_DIRS = {
    ".git", ".github", "__pycache__", ".venv", "venv", "node_modules", "dist", "build", "site",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".cache", "htmlcov", "bins",
}
EXCLUDE_NAMES = {"poetry.lock", "package-lock.json", "uv.lock", "Pipfile.lock"}
MAX_FILE_BYTES = 200_000  # anything bigger is almost certainly a blob, not source


def _is_text(path: Path) -> bool:
    if path.name in EXCLUDE_NAMES:
        return False
    if path.name in INCLUDE_NAMES or path.name.startswith("Dockerfile"):
        return True
    return path.suffix.lower() in TEXT_SUFFIXES


def _source_files(repo: Path) -> list[Path]:
    files = []
    for path in sorted(repo.rglob("*")):
        if path.is_dir():
            continue
        rel_parts = path.relative_to(repo).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        if not _is_text(path):
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        files.append(path)
    return files


def pack_repo(name: str, url: str, branch: str) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, url, tmp],
            check=True, capture_output=True,
        )
        sha = subprocess.run(
            ["git", "-C", tmp, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()

        repo = Path(tmp)
        files = _source_files(repo)
        out = [
            f"# {name} — full source",
            f"# repo: {url}  branch: {branch}  commit: {sha}",
            f"# generated: {datetime.date.today().isoformat()} — AUTO-GENERATED, do not edit by hand",
            "",
            "## File tree",
            *(f"  {p.relative_to(repo)}" for p in files),
            "",
        ]
        for path in files:
            rel = path.relative_to(repo)
            out.append(f"\n{'=' * 80}\n# FILE: {rel}\n{'=' * 80}")
            try:
                out.append(path.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                out.append("<non-utf8 file skipped>")
        return sha, "\n".join(out) + "\n"


def main() -> None:
    config = yaml.safe_load(CONFIG.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    for entry in config.get("integrations", []):
        name, url = entry["name"], entry["repo"]
        branch = entry.get("branch", "master")
        sha, text = pack_repo(name, url, branch)
        (OUT_DIR / f"{name}.txt").write_text(text, encoding="utf-8")
        manifest[name] = {"repo": url, "branch": branch, "commit": sha}
        print(f"  packed {name} @ {sha[:10]}  ({len(text):,} chars)")
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {OUT_DIR / 'manifest.json'} ({len(manifest)} sources)")


if __name__ == "__main__":
    main()
