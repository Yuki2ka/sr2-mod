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
  SR2_DECOMPILER   path to a rson-decompiler clone (only for mods with media)
  SR2_MOD_DIR      the mod to build (default mods/SbHello)
  PYTHON           python interpreter used to run sr-modkit / ModKit

rsmc.exe and rson-decompiler are auto-detected next to the sr-modkit clone
(C:\tools\rsmc\rsmc.exe, C:\tools\rson-decompiler\...) when not given explicitly.
A mod without images or packages needs no real decompiler: `srmod build` only
asks for one unconditionally (run_media opens the tree after the check), so
tools/stubs/noop-decompiler is passed instead and the build goes through.

Exit codes: 0 ok | 1 setup/operational error | 2 lint findings or build gate
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MOD_DIR = REPO_ROOT / "mods" / "SbHello"
TOOLS_DIR = Path(__file__).resolve().parent

# Stand-in that satisfies `srmod build`'s "give me rson-decompiler" check for a
# mod with no media. Its run.py fails loudly if it is ever actually called.
STUB_DECOMPILER = TOOLS_DIR / "stubs" / "noop-decompiler"

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


# ------------------------------------------------------------- tool discovery
def srmod_siblings(srmod_root) -> list[Path]:
    """Folders searched next to the sr-modkit clone (autodetect, like srmod)."""
    if not srmod_root:
        return []
    root = Path(srmod_root).resolve()
    return [root.parent / "rsmc", root.parent / "rson-decompiler",
            root.parent / "rson_decompiler"]


def find_rsmc(args) -> tuple[Path | None, str]:
    """Locate rsmc.exe: --rsmc > env > next to the sr-modkit clone."""
    if args.rsmc and Path(args.rsmc).is_file():
        return Path(args.rsmc).resolve(), "--rsmc"
    for var in ("SR2_RSMC", "SRMOD_RSMC"):
        env = os.environ.get(var)
        if env and Path(env).is_file():
            return Path(env).resolve(), f"${var}"
    for base in srmod_siblings(args.srmod_root):
        cand = base / "rsmc.exe"
        if cand.is_file():
            return cand.resolve(), f"next to {base.parent.name}"
    bare = Path(args.srmod_root).resolve().parent / "rsmc.exe" if args.srmod_root else None
    if bare and bare.is_file():
        return bare.resolve(), f"in {bare.parent}"
    return None, "rsmc.exe not found"


def find_decompiler(args) -> tuple[Path | None, str]:
    """Locate a real rson-decompiler clone (its folder holds run.py)."""
    if args.decompiler:
        p = Path(args.decompiler)
        if (p / "run.py").is_file():
            return p.resolve(), "--decompiler"
        return None, f"--decompiler {p}: no run.py inside — wrong folder"
    for var in ("SR2_DECOMPILER", "SRMOD_DECOMPILER"):
        env = os.environ.get(var)
        if env and (Path(env) / "run.py").is_file():
            return Path(env).resolve(), f"${var}"
    srmod_name = Path(args.srmod_root).resolve().name if args.srmod_root else "sr-modkit"
    for base in srmod_siblings(args.srmod_root):
        if (base / "run.py").is_file():
            return base.resolve(), f"next to {srmod_name}"
    return None, "rson-decompiler not found (only needed for mods with media)"


def media_needs(mod_dir: Path) -> list[str]:
    """src/ entries that require the real srgi/srpkg encoders."""
    src = mod_dir / "src"
    needs: list[str] = []
    if not src.is_dir():
        return needs
    if any(src.rglob("*.png")):
        needs.append("images (src/**/*.png -> .gi)")
    if any(src.rglob("*.gai.src")) or any(src.rglob("*.hai.src")):
        needs.append("atlases (*.gai.src/, *.hai.src/)")
    if any(src.rglob("*.pkg.src")):
        needs.append("packages (*.pkg.src/)")
    proj = read_json(mod_dir / "srmod.json")
    pkgs = (proj.get("packages") or []) if proj else []
    if pkgs:
        needs.append(f'"packages" in srmod.json: {", ".join(pkgs)}')
    return needs


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------- preflight
def load_srblockpar(args):
    """sr-modkit's own DAT reader, used for the headless Main.txt replay."""
    if not args.srmod_root:
        return None
    vendor = Path(args.srmod_root).resolve() / "srmod" / "vendor"
    if not (vendor / "srblockpar" / "__init__.py").is_file():
        return None
    if str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    try:
        import srblockpar  # noqa: PLC0415  (vendored, path known only at runtime)
    except ImportError as e:
        log("preflight", f"srblockpar unavailable ({e}) — skipping the Main.txt replay")
        return None
    return srblockpar


def _bp_kinds(srblockpar):
    bp = getattr(srblockpar, "blockpar", None)
    if bp is None:
        import importlib
        bp = importlib.import_module("srblockpar.blockpar")
    return bp


def _concatenate_values(block, bp) -> str:
    """Port of TBlockParEC.ConcatenateValues: the text the engine executes."""
    out = []
    for e in block.entries:
        if e.kind == bp.KIND_TEXT:
            continue
        if e.kind == bp.KIND_BLOCK:
            out.append("{" + _concatenate_values(e.block, bp) + "}")
        else:
            out.append(e.value or "")
    return "".join(out)


def _child_block(block, name, bp):
    for e in block.entries:
        if e.kind == bp.KIND_BLOCK and e.name == name:
            return e.block
    return None


def _script_run_names(text: str) -> list[str]:
    """The script names passed to ScriptRun(...) in a chunk of engine code.

    Not a one-regex job: the call contains nested parens
    (ScriptRun(ShipStar(Player()), GetShipPlanet(Player()), 'Name')), so the
    arguments are cut at the terminating ';' and the name is the last quoted
    literal in them — which is where SRHD puts it.
    """
    names = []
    for call in re.findall(r"ScriptRun\s*\(([^;]*)", text):
        quoted = re.findall(r"'([^']+)'", call)
        if quoted:
            names.append(quoted[-1])
    return names


def _comment_in_value(raw_text: str) -> list[str]:
    """Param lines whose value carries a '//' comment.

    Both the game's DAT parser and srblockpar cut the value at '//', so by the
    time the tree is parsed the comment — and anything of the statement that
    followed it — is already gone. That is why this is scanned on the raw text:
    a truncated line of engine code is silent and only shows up as a script
    that never starts.
    """
    found = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        if "=" not in stripped:
            continue
        value = stripped.split("=", 1)[1]
        if "//" in value:
            found.append(stripped.split("=", 1)[0].strip())
    return found


def check_main_dat(mod_dir: Path, args) -> list[str]:
    """Replay src/CFG/Main.txt the way the engine reads it. Returns problems.

    The game merges the mod's Main.dat into its own (LoadDatConfigAndModOverrides
    -> MergeFrom) and then executes two blocks from it as script code:
    BV/OnStart on a new game (TGalaxy.RunConfigOnStartHandlers, generation stage
    16) and BV/OnLoad on every save load (RunConfigOnLoadHandlers). Those are the
    hooks that let a mod start — and restart — without a new game, and they are
    also the easiest thing to get silently wrong, so the traps are checked here
    instead of in a playthrough: see docs/FAST_ITERATION.md.
    """
    main_txt = mod_dir / "src" / "CFG" / "Main.txt"
    if not main_txt.is_file():
        return []                      # config-only mod (mods/FastGalaxy)
    srblockpar = load_srblockpar(args)
    if srblockpar is None:
        return []
    bp = _bp_kinds(srblockpar)

    try:
        tree = srblockpar.read_text(main_txt)
    except Exception as e:             # BlockParError and friends
        return [f"{main_txt.name}: the DAT parser cannot read it ({e})."]

    problems: list[str] = []
    for param in _comment_in_value(main_txt.read_text(encoding="utf-16", errors="replace")):
        problems.append(
            f"{main_txt.name}: the value of '{param}' carries a '//' comment — the DAT "
            "parser cuts the value at '//', so the engine runs a truncated statement "
            "and reports nothing. Put comments on their own lines.")

    registered = set()
    data = _child_block(tree, "Data", bp)
    script = _child_block(data, "Script", bp) if data is not None else None
    if script is not None:
        registered = {e.name for e in script.entries if e.kind == bp.KIND_STRING}

    bv = _child_block(tree, "BV", bp)
    if bv is None:
        if registered:
            log("preflight", f"{main_txt.name}: no BV block — the script starts only "
                             "from its own onGlobal/GRun (works, but a save cannot "
                             "re-attach it; see docs/FAST_ITERATION.md)")
        return []

    for e in bv.entries:
        if e.kind == bp.KIND_STRING and e.name == "BV":
            problems.append(f"{main_txt.name}: a param named BV inside the BV block "
                            "overwrites the game version in the merged Main.dat and "
                            "the exe then reports a build version mismatch. Remove it.")

    for hook, guarded in (("OnStart", False), ("OnLoad", True)):
        node = _child_block(bv, hook, bp)
        if node is None:
            if hook == "OnLoad" and registered:
                log("preflight", f"{main_txt.name}: no BV/OnLoad — an existing save "
                                 "will not re-attach this script after a rebuild")
            continue
        handlers = [e for e in node.entries if e.kind == bp.KIND_BLOCK]
        if not handlers:
            problems.append(f"{main_txt.name}: BV/{hook} has no handler block; the "
                            f"engine runs each BLOCK inside {hook} as one script.")
        for h in handlers:
            text = _concatenate_values(h.block, bp)
            if not text.strip():
                problems.append(f"{main_txt.name}: BV/{hook}/{h.name} is empty — the "
                                "engine would execute an empty script.")
                continue
            log("preflight", f"{main_txt.name}: BV/{hook}/{h.name} executes: {text}")
            for called in _script_run_names(text):
                if called not in registered:
                    problems.append(
                        f"{main_txt.name}: BV/{hook} runs ScriptRun('{called}') but "
                        f"Data/Script registers {sorted(registered) or 'nothing'}. "
                        "ScriptRun takes the script NAME from Data/Script, not the "
                        "'Script.<Name>' path.")
            if guarded and "ScriptRun(" in text and "IsScriptActive(" not in text:
                problems.append(
                    f"{main_txt.name}: BV/{hook}/{h.name} calls ScriptRun without an "
                    "IsScriptActive guard — SF_ScriptRun matches the name against "
                    "ScriptFileName ('Script.<Name>'), never finds it, and starts a "
                    "second instance of the same script on every load.")
    return problems


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

    # 4b. CFG/Main.txt as the engine will read it: BV/OnStart + BV/OnLoad
    problems.extend(check_main_dat(mod_dir, args))

    # 5. build stage needs rsmc.exe, and rsmc.exe is Windows-only.
    #    A config-only mod has no .rsm to compile, so it needs neither — it can
    #    be built and deployed on any OS (that is what mods/FastGalaxy is).
    if args.stage in ("build", "deploy", "all") and is_config_only(mod_dir):
        log("preflight", f"{mod_dir.name}: no script (engine=none) — rsmc.exe not needed")
    elif args.stage in ("build", "deploy", "all"):
        if args.rsmc and not Path(args.rsmc).is_file():
            problems.append(f"--rsmc {args.rsmc}: file not found.")
        elif not args.rsmc:
            problems.append(
                "rsmc.exe path unknown. Pass --rsmc <path> or set SR2_RSMC "
                "(download: github.com/indiemagpie, RScript releases, rsmc.zip)."
            )
        elif os.name != "nt":
            problems.append(
                f"rsmc.exe is a Windows binary and this machine is {sys.platform}. "
                "Run the build/deploy stages on Windows (or use --stage lint here)."
            )

        # 5b. media needs the real rson-decompiler; a media-less mod does not
        #     (see STUB_DECOMPILER), so only the former is a preflight error.
        needs = media_needs(mod_dir)
        if needs:
            decomp, why = find_decompiler(args)
            if not decomp:
                problems.append(
                    f"this mod has media/packages: {'; '.join(needs)}. "
                    f"{why}. Clone it (github.com/ArtYudin89/rson-decompiler) and pass "
                    "--decompiler <folder> — see docs/TOOLS.md."
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


def is_config_only(mod_dir: Path) -> bool:
    """True when srmod.json declares no script at all (`mods/FastGalaxy`).

    `srmod build` supports that shape (`"script": {"engine": "none"}`,
    srmod/build.py:737): everything it produces — Main.dat, Lang.dat,
    CacheData.dat, ModuleInfo.txt — comes from sr-modkit's own Python, so
    rsmc.exe, the only Windows-only tool in the chain, is not needed.
    """
    try:
        proj = json.loads((mod_dir / "srmod.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False                     # unreadable config: not our call here
    script_cfg = proj.get("script") or {}
    return not script_cfg.get("entry") and script_cfg.get("engine") in (None, "none")


def check_script_name(mod_dir: Path) -> tuple[bool, str]:
    """scriptName("X") in main.rsm must equal srmod.json "name".

    A config-only mod (`script.engine == "none"`, or no `script` at all, like
    mods/FastGalaxy which ships a Lang.dat and nothing else) has no entry point
    to check; sr-modkit's own build accepts that shape.
    """
    import re

    cfg = mod_dir / "srmod.json"
    entry_path = None
    try:
        proj = json.loads(cfg.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        return False, f"{cfg}: cannot read ({e})"
    name = proj.get("name")
    script_cfg = proj.get("script") or {}
    entry = script_cfg.get("entry")
    if entry:
        entry_path = mod_dir / entry
    if not name:
        return False, f"{cfg}: no \"name\"."
    if entry_path is None and is_config_only(mod_dir):
        return True, f"config-only mod \"{name}\" (no script): name check skipped"
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
    decomp, why = find_decompiler(args)
    if decomp:
        cmd += ["--decompiler", str(decomp)]
        log("build", f"decompiler: {decomp} ({why})")
    elif not media_needs(mod_dir):
        # srmod build asks for rson-decompiler before it looks at the tree; a
        # mod with no images/packages never calls it, so the no-op stands in.
        cmd += ["--decompiler", str(STUB_DECOMPILER)]
        log("build", f"decompiler: {STUB_DECOMPILER} (no-op — no media in this mod)")
    else:
        die("this mod has media/packages and no rson-decompiler was found: "
            "git clone https://github.com/ArtYudin89/rson-decompiler <folder> "
            "and rerun with --decompiler <folder>.", 1)
    rc = run(cmd, cwd=Path(args.srmod_root), env_extra=srmod_env(args))
    if rc == 0:
        scr = sorted((build_dir / "DATA" / "Script").glob("*.scr")) if build_dir.is_dir() else []
        for s in scr:
            log("build", f"{s}  ({s.stat().st_size} bytes)")
        log("build", f"ready: {build_dir}")
    return rc


def install_rel(mod_dir: Path) -> str:
    proj = read_json(mod_dir / "srmod.json") or {}
    return proj.get("install") or f"Mods/{proj.get('name', 'Mod')}"


def clear_deploy_link(dest: Path) -> None:
    """Make room at dest so a fresh junction can be created there.

    `srmod deploy` only knows how to *create* the link, so a second run — or a
    leftover from an earlier one — dies with WinError 183. os.rmdir removes the
    reparse point itself and never follows it into the target; shutil.rmtree
    would, and would empty build/ through the link. A real, non-empty folder
    is not ours to delete: say so and stop.
    """
    if not os.path.lexists(dest):
        return
    try:
        os.rmdir(dest)
        log("deploy", f"cleared {dest} for the new junction")
        return
    except NotADirectoryError:
        dest.unlink()
        log("deploy", f"removed the file {dest}")
        return
    except OSError as e:
        die(f"cannot clear {dest} for the new junction: {e}. If a real folder "
            f"with files is sitting there, move it away and rerun, or deploy "
            f"with --deploy-mode copy --overwrite.", 2)


def stage_deploy(args, mod_dir: Path) -> int:
    build_dir = mod_dir / "build"
    if not build_dir.is_dir():
        die(f"{build_dir}: nothing to deploy — run the build stage first.", 2)
    rel = install_rel(mod_dir)
    dest = Path(args.game).joinpath(*rel.replace("\\", "/").split("/"))

    if args.deploy_mode == "junction":
        clear_deploy_link(dest)
        log("deploy", f"junction {dest} -> {build_dir}")
        cmd = srmod_cmd(args, "deploy", str(mod_dir), "--game", str(Path(args.game).resolve()))
        rc = run(cmd, cwd=Path(args.srmod_root), env_extra=srmod_env(args))
        if rc == 0 and not (dest / "ModuleInfo.txt").is_file():
            # A link can be created "successfully" and still point nowhere
            # (that is how a dangling junction gets missed: exit 0, no mod).
            die(f"deploy reported success, but {dest / 'ModuleInfo.txt'} is not "
                f"readable: the link is dangling. Check that {build_dir} exists.", 2)
        return rc

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
    p.add_argument("--decompiler", default=os.environ.get("SR2_DECOMPILER"),
                   help="rson-decompiler clone root (folder containing run.py); "
                        "only needed by mods that ship images (.gi) or packages (.pkg)")
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

    # rsmc.exe: keep --rsmc when it points at a real file, otherwise hunt for
    # it next to the sr-modkit clone (that is where srmod autodetect looks too).
    if args.stage in ("build", "deploy", "all") and not is_config_only(mod_dir):
        rsmc, why = find_rsmc(args)
        if rsmc is not None:
            if args.rsmc != str(rsmc):
                log("preflight", f"rsmc: {rsmc} ({why})")
            args.rsmc = str(rsmc)

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
            return finish(args, 0, mod_dir)

    if args.stage in ("build", "deploy", "all"):
        rc = stage_build(args, mod_dir)
        if rc != 0:
            die("build failed — read the sr-modkit message above.", 2)
        if args.stage == "build":
            if args.audit:
                rc = stage_audit(args, mod_dir)
                if rc != 0:
                    die("audit failed (see docs/VERIFICATION.md)", 2)
            return finish(args, 0, mod_dir)

    if args.stage in ("deploy", "all"):
        rc = stage_deploy(args, mod_dir)
        if rc != 0:
            die("deploy failed.", 2)

    if args.audit:
        rc = stage_audit(args, mod_dir)
        if rc != 0:
            die("audit failed (see docs/VERIFICATION.md)", 2)

    return finish(args, 0, mod_dir)


def finish(args, code: int, mod_dir: Path | None = None) -> int:
    if code == 0 and args.stage in ("build", "deploy", "all"):
        print()
        if mod_dir is not None and is_config_only(mod_dir):
            print("NEXT: start the game -> Mods -> enable the mod -> Apply -> a NEW game.")
            print("      This mod has no script: it only overrides config values, and the")
            print("      galaxy is generated once and then lives in the save, so a config")
            print("      mod like this one affects NEW games only. A mod with a script is")
            print("      the other way round — rebuild and just load the existing save")
            print("      (docs/FAST_ITERATION.md).")
        else:
            print("NEXT: start the game -> Mods -> enable the mod.")
            print("      A NEW game is needed only once per campaign: after that, edit")
            print("      the sources, rerun this script and just LOAD THE SAVE — the")
            print("      engine re-reads the .scr on load and BV/OnLoad re-attaches the")
            print("      script (docs/FAST_ITERATION.md).")
            print("      With vProbe enabled, RC diagnostics are expected; a Science")
            print("      base is generated in the starting system, so the research item")
            print("      can be checked without flying anywhere.")
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
