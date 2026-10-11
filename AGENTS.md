# AGENTS.md

Working notes for agents (and humans) on **sr2-mod** — mods for
*Space Rangers HD: A War Apart* (Космические рейнджеры HD: Революция), built
headlessly from text sources.

Read this first. It points at the tools, the examples, the docs and the exact
workflow. Everything below is verified against tool sources; where it is not,
it says so.

---

## 1. Tools (install, links, what needs Windows)

| Tool | Role | Windows only | Link |
|---|---|---|---|
| **sr-modkit** (`srmod`) | primary toolkit: scaffold, lint, build, deploy, decompile foreign mods | no | https://github.com/ArtYudin89/sr-modkit |
| **rsmc.exe** | console compiler `.rsm -> .scr` (ships with RScript releases) | **yes** | https://github.com/indiemagpie/RScript (releases → `rsmc.zip`) |
| **SRHD-XenoModKit** | optional auditor: DAT/SCR/RSON checks, runtime lint, release packaging | no (Windows-oriented) | https://github.com/Xenomorphchyma/SRHD-XenoModKit |
| RScript (GUI) | only to decompile somebody else's `.scr` → `.rson` | yes | https://github.com/indiemagpie/RScript |
| rson-decompiler | `.png → .gi`, PKG packing (media; unused by this mod) | no | https://github.com/ArtYudin89/rson-decompiler |

**The mods in this repo need exactly one foreign binary: `rsmc.exe`.**
DAT files, the language table and `CacheData.dat` are produced by sr-modkit's
own Python code, so there is no BlockParEditor in the loop. Caveat worth
remembering: `srmod build` still asks for the `rson-decompiler` tool even when
the mod ships no media, so `tools/compile.py` passes
`tools/stubs/noop-decompiler` (a `run.py` that never gets called) — a mod with
images or packages needs the real clone, see `docs/TOOLS.md`.

Setup details, install commands and the reference data files each tool ships:
→ **[docs/TOOLS.md](docs/TOOLS.md)**

## 2. Examples

* **Official `.rsm` example mod** (pirate-base dialog injection, world graph,
  states, dialogs, item, Ether):
  https://github.com/indiemagpie/RScript/tree/main/Example
* **`srmod new <dir> --name <Name>`** — generates a *working*, commented mod
  (star, planet, player ship, NPC with a two-replica dialog, Lang, media).
  `--minimal` for a bare skeleton. Start from it rather than from nothing.
* **`mods/SbHello/`** — this repo's own example: injects a menu item into the
  Science base dialog. Shortest path through the whole pipeline.
* **Corpus-built function dictionary** — 977 game functions with descriptions,
  arity and real call samples: `data/lexicon.json` in sr-modkit
  (built from 330 decompiled mods, 183 657 observed calls).
* **Machine-readable `.rsm` grammar** — `data/rsm-dsl.json` in sr-modkit:
  all 17 declarations, their fields, required fields and enum values, pulled
  out of `rsmc.exe` itself.
* **XenoModKit's worked rules** — `SCRIPTING_GUIDE_RU.md`, `AUDIT_RU.md`,
  `PROJECTS_RU.md`, `.agents/skills/srhd-modkit/references/commands.md`.

## 3. Documentation

In this repo:

* [docs/TOOLS.md](docs/TOOLS.md) — install, tool inventory, upstream reference files
* [docs/RSM_SYNTAX.md](docs/RSM_SYNTAX.md) — verified `.rsm` reference (declarations, hooks, dialogs, injection, traps)
* [docs/STATIONS.md](docs/STATIONS.md) — station/base type tokens (`'SB'` = Science base) and the diagnostic probe
* [docs/WORKFLOW.md](docs/WORKFLOW.md) — edit → lint → build → deploy → test + troubleshooting table
* [docs/VERIFICATION.md](docs/VERIFICATION.md) — proved by tooling vs still needs the game
* [investigation.txt](investigation.txt) — feasibility investigation + resolved addendum

Upstream:

* sr-modkit `docs/STAGE0.md` — build internals and the rsmc traps they exist to catch
* SRHD-XenoModKit `SCRIPTING_GUIDE_RU.md` and `README_RU.md`
* RScript `README.md` — the `.rsm` format and `rsmc` CLI

## 4. Workflow

The user runs **Windows** and prefers scripts where every parameter is a
variable:

* `tools/compile.py` — all parameters as CLI args (`--mod-dir`, `--srmod-root`,
  `--rsmc`, `--game`, `--stage`, `--deploy-mode`, …). Also accepts env vars
  `SR2_SRMOD_ROOT`, `SR2_RSMC`, `SR2_GAME`, `SR2_MODKIT_ROOT`.
* `tools/run_compile.py` — **double-click** front-end: the same values as plain
  variables in a SETTINGS block at the top, no command line needed.
* `tools/run_compile.cmd` — double-click launcher, keeps the window open.

```bat
:: check sources only (no rsmc needed, runs on any OS)
python tools\compile.py --stage lint --srmod-root C:\tools\sr-modkit

:: or just double-click:
tools\run_compile.cmd
```

Pipeline stages: **lint** (static, rsmc DSL + traps) → **build**
(`src/` → `build/`, needs `rsmc.exe`) → **deploy** (junction from
`<game>\Mods\SbHello` to `build/` by default, so rebuilds are instant) →
optional **audit** (XenoModKit). Full detail and the troubleshooting table:
→ **[docs/WORKFLOW.md](docs/WORKFLOW.md)**

## 5. Layout and conventions

```
mods/<Mod>/
  srmod.json          name, install path ("Mods/<Mod>"), languages, script entry
  src/                ALL sources (this is what gets committed)
    ModuleInfo.txt    UTF-16LE — what the player sees in the mod list
    CFG/Main.txt      UTF-16LE — binds the script to the game
    CFG/<lang>/Lang.txt  UTF-16LE — own text keys; NEVER the Script/<Name> section
    DATA/Script/<Name>.src/*.rsm   UTF-8, no BOM
  build/              generated, git-ignored, game-ready
```

Non-negotiable conventions:

1. **`.rsm` = UTF-8 without BOM.** `srmod` rejects a BOM outright.
2. **`src/**/*.txt` = UTF-16LE with BOM.** UTF-8 with Cyrillic is silently
   mangled: no build error, garbage in game. `tools/compile.py --fix-encodings`
   repairs it.
3. **One name, three places**: `scriptName("X")` in `main.rsm`, `"name": "X"` in
   `srmod.json`, and `build/DATA/Script/X.scr`. Mismatch ⇒ rsmc quietly skips
   the language merge.
4. **Never hand-write `Script/<Name>` in `Lang.txt`** — the build creates it so
   rsmc can merge its `text:` table into it.
5. Dialog text goes in `text:` only — never `DText(CT(...))` inside `code:`.
6. Station/planet dialogs: `answerCommand: "restart"`, not `fastexit`.
7. Visible game text: plain Cyrillic, digits and `. , : ; - ! ?` — no em dashes
   or «quotes» (they are in CP1251 but may be missing from the game's fonts).
8. Install path lives in `srmod.json` → `install` and is baked into
   `CacheData.dat` at build time; change it there, then rebuild and redeploy.
9. A `ship({player: true, ...})` declaration is only a template-matching
   requirement; it does not keep an active script instance alive. If a script
   must survive turns (e.g. to inject station dialog options), bind the player
   into a group with `addPlayer: true` and `countMin/countMax: 1`. The engine
   deletes instances with zero bound ships after a turn, and `GCntRun` still
   remembers the initial start.

## 6. Verification policy

* Never claim runtime behaviour from a static check. Say what the tooling
  proved and what still needs the game — `docs/VERIFICATION.md` is the ledger;
  update it when something moves from "unverified" to "verified".
* `rsmc` warnings are errors: a warning means the text table was not merged and
  the mod ships mute.
* Prefer a new output file over overwriting an existing one.
* Do not edit files inside the game installation; deploy to a copy or use the
  junction. Do not hand-edit `Mods/ModCFG.txt`.
* Build artifacts (`build/`, `.srmod/`, `__pycache__/`) never get committed.

## 7. Current state

* `'SB'` (Science base) is confirmed from real mod code and `rsmc`'s constants —
  `docs/STATIONS.md` has the evidence; `vProbe = 1` remains enabled for testing.
* A one-time probe report exposed the empty-group lifecycle bug. `SbGroup` now
  binds the player as its sole member (`countMin/countMax = 1`, `addPlayer =
  true`); the reverse-engineered source shows this prevents the engine from
  deleting the script instance after a turn. See `docs/VERIFICATION.md`.
* Latest `.rsm` sources pass `srmod lint` with zero findings. The prior revision
  passed Windows build/deploy; the latest source change must be rebuilt on
  Windows and retested in a NEW game at RC and a Science base.
