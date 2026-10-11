# sr2-mod

Mods for **Space Rangers HD: A War Apart** (Космические рейнджеры HD), built
headlessly from text sources.

Contents:

| Path | What |
|---|---|
| `mods/SbHello/` | the mod: adds a menu item and a short replica to the **Science base** ("Научная база") dialog. Works in game. |
| `mods/FastGalaxy/` | optional config-only mod (no script): 45 stars instead of 73, so new-game generation — including «Проходит время» — is markedly faster |
| `tools/compile.py` | build driver — every path is a CLI argument |
| `tools/run_compile.py` | double-click front-end — the same values as variables at the top; `MOD_DIRS` lists the mods to build |
| `tools/run_compile.cmd` | double-click launcher that also keeps the window open |
| `docs/FAST_ITERATION.md` | **iterating without a new game**, and what is/is not moddable about the «Проходит время» phase — with engine citations |
| `docs/TOOLS.md` | what to install and where to get it |
| `docs/RSM_SYNTAX.md` | verified `.rsm` reference |
| `docs/STATIONS.md` | the full station type table (`SB` = Science base, `CB` = Dominion) straight from the engine |
| `docs/WORKFLOW.md` | edit → lint → build → deploy → test, plus troubleshooting |
| `docs/VERIFICATION.md` | what is proved by tooling vs what still needs the game |
| `investigation.txt` | the feasibility investigation + addenda |

## Quick start (Windows)

1. Install: Python 3.9+, `sr-modkit` clone, `rsmc.exe` — see `docs/TOOLS.md`.
2. Open `tools/run_compile.py` and set the paths in the SETTINGS block:

   ```python
   SRMOD_ROOT = r"C:\tools\sr-modkit"
   RSMC       = r"C:\tools\rsmc\rsmc.exe"
   GAME_DIR   = r"C:\Games\Space Rangers HD A War Apart"
   STAGE      = "all"
   MOD_DIRS   = [r"", r"mods\FastGalaxy"]   # "" = the default mod (SbHello)
   ```

3. Double-click `tools/run_compile.cmd` — it builds and deploys both mods.
4. In the game: **Mods** → enable what you want → **«Применить»** → **one** new
   game. You start docked at the ranger centre and the science base is in the
   same system, so the dialog is one undock/dock away.
5. Every change after that: rebuild → **load the same save**. No new game, no
   reinstall. Add «Применить» only when you touched `Main.txt`, `Lang.txt` or
   the mod list — `docs/FAST_ITERATION.md` has the exact table and the reason.

The build itself is one command (`srmod build`); everything else is checks and
convenience. Sources live in `mods/<Mod>/src/`, output in `mods/<Mod>/build/`
(generated, not committed).

## Why text sources

`.rsm` is a small text DSL compiled by `rsmc` straight into the game's `.scr`.
No node-graph clicking, so mods are reviewable diffs in git and the whole
pipeline runs without a GUI.

## Status

* **SbHello works in game** (player-tested at the Science base). It now starts
  itself from `CFG/Main.txt` (`BV/OnStart` on a new game, guarded `BV/OnLoad` on
  every save load), which is what makes a rebuild visible without a new game.
  `vProbe = 1` is still on for diagnostics; set it to `0` before release.
* **FastGalaxy is headless-verified only** — it builds, and its `Lang.dat`
  overrides exactly one value (`GalaxyCountStars` 73 → 45) while its neighbours
  survive the merge. In-game generation time and galaxy sanity are pending
  (`docs/VERIFICATION.md`).
* The 300 warmup turns of «Проходит время» are a compile-time constant no config
  key and no script function can reach, so the phase can be made *cheaper*, not
  *skipped* — `docs/FAST_ITERATION.md` §2 lists every door that was checked.
* The current source revision has not been through `rsmc.exe` on Windows yet.
