# Workflow

## 0. One-time setup (Windows)

See `docs/TOOLS.md`. In short: Python 3.9+, `sr-modkit` clone, `rsmc.exe`, then
put their paths in the SETTINGS block of `tools/run_compile.py`.

## 1. Edit

All sources live in `mods/<Mod>/src/`:

```
src/ModuleInfo.txt                     what the player sees in the mod list
src/CFG/Main.txt                       binds the script to the game
src/CFG/Rus/Lang.txt                   your own text keys (NOT Script/<Name>)
src/DATA/Script/<Name>.src/*.rsm       the script
```

Keep `.rsm` as UTF-8 without BOM and `*.txt` as UTF-16LE with BOM. VS Code shows
neither reliably — if in doubt, run:

```bat
python tools\compile.py --fix-encodings
```

## 2. Lint (no external tools, works on any OS)

```bat
python tools\compile.py --stage lint --srmod-root C:\tools\sr-modkit
```

Static checks against rsmc's own DSL plus the two known rsmc traps.

## 3. Build

Double-click **`tools/run_compile.cmd`**, or:

```bat
python tools\compile.py --stage build ^
  --srmod-root C:\tools\sr-modkit --rsmc C:\tools\rsmc\rsmc.exe
```

Produces `mods/SbHello/build/` — a game-ready tree with no sources and no
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

## 5. Test in game

1. Start the game → **Mods** → enable the mod → **start a NEW game** (mods do
   not apply to existing saves).
2. The first station may be the Ranger Centre. With `vProbe = 1`, a probe at
   RC is expected; it reports the current station, not a failure of the Science
   base check. Then travel to a Science base and talk to it.
3. At the Science base the probe should report `SB` (or `CB`) and the menu
   should contain **"Спросить о текущих исследованиях"**.
4. To verify the reported lifecycle bug is fixed, leave and dock again (advance
   a turn if needed): the probe should still be injected. The script binds the
   player as its sole group member so the game does not discard the script after
   its first turn. Details: [`docs/STATIONS.md`](STATIONS.md).

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
| replicas are empty / show `Script.SbHello.3` | Lang table not merged, or `Script/SbHello` created by hand in `Lang.txt` |
| text is mojibake | a `src/**/*.txt` is not UTF-16LE — `--fix-encodings` |
| build passes, rsmc printed a `warning:` | `srmod build` treats warnings as errors on purpose: a warning means the text table was not merged |
| the menu item never appears, or the probe appeared only at the first dock | check that the station is `SB`/`CB`, and that `SbGroup` binds the player (`countMin/countMax: 1`, `addPlayer: true`); an unbound zero-ship script is deleted after a turn and the one-time `GCntRun` guard will not restart it — see `docs/STATIONS.md` |
| build stops with `не найден decompiler (rson-decompiler)` | `srmod build` wants a `decompiler` tool even for media-less mods — `tools/compile.py` covers that with a no-op stub; add images or `packages` and you need the real clone (see `docs/TOOLS.md`) |
| `--rsmc <path>: file not found` | `rsmc.exe` moved: fix `RSMC` in `run_compile.py`, or leave it empty and let `compile.py` find `rsmc.exe` next to the sr-modkit clone |
| `deploy failed` / `WinError 183: Cannot create a file when that file already exists` | `<game>\Mods\<Mod>` already exists — `srmod deploy` can only *create* a link, not replace one. `compile.py` now clears it first; a real folder with files inside is refused (move it away, or use `--deploy-mode copy --overwrite`) |
| deploy exits 0 but the game shows no mod | the junction is dangling (its target was moved or never existed). `compile.py` now fails loudly if `ModuleInfo.txt` is not readable through the link. `cmd /c dir /AL "<game>\Mods"` prints the target in brackets |

## Repo hygiene

* `build/` is generated — never commit it (see `.gitignore`).
* Commit the `src/` tree and `srmod.json`; that is the whole mod.
* UTF-16LE files are marked in `.gitattributes` so neither git nor a Windows
  checkout with `core.autocrlf` can corrupt them.
