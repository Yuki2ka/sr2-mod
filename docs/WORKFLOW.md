# Workflow

## 0. One-time setup (Windows)

See `docs/TOOLS.md`. In short: Python 3.9+, `sr-modkit` clone, `rsmc.exe`, then
put their paths in the SETTINGS block of `tools/run_compile.py`.

## 1. Edit

All sources live in `mods/<Mod>/src/`:

```
src/ModuleInfo.txt                     what the player sees in the mod list
src/CFG/Main.txt                       binds the script to the game (+ BV hooks)
src/CFG/Rus/Lang.txt                   your own text keys (NOT Script/<Name>)
src/DATA/Script/<Name>.src/*.rsm       the script
```

Keep `.rsm` as UTF-8 without BOM and `*.txt` as UTF-16LE with BOM. VS Code shows
neither reliably — if in doubt, run:

```bat
python tools\compile.py --fix-encodings
```

A mod that only changes config (no script at all, like `mods/FastGalaxy`) is
legal too: `"script": {"engine": "none"}` in `srmod.json`, and only
`ModuleInfo.txt` + `CFG/**` under `src/`.

## 2. Lint (no external tools, works on any OS)

```bat
python tools\compile.py --stage lint --srmod-root C:\tools\sr-modkit
```

Static checks against rsmc's own DSL plus the known rsmc traps, **plus** a
replay of `src/CFG/Main.txt`: the DAT is parsed, each `BV/OnStart` and
`BV/OnLoad` handler is concatenated exactly the way the engine does it, and the
resulting script text is printed and checked (see `docs/FAST_ITERATION.md` §3).

## 3. Build

Double-click **`tools/run_compile.cmd`** — it builds every mod listed in
`MOD_DIRS` (`mods/SbHello` and `mods/FastGalaxy` by default), keeps going after a
failure, and reports one exit code for the batch. Or a single mod:

```bat
python tools\compile.py --stage build ^
  --srmod-root C:\tools\sr-modkit --rsmc C:\tools\rsmc\rsmc.exe
python tools\compile.py --stage build --mod-dir mods\FastGalaxy ^
  --srmod-root C:\tools\sr-modkit --rsmc C:\tools\rsmc\rsmc.exe
```

Produces `mods/<Mod>/build/` — a game-ready tree with no sources and no
comments. That folder *is* the mod; hand it to players as-is.

## 4. Deploy

```bat
python tools\compile.py --stage deploy --srmod-root C:\tools\sr-modkit ^
  --rsmc C:\tools\rsmc\rsmc.exe --game "C:\Games\Space Rangers HD A War Apart"
```

Default `--deploy-mode junction`: `<game>\Mods\SbHello` becomes a live link to
`build\`, so every rebuild is instantly visible in the game and you never
reinstall. (`--deploy-mode copy --overwrite` copies real files instead, e.g. to
make a standalone install.)

The install path (`Mods/SbHello` by default) lives in `srmod.json` → `install`,
and it is baked into `CacheData.dat` at build time. Change it there, rebuild,
redeploy.

Re-running deploy is safe: whatever occupies `Mods\<Mod>` is cleared first —
but only the link itself (a junction is removed with `os.rmdir`, never with a
recursive delete, which would empty `build/` *through* the link), and the new
link is verified to resolve before the stage reports success.

## 5. Test in game — the first time

1. Start the game → **Mods** → enable the mod(s) → **«Применить»** → **start a
   new game**. One new game is enough: from then on you load the same save
   (next section). A new game is also the only way to see `FastGalaxy` work,
   because the galaxy is generated once and stored in the save.
2. Generation shows eight labels; the sixth, **«Проходит время»**, is 300
   simulated days (`GalaxyWarmupTurns`, `aGalaxyStruct.pas:7`). With
   `FastGalaxy` enabled there are 45 stars instead of 73, so each of those days
   costs less. Details and why it cannot be skipped: `docs/FAST_ITERATION.md` §2.
3. You start docked at the ranger centre, and the **science base is in the same
   system** (generation stage 14 creates RC, science base and medical base in
   the player's starting system) — no flying needed to test the dialog.
4. With `vProbe = 1` every station dialog gets probe items. At RC the type probe
   reads `RC`; at the science base it reads `SB` and the menu contains
   **«Спросить о текущих исследованиях»**.
5. Leave and dock again, and advance a turn: the probe must still be injected
   (the script binds the player as its sole group member, so the game does not
   discard it after the first turn). Details: `docs/STATIONS.md`.

## 5.1 Every change after that — **no new game**

```bat
tools\run_compile.cmd     :: rebuild (junction deploy means no reinstall)
```

then in the game: **load the existing save**. Add **Mods → «Применить»** (or a
game restart) only when you changed something the game reads at startup:
`CFG/Main.txt`, `CFG/Rus/Lang.txt`, `ModuleInfo.txt`, or the enabled-mod list.

| you changed | «Применить»/restart? | new game? |
|---|---|---|
| `.rsm` logic (code, dialogs, states, world bodies) | no | **no** |
| dialog text in `Lang.txt` | yes | no |
| `CFG/Main.txt` (BV hooks, script registration) | yes | no |
| `ModuleInfo.txt`, install path, enabling a mod | yes (+ redeploy) | no |
| star count / galaxy size / custom rules | yes | **yes** |

Why this works, what breaks an old save anyway (renaming a star, a script or a
variable that the save references), and how saved `globalVar` values override
the source — all in **`docs/FAST_ITERATION.md`**.

## 6. Optional second opinion

```bat
python tools\compile.py --stage build --audit ^
  --srmod-root C:\tools\sr-modkit --rsmc C:\tools\rsmc\rsmc.exe ^
  --modkit-root C:\tools\SRHD-XenoModKit
```

Runs XenoModKit's `audit --profile dev` over `build/`. Deeper checks available
directly from the ModKit clone (`python -B srhd.py --help`):

```bat
python -B srhd.py audit build --profile release --json
python -B srhd.py script audit-mod build --json
python -B srhd.py script lint-runtime build --json
python -B srhd.py lang coverage build --base Rus --json
```

## Troubleshooting

| Symptom | Cause |
|---|---|
| rsmc: `has no existing Script^{…} block to merge into` | `Script/<Name>` section missing from the staged Lang — usually the mod name differs between `scriptName()`, `srmod.json` and the `.scr` file name |
| mod is listed but nothing happens | script not registered (`CFG/Main.txt`) or mod disabled in game |
| **I rebuilt but the game behaves exactly like before** | a config change (`Main.txt`, `Lang.txt`, mod list) needs **Mods → «Применить»** or a restart; a `.scr`-only change needs neither, but then you must **load the save** for it to be read |
| **I changed `vProbe`/a global in `vars.rsm` and nothing changed** | global variables are stored in the save and restored by name, so the source value applies to new games only — flip it at runtime (SUDO cheat) or start a new game |
| replicas are empty / show `Script.SbHello.3` | Lang table not merged, or `Script/SbHello` created by hand in `Lang.txt` |
| text is mojibake | a `src/**/*.txt` is not UTF-16LE — `--fix-encodings` |
| build passes, rsmc printed a `warning:` | `srmod build` treats warnings as errors on purpose: a warning means the text table was not merged |
| the menu item never appears, or the probe appeared only at the first dock | check that the station is `SB` (only the science base — `CB` is the Dominion, see `docs/STATIONS.md`), and that `SbGroup` binds the player (`countMin/countMax: 1`, `addPlayer: true`); an unbound zero-ship script is deleted after a turn and the one-time `GCntRun` guard will not restart it |
| «Проходит время» takes forever, or hangs | 300 warmup turns are fixed and not moddable; a heavy `onTurn`/`onGlobal` in *your* script runs 300 times there. Keep them O(1), and use `mods/FastGalaxy` to shrink the galaxy |
| new game dies during generation | `<game>\#####add.log` gets `Galaxy create exception, label = <Stage> seed = <seed>`; `label` is the internal stage (14 = stations, 16 = `BV/OnStart`, 17 = warmup, 18/19 = player setup). A star-count mod that is too aggressive dies in the layout stage — raise `GalaxyCountStars` |
| build stops with `не найден decompiler (rson-decompiler)` | `srmod build` wants a `decompiler` tool even for media-less mods — `tools/compile.py` covers that with a no-op stub; add images or `packages` and you need the real clone (see `docs/TOOLS.md`) |
| `--rsmc <path>: file not found` | `rsmc.exe` moved: fix `RSMC` in `run_compile.py`, or leave it empty and let `compile.py` find `rsmc.exe` next to the sr-modkit clone |
| `deploy failed` / `WinError 183: Cannot create a file when that file already exists` | `<game>\Mods\<Mod>` already exists — `srmod deploy` can only *create* a link, not replace one. `compile.py` now clears it first; a real folder with files inside is refused (move it away, or use `--deploy-mode copy --overwrite`) |
| deploy exits 0 but the game shows no mod | the junction is dangling (its target was moved or never existed). `compile.py` now fails loudly if `ModuleInfo.txt` is not readable through the link. `cmd /c dir /AL "<game>\Mods"` prints the target in brackets |

## Repo hygiene

* `build/` is generated — never commit it (see `.gitignore`).
* Commit the `src/` tree and `srmod.json`; that is the whole mod.
* UTF-16LE files are marked in `.gitattributes` so neither git nor a Windows
  checkout with `core.autocrlf` can corrupt them.
* Never edit files inside the game install: deploy creates a link, and the game
  folder stays pristine.
