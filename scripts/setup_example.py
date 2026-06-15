#!/usr/bin/env python3
"""Set up a single example: create a venv, install its requirements.

Works the same on Windows, macOS, and Linux — uses sys.executable + pathlib
so there's no python3/python.exe drift and no bash/.venv/bin/activate vs
.venv\\Scripts\\activate.bat split inside this script.

Usage:
    python scripts/setup_example.py 01-hello-waxell
    py -3 scripts/setup_example.py 01-hello-waxell         (Windows alt)
    python scripts/setup_example.py examples/01-hello-waxell

After this finishes, activate the venv. The command differs per platform —
the script prints the right one when it's done.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"


def fail(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def list_examples() -> None:
    if not EXAMPLES_DIR.is_dir():
        return
    print("available examples:", file=sys.stderr)
    for p in sorted(EXAMPLES_DIR.iterdir()):
        if p.is_dir():
            print(f"  {p.name}", file=sys.stderr)


def find_python() -> list[str]:
    """Return a Python launcher cmd that targets 3.12 or 3.13.

    waxell-observe is Cython-compiled and ships only cp312/cp313 wheels;
    newer Pythons (3.14+) get "No matching distribution found". Older
    ones miss Cython features.

    Tries Windows `py` launcher first on Windows, then named Python
    binaries, then the current interpreter as a last resort.
    """
    candidates: list[list[str]]
    if os.name == "nt":
        candidates = [
            ["py", "-3.13"],
            ["py", "-3.12"],
            ["python3.13"],
            ["python3.12"],
            ["python"],
        ]
    else:
        candidates = [
            ["python3.13"],
            ["python3.12"],
            ["python3"],
            [sys.executable],
        ]

    for cmd in candidates:
        try:
            out = subprocess.run(
                cmd + [
                    "-c",
                    "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            version = out.stdout.strip()
            if version in ("3.12", "3.13"):
                return cmd
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue

    return [sys.executable]


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def activate_hint(venv_dir: Path) -> str:
    if os.name == "nt":
        return f"{venv_dir}\\Scripts\\activate.bat"
    return f"source {venv_dir}/bin/activate"


def main() -> None:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <example-name>", file=sys.stderr)
        list_examples()
        sys.exit(1)

    arg = sys.argv[1].replace("\\", "/")
    name = arg.split("/")[-1] if "/" in arg else arg

    example_dir = EXAMPLES_DIR / name
    if not example_dir.is_dir():
        fail(f"example not found at {example_dir}")

    requirements = example_dir / "requirements.txt"
    if not requirements.is_file():
        fail(f"{example_dir} has no requirements.txt")

    env_file = REPO_ROOT / ".env"
    if not env_file.is_file():
        fail(
            f"{env_file} missing. "
            f"Run: python scripts/seed_env_from_wax.py"
        )

    has_key = False
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("WAXELL_API_KEY=") and line.split("=", 1)[1].strip():
            has_key = True
            break
    if not has_key:
        fail(
            "WAXELL_API_KEY is empty in .env\n"
            "       run: python scripts/seed_env_from_wax.py"
        )

    venv_dir = example_dir / ".venv"
    if not venv_dir.is_dir():
        py = find_python()
        print(f"creating venv at {venv_dir}")
        try:
            subprocess.run(py + ["-m", "venv", str(venv_dir)], check=True)
        except subprocess.CalledProcessError as exc:
            fail(f"venv creation failed: {exc}")

    vpy = venv_python(venv_dir)
    if not vpy.exists():
        fail(f"expected python at {vpy} after venv create — something went wrong")

    print("upgrading pip...")
    subprocess.run(
        [str(vpy), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
        check=True,
    )

    print("installing requirements...")
    subprocess.run(
        [str(vpy), "-m", "pip", "install", "--quiet", "--pre", "-r", str(requirements)],
        check=True,
    )

    print()
    print("ready. to run:")
    print(f"  {activate_hint(venv_dir)}")
    sep = "\\" if os.name == "nt" else "/"
    print(f"  python {example_dir}{sep}agent.py")
    print()
    print(f"see {example_dir / 'README.md'} for what to look for in the Waxell UI.")


if __name__ == "__main__":
    main()
