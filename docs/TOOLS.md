# Tools

Everything you need to build the mods in this repo. Only **one** part is
Windows-only (`rsmc.exe`); everything else is pure Python and runs headless.

## The pipeline in one picture

```
src/**/*.rsm  ──rsmc.exe──►  build/DATA/Script/<Name>.scr      (script)
                                   │
                                   └──►  Script/<Name>/<n>=…  (dialog text table)
src/CFG/Rus/Lang.txt + that table ─►  build/CFG/Rus/Lang.dat   (own DAT writer)
src/CFG/Main.txt               ──►  build/CFG/Main.dat         (script registration)
(install path)                 ──►  build/CFG/CacheData.dat    (where the mod lives)
```

`srmod build` does all of it, in this order, and stops on the first gate.

## Inventory

| Tool | What it is | Needed for | Windows only | Link |
|---|---|---|---|---|
| **sr-modkit** (`srmod`) | pure-Python build tool: scaffold, lint, build, deploy, decompile | **everything** | no | https://github.com/ArtYudin89/sr-modkit |
| **rsmc.exe** | console compiler `.rsm -> .scr`, part of RScript releases | `build` stage — but **not** a config-only mod (`"script": {"engine": "none"}`, e.g. `mods/FastGalaxy`): it has no `.rsm`, so it builds and deploys on any OS | **yes** | https://github.com/indiemagpie/RScript (releases → `rsmc.zip`) |
| **Python 3.9+** | runs `srmod` and the scripts in `tools/` | everything | no | https://www.python.org/downloads/windows/ |
| **SRHD-XenoModKit** | optional second-opinion auditor (DAT/SCR/RSON, runtime lint, releases) | `--audit` | no (Windows-oriented) | https://github.com/Xenomorphchyma/SRHD-XenoModKit |
| RScript (GUI) | node editor; only to *decompile* somebody else's `.scr` into `.rson` | `srmod open` / `srmod import` | yes | https://github.com/indiemagpie/RScript |
| rson-decompiler | `.png -> .gi`, `.pkg` packing | media/packages only (unused by this mod) | no | https://github.com/ArtYudin89/rson-decompiler |

**This mod has no media**, so `rsmc.exe` is the only foreign binary you need.

One trap worth knowing: `srmod build` asks for the `decompiler` tool *before* it
looks at the source tree, so even a mod without images fails with
`не найден decompiler (rson-decompiler)`. `tools/compile.py` therefore passes
`tools/stubs/noop-decompiler` in that case — a `run.py` that is never executed
(and refuses loudly if it ever is). A mod that *does* ship `.png`, `*.gai.src/`
or `*.pkg.src/` needs the real clone; pass it with `--decompiler <folder>`.

## Windows install (once)

1. Python 3.9+ — tick **"Add Python to PATH"** during install.
2. Unpack `rsmc.zip` anywhere, e.g. `C:\tools\rsmc\rsmc.exe`. Leaving `RSMC`
   empty works too — `compile.py` then looks for `rsmc.exe` next to the
   sr-modkit clone, exactly where `srmod` autodetects it.
3. Get sr-modkit:

   ```bat
   git clone https://github.com/ArtYudin89/sr-modkit.git C:\tools\sr-modkit
   ```

   (or GitHub → Code → Download ZIP and unpack; no `pip install` needed — the
   scripts in `tools/` run it as `python -m srmod` with `PYTHONPATH` set.)
4. Put the two paths into the SETTINGS block of `tools/run_compile.py`:

   ```python
   SRMOD_ROOT = r"C:\tools\sr-modkit"
   RSMC       = r"C:\tools\rsmc\rsmc.exe"
   GAME_DIR   = r"C:\Games\Space Rangers HD A War Apart"
   ```

5. Check the machine without touching the mod:

   ```bat
   python tools\compile.py --stage lint --srmod-root C:\tools\sr-modkit
   ```

Optional, any time: `python -m srmod doctor` prints which tools it found and
runs each of them once to prove it answers.

## Reference material worth keeping open

| What | Where |
|---|---|
| `.rsm` grammar, straight out of `rsmc.exe` (17 declarations, fields, enums) | `data/rsm-dsl.json` in sr-modkit |
| 977 game functions with descriptions and arity | `data/lexicon.json` in sr-modkit |
| Official `.rsm` example mod (pirate-base dialog injection) | https://github.com/indiemagpie/RScript/tree/main/Example |
| VS Code highlighting + go-to-definition for `.rsm` | https://github.com/indiemagpie/RScript/tree/main/rsmc.rsm-language-0.1.0 |
| sr-modkit VS Code extension (snippets, field hints, lint on save) | `extension/` in sr-modkit |
| Build pipeline internals and the traps it works around | `docs/STAGE0.md` in sr-modkit |
| XenoModKit command reference | `.agents/skills/srhd-modkit/references/commands.md` |
| XenoModKit scripting guide (RU) | `SCRIPTING_GUIDE_RU.md` in SRHD-XenoModKit |
