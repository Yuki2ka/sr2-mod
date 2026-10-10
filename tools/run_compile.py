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
import sys
from pathlib import Path

# ============================== SETTINGS ====================================
# Paths are Windows paths. Use a raw string (r"...") so backslashes stay put.

# Which mod to build. Leave empty for mods/SbHello next to this repo.
MOD_DIR = r""

# sr-modkit clone: the folder that contains srmod\ (and its own README.md).
SRMOD_ROOT = r"C:\tools\sr-modkit"

# rsmc.exe — the only foreign binary needed. Download: github.com/indiemagpie
# -> RScript releases -> rsmc.zip, unpack anywhere, point here.
RSMC = r"C:\tools\rsmc\rsmc.exe"

# Game install root: the folder that contains Mods\ and the game exe.
GAME_DIR = r"C:\Games\Space Rangers HD A War Apart"

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


def main() -> int:
    compile_mod = load_compile()

    argv = ["--stage", STAGE, "--deploy-mode", DEPLOY_MODE]
    if MOD_DIR:
        argv += ["--mod-dir", MOD_DIR]
    if SRMOD_ROOT:
        argv += ["--srmod-root", SRMOD_ROOT]
    if PYTHON_EXE:
        argv += ["--python", PYTHON_EXE]
    if RSMC:
        argv += ["--rsmc", RSMC]
    if GAME_DIR:
        argv += ["--game", GAME_DIR]
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
    if PAUSE_AT_END:
        argv += ["--pause"]

    return compile_mod.main(argv)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
