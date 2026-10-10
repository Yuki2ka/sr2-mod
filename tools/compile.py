#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compile.py — headless build driver for the SR2HD mods in this repo.

Every path is a variable: pass them as CLI arguments, or set the matching
environment variable (see ENV FALLBACKS below). Nothing is hardcoded to a
machine. `run_compile.py` next to this file is the double-click front-end:
it holds the same values as plain variables at the top and calls this script.

Under the hood it drives `sr-modkit` (https://github.com/ArtYudin89/sr-modkit),
which needs exactly one foreign binary: rsmc.exe (Windows). Everything else
(DAT files, language table, CacheData) sr-modkit does in pure Python.

Stages
  lint    static checks of .rsm against rsmc's own DSL (no external tools)
  build   src/ -> build/  (needs rsmc.exe, Windows only)
  deploy  put build/ into the game (junction by default, or a plain copy)
  all     lint -> build -> deploy                       [default]

ENV FALLBACKS (used when the matching argument is omitted)
  SR2_SRMOD_ROOT   path to the sr-modkit clone (the dir containing srmod/)
  SR2_RSMC         path to rsmc.exe
  SR2_GAME         path to the game install root (the dir containing Mods/)
  SR2_MODKIT_ROOT  path to the SRHD-XenoModKit clone (optional audit)
  PYTHON           python interpreter used to run sr-modkit / ModKit

Exit codes: 0 ok | 1 setup/operational error | 2 lint findings or build gate
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MOD_DIR = REPO_ROOT / "mods" / "SbHello"

# Files the game reads only as UTF-16LE ("Notepad -> Unicode").
UTF16_FILES_GLOB = ("**/*.txt",)

UTF16_BOM_LE = b"\xff\xfe"
UTF16_BOM_BE = b"\xfe\xff"
UTF8_BOM = b"\xef\xbb\xbf"


# --------------------------------------------------------------------- logging
def log(stage: str, msg: str) -> None:
    print(f"[{stage:<9}] {msg}", flush=True)


def die(msg: str, code: int = 1) -> "NoReturn":  # type: ignore[valid-type]
    print(f"[error    ] {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


# --------------------------------------------------------------------- helpers
def first(*values):
    """First non-empty value wins (CLI args beat env vars beat defaults)."""
    for v in values:
        if v:
            return v
    return None


def is_utf16(data: bytes) -> bool:
    return data[:2] in (UTF16_BOM_LE, UTF16_BOM_BE)


def decode_text(data: bytes) -> tuple[str, str]:
    """Best-effort decode of a source .txt -> (text, encoding-name)."""
    if data[:2] == UTF16_BOM_LE:
        return data[2:].decode("utf-16-le"), "utf-16-le"
    if data[:2] == UTF16_BOM_BE:
        return data[2:].decode("utf-16-be"), "utf-16-be"
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("cp1251", errors="replace"), "cp1251(replaced)"


def to_utf16le(path: Path) -> bool:
    """Rewrite one .txt as UTF-16LE+BOM. Returns True if the file changed."""
    data = path.read_bytes()
    if data[:2] == UTF16_BOM_LE:
        return False
    text, _enc = decode_text(data)
    path.write_bytes(UTF16_BOM_LE + text.encode("utf-16-le"))
    return True


# --------------------------------------------------------------------- preflight
def preflight(args, mod_dir: Path) -> list[str]:
    """Sanity-check the machine before any subprocess runs. Returns problems."""
    problems: list[str] = []

    # 1. sr-modkit clone
    srmod_root = Path(args.srmod_root) if args.srmod_root else None
    if srmod_root is None:
        problems.append(
            "sr-modkit clone not found. Pass --srmod-root <path> or set "
            "SR2_SRMOD_ROOT to the folder that contains srmod/ (see docs/TOOLS.md)."
        )
    elif not (srmod_root / "srmod" / "__init__.py").is_file():
        problems.append(f"--srmod-root {srmod_root}: no srmod/__init__.py inside — wrong folder.")

    # 2. mod folder
    if not (mod_dir / "srmod.json").is_file():
        problems.append(f"{mod_dir}: no srmod.json — is --mod-dir pointing at a mod?")
    src_dir = mod_dir / "src"
    if not src_dir.is_dir():
        problems.append(f"{src_dir}: missing (expected the mod sources).")
    else:
        # 3. name must match in scriptName / srmod.json / entry path
        name_ok, name_msg = check_script_name(mod_dir)
        if not name_ok:
            problems.append(name_msg)

    # 4. encodings (the silent killers: no error at build, garbage in game)
    enc_problems, _fixable = check_encodings(mod_dir)
    problems.extend(enc_problems)

    # 5. build stage needs rsmc.exe, and rsmc.exe is Windows-only
    if args.stage in ("build", "deploy", "all"):
        if not args.rsmc:
            problems.append(
                "rsmc.exe path unknown. Pass --rsmc <path> or set SR2_RSMC "
                "(download: github.com/indiemagpie, RScript releases, rsmc.zip)."
            )
        elif not Path(args.rsmc).is_file():
            problems.append(f"--rsmc {args.rsmc}: file not found.")
        elif os.name != "nt":
            problems.append(
                f"rsmc.exe is a Windows binary and this machine is {sys.platform}. "
                "Run the build/deploy stages on Windows (or use --stage lint here)."
            )

    # 6. deploy needs the game folder
    if args.stage in ("deploy", "all"):
        if not args.game:
            problems.append(
                "game folder unknown. Pass --game <path> or set SR2_GAME "
                "(the folder that contains Mods/)."
            )
        elif not Path(args.game).is_dir():
            problems.append(f"--game {args.game}: folder not found.")

    # 7. optional audit
    if args.audit:
        mk = Path(args.modkit_root) if args.modkit_root else None
        if mk is None:
            problems.append("--audit needs --modkit-root (SRHD-XenoModKit clone) or SR2_MODKIT_ROOT.")
        elif not (mk / "srhd.py").is_file():
            problems.append(f"--modkit-root {mk}: no srhd.py inside — wrong folder.")

    return problems


def check_script_name(mod_dir: Path) -> tuple[bool, str]:
    """scriptName("X") in main.rsm must equal srmod.json "name"."""
    import json
    import re

    cfg = mod_dir / "srmod.json"
    entry_path = None
    try:
        proj = json.loads(cfg.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        return False, f"{cfg}: cannot read ({e})"
    name = proj.get("name")
    entry = (proj.get("script") or {}).get("entry")
    if entry:
        entry_path = mod_dir / entry
    if not name:
        return False, f"{cfg}: no \"name\"."
    if entry_path is None or not entry_path.is_file():
        return False, f"{cfg}: script.entry missing or not found on disk."
    text = entry_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"scriptName\s*\(\s*[\"']([^\"']+)[\"']\s*\)", text)
    if not m:
        return False, f"{entry_path}: no scriptName(\"...\") declaration."
    if m.group(1) != name:
        return False, (
            f"name mismatch: scriptName(\"{m.group(1)}\") in {entry_path.name} "
            f"but srmod.json says \"{name}\". All three must be identical."
        )
    return True, f"script name \"{name}\" matches srmod.json"


def check_encodings(mod_dir: Path) -> tuple[list[str], list[Path]]:
    """Check the two encoding rules. Returns (problems, files fixable)."""
    problems: list[str] = []
    fixable: list[Path] = []
    src = mod_dir / "src"
    if not src.is_dir():
        return problems, fixable

    for rsm in sorted(src.glob("**/*.rsm")):
        data = rsm.read_bytes()
        if data[:3] == UTF8_BOM:
            problems.append(f"{rsm.name}: .rsm must be UTF-8 WITHOUT BOM (found a BOM).")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as e:
            problems.append(f"{rsm.name}: .rsm is not valid UTF-8 ({e}).")

    for txt in sorted(src.glob("**/*.txt")):
        data = txt.read_bytes()
        if is_utf16(data):
            continue
        text, enc = decode_text(data)
        fixable.append(txt)
        if any(ord(ch) >= 0x80 for ch in text):
            problems.append(
                f"{txt.as_posix()}: must be UTF-16LE+BOM, found {enc}. "
                "Run again with --fix-encodings to convert in place."
            )
    return problems, fixable


def fix_encodings(mod_dir: Path) -> int:
    changed = 0
    for txt in sorted((mod_dir / "src").glob("**/*.txt")):
        if to_utf16le(txt):
            log("fix", f"{txt.as_posix()} -> UTF-16LE+BOM")
            changed += 1
    for rsm in sorted((mod_dir / "src").glob("**/*.rsm")):
        data = rsm.read_bytes()
        if data[:3] == UTF8_BOM:
            rsm.write_bytes(data[3:])
            log("fix", f"{rsm.as_posix()} -> UTF-8, BOM removed")
            changed += 1
    return changed


# --------------------------------------------------------------------- runners
def run(cmd: list[str], cwd: Path | None = None, env_extra: dict | None = None,
        timeout: int = 900) -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    if env_extra:
        env.update(env_extra)
    printable = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    if cwd:
        log("run", f"cd {cwd} && {printable}")
    else:
        log("run", printable)
    try:
        proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, timeout=timeout)
    except FileNotFoundError as e:
        raise RuntimeError(f"cannot start {cmd[0]}: {e}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"timed out after {timeout}s: {printable}")
    return proc.returncode


def srmod_cmd(args, *srmod_args: str) -> list[str]:
    return [args.python, "-m", "srmod", *srmod_args]


def srmod_env(args) -> dict:
    return {"PYTHONPATH": str(Path(args.srmod_root).resolve())}


def stage_lint(args, mod_dir: Path) -> int:
    log("lint", "static checks of .rsm (rsmc DSL + known rsmc traps)")
    rc = run(srmod_cmd(args, "lint", str(mod_dir)),
             cwd=Path(args.srmod_root), env_extra=srmod_env(args))
    if rc == 0:
        log("lint", "clean")
    else:
        log("lint", f"srmod lint reported findings (rc={rc})")
    return rc


def stage_build(args, mod_dir: Path) -> int:
    build_dir = mod_dir / "build"
    if build_dir.exists() and args.clean:
        log("build", f"removing {build_dir}")
        shutil.rmtree(build_dir, ignore_errors=True)
    log("build", "src/ -> build/  (rsmc + DAT/lang/CacheData)")
    cmd = srmod_cmd(args, "build", str(mod_dir))
    if args.rsmc:
        cmd += ["--rsmc", str(Path(args.rsmc).resolve())]
    rc = run(cmd, cwd=Path(args.srmod_root), env_extra=srmod_env(args))
    if rc == 0:
        scr = sorted((build_dir / "DATA" / "Script").glob("*.scr")) if build_dir.is_dir() else []
        for s in scr:
            log("build", f"{s}  ({s.stat().st_size} bytes)")
        log("build", f"ready: {build_dir}")
    return rc


def install_rel(mod_dir: Path) -> str:
    import json

    proj = json.loads((mod_dir / "srmod.json").read_text(encoding="utf-8-sig"))
    return proj.get("install") or f"Mods/{proj.get('name', 'Mod')}"


def stage_deploy(args, mod_dir: Path) -> int:
    build_dir = mod_dir / "build"
    if not build_dir.is_dir():
        die(f"{build_dir}: nothing to deploy — run the build stage first.", 2)
    rel = install_rel(mod_dir)
    dest = Path(args.game).joinpath(*rel.replace("\\", "/").split("/"))

    if args.deploy_mode == "junction":
        log("deploy", f"junction {dest} -> {build_dir}")
        cmd = srmod_cmd(args, "deploy", str(mod_dir), "--game", str(Path(args.game).resolve()))
        return run(cmd, cwd=Path(args.srmod_root), env_extra=srmod_env(args))

    log("deploy", f"copy build/ -> {dest}")
    if dest.exists():
        if not args.overwrite:
            die(f"{dest} already exists. Re-run with --overwrite to replace it.", 1)
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(build_dir, dest)
    log("deploy", f"copied {sum(1 for _ in dest.rglob('*') if _.is_file())} files")
    return 0


def stage_audit(args, mod_dir: Path) -> int:
    build_dir = mod_dir / "build"
    if not build_dir.is_dir():
        die(f"{build_dir}: nothing to audit — run the build stage first.", 2)
    mk = Path(args.modkit_root)
    log("audit", "SRHD-XenoModKit: audit --profile dev")
    cmd = [args.python, "-B", "srhd.py", "audit", str(build_dir), "--profile", "dev"]
    if args.audit_json:
        cmd.append("--json")
    rc = run(cmd, cwd=mk)
    log("audit", "see docs/TOOLS.md for the extra ModKit checks you can run")
    return rc


# --------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="compile.py",
        description="Build a Space Rangers HD mod from this repo (headless).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--mod-dir", default=os.environ.get("SR2_MOD_DIR") or str(DEFAULT_MOD_DIR),
                   help="mod project folder (the one holding srmod.json)")
    p.add_argument("--srmod-root", default=os.environ.get("SR2_SRMOD_ROOT"),
                   help="sr-modkit clone root (folder containing srmod/)")
    p.add_argument("--python", default=os.environ.get("PYTHON") or sys.executable,
                   help="python interpreter used to run sr-modkit / ModKit")
    p.add_argument("--rsmc", default=os.environ.get("SR2_RSMC"),
                   help="path to rsmc.exe (needed by the build stage, Windows only)")
    p.add_argument("--game", default=os.environ.get("SR2_GAME"),
                   help="game install root (the folder containing Mods/)")
    p.add_argument("--modkit-root", default=os.environ.get("SR2_MODKIT_ROOT"),
                   help="SRHD-XenoModKit clone root (folder containing srhd.py)")
    p.add_argument("--stage", default="all", choices=("lint", "build", "deploy", "all"),
                   help="what to do")
    p.add_argument("--deploy-mode", default="junction", choices=("junction", "copy"),
                   help="junction = live link to build/ (no reinstall ever); copy = real files")
    p.add_argument("--overwrite", action="store_true",
                   help="allow --deploy-mode copy to replace an existing folder")
    p.add_argument("--clean", action="store_true", help="delete build/ before building")
    p.add_argument("--fix-encodings", action="store_true",
                   help="convert src/**/*.txt to UTF-16LE+BOM and strip BOM from .rsm, then exit")
    p.add_argument("--audit", action="store_true", help="after build, run XenoModKit audit")
    p.add_argument("--audit-json", action="store_true", help="ask ModKit audit for --json")
    p.add_argument("--timeout", type=int, default=900, help="per-command timeout, seconds")
    p.add_argument("--pause", action="store_true", help="wait for Enter before exiting")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    mod_dir = Path(args.mod_dir).resolve()

    print("=" * 72)
    print(f" SR2HD mod build   stage={args.stage}   mod={mod_dir.name}")
    print("=" * 72)

    if not mod_dir.is_dir():
        die(f"--mod-dir {mod_dir}: folder not found.", 1)

    if args.fix_encodings:
        n = fix_encodings(mod_dir)
        log("fix", f"{n} file(s) converted" if n else "nothing to convert")
        return 0

    problems = preflight(args, mod_dir)
    if problems:
        print()
        for pr in problems:
            print(f"[preflight ] {pr}", file=sys.stderr)
        print()
        hint = ("Some problems are fixable: rerun with --fix-encodings."
                if any("UTF-16LE" in p for p in problems) else "")
        die(f"{len(problems)} preflight problem(s). {hint}".strip(), 1)

    log("preflight", f"ok: srmod={args.srmod_root}" + (f"  rsmc={args.rsmc}" if args.rsmc else ""))

    if args.stage in ("lint", "all"):
        rc = stage_lint(args, mod_dir)
        if rc != 0:
            die("lint failed — fix the findings above, then rerun.", 2)
        if args.stage == "lint":
            return finish(args, 0)

    if args.stage in ("build", "deploy", "all"):
        rc = stage_build(args, mod_dir)
        if rc != 0:
            die("build failed — read the sr-modkit message above.", 2)
        if args.stage == "build":
            if args.audit:
                rc = stage_audit(args, mod_dir)
                if rc != 0:
                    die("audit failed (see docs/VERIFICATION.md)", 2)
            return finish(args, 0)

    if args.stage in ("deploy", "all"):
        rc = stage_deploy(args, mod_dir)
        if rc != 0:
            die("deploy failed.", 2)

    if args.audit:
        rc = stage_audit(args, mod_dir)
        if rc != 0:
            die("audit failed (see docs/VERIFICATION.md)", 2)

    return finish(args, 0)


def finish(args, code: int) -> int:
    if code == 0 and args.stage in ("build", "deploy", "all"):
        print()
        print("NEXT: start the game -> Mods -> enable the mod -> start a NEW game.")
        print("      Docking at a Science base should now show the new menu item.")
    elif code == 0:
        print("\n(sources check out; nothing was compiled)")
    if args.pause:
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        die(str(e), 1)
    except KeyboardInterrupt:
        die("interrupted", 130)
