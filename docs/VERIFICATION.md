# What is actually verified

Honest split between "proved by tooling" and "needs the game". Updated after the
second investigation pass (see the addendum at the bottom of
`investigation.txt`).

## Verified by running the tools (nothing below is a guess)

Rows marked *Linux* were proved in the headless sandbox that had no game and no
`rsmc.exe`; the rest were proved on the Windows machine, through
`tools/run_compile.py`:

| Claim | How it was proved |
|---|---|
| `srmod lint` passes on `mods/SbHello` with **zero** findings *(Linux)* | `python -m srmod lint` (DSL check against `data/rsm-dsl.json`, which is extracted from `rsmc.exe` itself) |
| All `.rsm` are valid UTF-8 without BOM *(Linux)* | `srmod.build.assert_rsm_is_utf8` over every module |
| All `src/**/*.txt` are UTF-16LE+BOM *(Linux)* | `srmod.build.assert_not_utf8_datnik` over every file (the gate that fails the build on UTF-8 Cyrillic) |
| `scriptName("SbHello")` == `srmod.json:name` == entry path *(Linux)* | `tools/compile.py` preflight |
| `tools/compile.py --fix-encodings` repairs broken encodings *(Linux)* | round-trip test on a deliberately broken copy: detected 3 problems, fixed all 3, lint clean again |
| `ShipType(...) == 'SB'` is the Science base *(Linux)* | two sources: a real line of code in sr-modkit's corpus-built `data/lexicon.json`, and `t_SB` in `rsmc`'s own constant list (see `docs/STATIONS.md`) |
| `AddDialogInject` argument order and meaning *(Linux)* | `data/lexicon.json` (function manual + corpus) **and** XenoModKit issue #17, which quotes the engine sources: arg 1 is a *jump target*, not the injection target |
| Only `rsmc.exe` is required; DAT/Lang/CacheData need no foreign tool *(Linux read)* | `srmod/build.py` — `run_blockpar` uses `srmod/vendor/srblockpar`; media encoding is the only part that wants `rson-decompiler`, and this mod ships no media |
| `srmod build` finishes green on Windows, with `rsmc.exe` doing the compile *(Windows)* | `tools/run_compile.py` on Windows: `SbHello.scr` (2860 bytes) plus `Lang.dat`, `Main.dat`, `CacheData.dat`, exit 0 |
| Junction deployment works *(Windows)* | `srmod deploy` exit 0 **and** every file readable through the link: `ModuleInfo.txt`, `CFG\Main.dat`, `CFG\Rus\Lang.dat`, `CFG\CacheData.dat`, `DATA\Script\SbHello.scr`. Caveat found on the way: an earlier link was **dangling** (target `C:\CY\=\sr2-mod\...\build` never existed) while deploy still exited 0, so the game saw nothing — `compile.py` now clears a stale entry and verifies the new link resolves |
| `rsmc` is a Windows-only binary *(Linux read)* | it is a Win32 `.exe`, and the build stage refuses to run it on `os.name != 'nt'` instead of crashing confusingly |

## Verified earlier by reading tool sources (not executed)

* `rsmc build <entry.rsm> -o <out.scr> [--lang-txt F] [--lang-dat F]` — CLI shape
  from the RScript README and from `srmod.build.run_rsmc`, which builds exactly
  that argv.
* `srmod build` step order and its gates (`docs/STAGE0.md` + `build.py`).
* Language table: rsmc writes `Script/<ScriptName>/<n>` into the staged
  `Lang.txt`, which then becomes `CFG/<lang>/Lang.dat`.
* XenoModKit's runtime advice: prefer `restart` over `fastexit` for
  station/planet dialogs (`dialog-fastexit-on-station`).

## NOT verified — needs the game

1. **That the menu item appears on a Science base in game.** Static checks
   cannot prove runtime behaviour. If it does not, `vProbe = 1` shows the real
   `ShipType` (see `docs/STATIONS.md`).
2. Whether `'SB'` also covers every science-base variant — a real mod tested
   `'SB' || 'CB'` together, so `'CB'` may be needed too.
3. Whether an empty group (`countMin: 0, countMax: 0`) is accepted by the
   installed rsmc version. It is a documented, supported shape in RScript, and
   the build of this source passed with it, but nothing has tested it at runtime.
4. Save-game compatibility and interaction with other mods.

The compile and deploy stages have now run green on Windows (table above), so
`SbHello` is built, linked into `<game>\Mods\SbHello`, and only the in-game
behaviour is left: enable the mod, start a NEW game, dock at a Science base.
