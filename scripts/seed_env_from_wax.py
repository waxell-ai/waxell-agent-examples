#!/usr/bin/env python3
"""Seed .env from your local wax profile.

Reads ~/.waxell/config (the file `wax config show` reports), pulls the
api_key + api_url from the chosen profile, and writes them into the
repo-root .env. Provider keys (OPENAI_API_KEY etc.) are preserved if
the .env already exists — only the WAXELL_* lines are overwritten.

Cross-platform replacement for the legacy seed-env-from-wax.sh — works
the same on Windows, macOS, and Linux. No bash / awk / sed dependency.

Usage:
    python scripts/seed_env_from_wax.py               # uses [default]
    python scripts/seed_env_from_wax.py my-profile    # uses [my-profile]

Output: .env at the repo root.
"""

from __future__ import annotations

import configparser
import os
import shutil
import stat
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def wax_config_path() -> Path:
    override = os.environ.get("WAXELL_CONFIG_FILE")
    if override:
        return Path(override)
    return Path.home() / ".waxell" / "config"


def fail(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def read_profile(config_file: Path, profile: str) -> tuple[str, str]:
    if not config_file.is_file():
        fail(
            f"wax config not found at {config_file}\n"
            f"       run `wax setup` first, then re-run this script."
        )

    parser = configparser.ConfigParser(
        comment_prefixes=("#", ";"),
        inline_comment_prefixes=("#",),
    )
    try:
        parser.read(config_file, encoding="utf-8")
    except configparser.Error as exc:
        fail(f"failed to parse {config_file}: {exc}")

    if not parser.has_section(profile):
        available = "\n".join(f"  [{s}]" for s in parser.sections())
        fail(
            f"profile [{profile}] not in {config_file}\n"
            f"available profiles:\n{available}"
        )

    api_key = parser.get(profile, "api_key", fallback="").strip()
    if not api_key:
        fail(f"profile [{profile}] in {config_file} has no api_key")

    api_url = parser.get(profile, "api_url", fallback="").strip()
    if not api_url:
        api_url = "https://api.waxell.dev"

    return api_key, api_url


def confirm_overwrite(existing: str, new: str, profile: str) -> bool:
    if not existing or existing == new:
        return True
    print(
        f"warning: {ENV_FILE} already has a different WAXELL_API_KEY "
        f"({existing[:12]}…)",
        file=sys.stderr,
    )
    try:
        ans = input(
            f"overwrite with profile [{profile}] key ({new[:12]}…)? [y/N] "
        ).strip().lower()
    except EOFError:
        ans = ""
    return ans in ("y", "yes")


def patch_env_lines(text: str, api_key: str, api_url: str) -> str:
    out = []
    seen_key = False
    seen_url = False
    for line in text.splitlines():
        if line.startswith("WAXELL_API_KEY="):
            out.append(f"WAXELL_API_KEY={api_key}")
            seen_key = True
        elif line.startswith("WAXELL_API_URL="):
            out.append(f"WAXELL_API_URL={api_url}")
            seen_url = True
        else:
            out.append(line)
    if not seen_key:
        out.append(f"WAXELL_API_KEY={api_key}")
    if not seen_url:
        out.append(f"WAXELL_API_URL={api_url}")
    return "\n".join(out) + "\n"


def main() -> None:
    profile = sys.argv[1] if len(sys.argv) > 1 else "default"
    api_key, api_url = read_profile(wax_config_path(), profile)

    if ENV_FILE.is_file():
        existing_text = ENV_FILE.read_text(encoding="utf-8", errors="replace")
        existing_key = ""
        for line in existing_text.splitlines():
            if line.startswith("WAXELL_API_KEY="):
                existing_key = line.split("=", 1)[1].strip()
                break
        if not confirm_overwrite(existing_key, api_key, profile):
            print("aborted.")
            return
        new_text = patch_env_lines(existing_text, api_key, api_url)
    else:
        if ENV_EXAMPLE.is_file():
            base = ENV_EXAMPLE.read_text(encoding="utf-8", errors="replace")
        else:
            base = ""
        new_text = patch_env_lines(base, api_key, api_url)

    ENV_FILE.write_text(new_text, encoding="utf-8")

    # On POSIX, lock the file down to user-only — it carries a secret.
    # Windows doesn't honor 0600 in the same way; skip silently there
    # (the parent dir's ACL is the user's normal home permissions).
    if os.name != "nt":
        try:
            os.chmod(ENV_FILE, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    suffix = f"…{api_key[-4:]}" if len(api_key) > 16 else ""
    print(f"wrote {ENV_FILE} from wax profile [{profile}]")
    print(f"  WAXELL_API_KEY={api_key[:12]}{suffix}")
    print(f"  WAXELL_API_URL={api_url}")
    print()
    print(
        "next: add provider keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, ...) "
        f"to {ENV_FILE}"
    )
    print("      see each example's README for which keys it needs.")


if __name__ == "__main__":
    main()
