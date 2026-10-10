# sr2-mod

Mods for **Space Rangers HD: A War Apart** (Космические рейнджеры HD), built
headlessly from text sources.

Contents:

| Path | What |
|---|---|
| `mods/SbHello/` | the mod: adds a menu item and a short replica to the **Science base** ("Научная база") dialog |
| `tools/compile.py` | build driver — every path is a CLI argument |
| `tools/run_compile.py` | double-click front-end — the same values as variables at the top |
| `tools/run_compile.cmd` | double-click launcher that also keeps the window open |
| `docs/TOOLS.md` | what to install and where to get it |
| `docs/RSM_SYNTAX.md` | verified `.rsm` reference |
| `docs/STATIONS.md` | station type tokens (`'SB'`, `'PB'`, …) and why they are trusted |
| `docs/WORKFLOW.md` | edit → lint → build → deploy → test, plus troubleshooting |
| `docs/VERIFICATION.md` | what is proved by tooling vs what still needs the game |
| `investigation.txt` | the feasibility investigation (with a resolved addendum) |

## Quick start (Windows)

1. Install: Python 3.9+, `sr-modkit` clone, `rsmc.exe` — see `docs/TOOLS.md`.
2. Open `tools/run_compile.py` and set the four paths in the SETTINGS block:

   ```python
   SRMOD_ROOT = r"C:\tools\sr-modkit"
   RSMC       = r"C:\tools\rsmc\rsmc.exe"
   GAME_DIR   = r"C:\Games\Space Rangers HD A War Apart"
   STAGE      = "all"
   ```

3. Double-click `tools/run_compile.cmd`.
4. Start the game → Mods → enable the mod → **new game** → fly to a Science base.

The build itself is one command (`srmod build`); everything else is checks and
convenience. Sources live in `mods/SbHello/src/`, output in
`mods/SbHello/build/` (generated, not committed).

## Why text sources

`.rsm` is a small text DSL compiled by `rsmc` straight into the game's `.scr`.
No node-graph clicking, so mods are reviewable diffs in git and the whole
pipeline runs without a GUI.

## Status

`investigation.txt` (first pass) concluded headless modding is feasible but
could not compile in the sandbox. Second pass: the mod sources exist, lint and
every encoding gate pass headlessly, and the `'SB'` token is confirmed from real
mod code. The remaining gap is a single Windows-only step — running `rsmc.exe` —
and the in-game test. See `docs/VERIFICATION.md`.
