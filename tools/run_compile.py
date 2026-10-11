#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_compile.py — double-click front-end for compile.py.

EDIT THE SETTINGS BLOCK BELOW ONCE, then just double-click this file
(or run_compile.cmd). Every parameter is a plain variable: no command line,
no remembering flags. `compile.py` in the same folder is the version that
takes the very same values as arguments; this file only feeds it.

If a variable is left empty it is skipped, and compile.py falls back to its
own default / environment variable (see docs/WORKFLOW.md).
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

# ============================== SETTINGS ====================================
# Paths are Windows paths. Use a raw string (r"...") so backslashes stay put.

# Which mods to build, in order — each entry is a mod project folder (the one
# holding srmod.json). An empty entry means the repo default (mods/SbHello).
# Relative paths are resolved against the REPO ROOT, so they work no matter
# which folder this script was launched from. A plain string is accepted too.
#
#   mods/SbHello     the test mod: script + BV/OnStart + BV/OnLoad, so a
#                    rebuilt .scr is picked up by an existing save.
#   mods/FastGalaxy  config-only (no script): fewer stars, so a NEW game
#                    generates faster. Does not touch existing saves; comment
#                    the line out when you want a normal-size galaxy.
MOD_DIRS = [
    r"",                    # = mods/SbHello
    r"mods\FastGalaxy",
]

# sr-modkit clone: the folder that contains srmod\ (and its own README.md).
SRMOD_ROOT = r"C:\Games\sr-modkit"

# rsmc.exe — the only foreign binary this mod needs (see DECOMPILER below for
# the exception). Download: github.com/indiemagpie
# -> RScript releases -> rsmc.zip, unpack anywhere, point here.
# Left empty, compile.py looks for rsmc.exe next to the sr-modkit clone.
RSMC = r"C:\Games\sr-rsmc\rsmc.exe"

# Game install root: the folder that contains Mods\ and the game exe.
GAME_DIR = r"C:\Games\Space Rangers HD A War Apart"

# Optional: rson-decompiler clone (the folder that contains run.py). Only needed
# when the mod ships images (.png -> .gi), atlases (*.gai.src/) or packages
# (*.pkg.src/). SbHello has none, so leave this empty: compile.py then passes a
# no-op stub that satisfies srmod's unconditional tool check.
# Clone if you ever add media: git clone github.com/ArtYudin89/rson-decompiler
DECOMPILER = r""

# Optional: SRHD-XenoModKit clone (the folder that contains srhd.py).
# Used only when DO_AUDIT is True. Leave empty to skip the audit.
MODKIT_ROOT = r""

# Python interpreter. Empty = the python.exe that runs this file.
PYTHON_EXE = r""

# What to do:  "all"    = lint + build + deploy      (normal use)
#              "build"  = lint + build, no install
#              "lint"   = only check the sources (no rsmc needed, any OS)
#              "deploy" = install an existing build\
STAGE = "all"

# How the mod reaches the game:
#   "junction" = Mods\SbHello is a live link to build\ — rebuild and it is
#                already in the game, never reinstall again (recommended)
#   "copy"     = real files are copied into Mods\ (needs --overwrite to redo)
DEPLOY_MODE = "junction"
OVERWRITE_COPY = False

# Delete build\ before building (avoids stale leftovers).
CLEAN_BUILD = True

# Run the XenoModKit audit after the build (needs MODKIT_ROOT).
DO_AUDIT = False
AUDIT_JSON = False

# One-off repair: convert src\*.txt to UTF-16LE+BOM and strip BOM from .rsm,
# then exit without building. Set to True, run once, set back to False.
FIX_ENCODINGS = False

# Keep the console window open at the end so you can read the output.
PAUSE_AT_END = True
# ============================================================================


def load_compile():
    """Import compile.py by path (its name shadows nothing, but be explicit)."""
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("sr2_compile", here / "compile.py")
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {here / 'compile.py'}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def resolve_mod_dir(entry: str, repo_root: Path) -> str:
    """Absolute mod folder for compile.py; '' keeps compile.py's own default."""
    if not entry or not entry.strip():
        return ""
    # SETTINGS are written with Windows separators; keep them working when the
    # repo is checked out somewhere else (lint stage runs on any OS).
    if os.sep != "\\":
        entry = entry.replace("\\", "/")
    path = Path(entry)
    return str(path if path.is_absolute() else repo_root / path)


def main() -> int:
    compile_mod = load_compile()
    repo_root = Path(__file__).resolve().parent.parent

    entries = MOD_DIRS if isinstance(MOD_DIRS, (list, tuple)) else [MOD_DIRS]
    targets = [resolve_mod_dir(e, repo_root) for e in entries]

    worst = 0
    for index, target in enumerate(targets):
        argv = ["--stage", STAGE, "--deploy-mode", DEPLOY_MODE]
        if target:
            argv += ["--mod-dir", target]
        # Only the last mod keeps the window open; compile.py's own --pause
        # would otherwise stop after every single one.
        if PAUSE_AT_END and index == len(targets) - 1:
            argv += ["--pause"]
        if SRMOD_ROOT:
            argv += ["--srmod-root", SRMOD_ROOT]
        if PYTHON_EXE:
            argv += ["--python", PYTHON_EXE]
        if RSMC:
            argv += ["--rsmc", RSMC]
        if GAME_DIR:
            argv += ["--game", GAME_DIR]
        if DECOMPILER:
            argv += ["--decompiler", DECOMPILER]
        if MODKIT_ROOT:
            argv += ["--modkit-root", MODKIT_ROOT]
        if OVERWRITE_COPY:
            argv += ["--overwrite"]
        if CLEAN_BUILD:
            argv += ["--clean"]
        if DO_AUDIT:
            argv += ["--audit"]
        if AUDIT_JSON:
            argv += ["--audit-json"]
        if FIX_ENCODINGS:
            argv += ["--fix-encodings"]

        # compile.py signals a hard stop with die() -> sys.exit(); one broken
        # mod must not hide the state of the next one.
        try:
            rc = compile_mod.main(argv)
        except SystemExit as e:
            rc = int(e.code or 0)
        if rc:
            print(f"\n[run_compile] {Path(target).name if target else 'SbHello'}: "
                  f"exit code {rc}", file=sys.stderr)
            worst = worst or rc

    if len(targets) > 1:
        print(f"\n[run_compile] {len(targets)} mod(s) processed, "
              f"exit code {worst}")
    return worst


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
