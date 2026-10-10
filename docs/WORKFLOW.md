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

## 5. Test in game

1. Start the game → **Mods** → enable the mod → **start a NEW game** (mods do
   not apply to existing saves).
2. Fly to a Science base (Научная база) and talk to it.
3. The menu should contain **"Спросить о текущих исследованиях"**.

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
| the menu item never appears | script did not start, or the station is not `'SB'` — see `docs/STATIONS.md` |

## Repo hygiene

* `build/` is generated — never commit it (see `.gitignore`).
* Commit the `src/` tree and `srmod.json`; that is the whole mod.
* UTF-16LE files are marked in `.gitattributes` so neither git nor a Windows
  checkout with `core.autocrlf` can corrupt them.
