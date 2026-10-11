# What is actually verified

Honest split between "proved by tooling/source review" and "needs the game".
Updated after the third pass: the reported one-time probe was traced to the
script instance having no bound ships (see the final addendum in
`investigation.txt`). The source fix is in, but its Windows rebuild and in-game
retest are still pending.

## Verified by running the tools (nothing below is a guess)

Rows marked *Linux* were proved in the headless sandbox that had no game and no
`rsmc.exe`; the rest were proved on the Windows machine, through
`tools/run_compile.py`:

| Claim | How it was proved |
|---|---|
| Latest `srmod lint` passes on `mods/SbHello` with **zero** findings *(Linux)* | `tools/compile.py --stage lint --srmod-root <sr-modkit-root>` after the player-binding fix (DSL check against `data/rsm-dsl.json`, extracted from `rsmc.exe`) |
| All `.rsm` are valid UTF-8 without BOM *(Linux)* | `srmod.build.assert_rsm_is_utf8` over every module |
| All `src/**/*.txt` are UTF-16LE+BOM *(Linux)* | `srmod.build.assert_not_utf8_datnik` over every file (the gate that fails the build on UTF-8 Cyrillic) |
| `scriptName("SbHello")` == `srmod.json:name` == entry path *(Linux)* | `tools/compile.py` preflight |
| `tools/compile.py --fix-encodings` repairs broken encodings *(Linux)* | round-trip test on a deliberately broken copy: detected 3 problems, fixed all 3, lint clean again |
| `ShipType(...) == 'SB'` is the Science base *(Linux)* | two sources: a real line of code in sr-modkit's corpus-built `data/lexicon.json`, and `t_SB` in `rsmc`'s own constant list (see `docs/STATIONS.md`) |
| `AddDialogInject` argument order and meaning *(Linux)* | `data/lexicon.json` (function manual + corpus) **and** XenoModKit issue #17, which quotes the engine sources: arg 1 is a *jump target*, not the injection target |
| Only `rsmc.exe` is required; DAT/Lang/CacheData need no foreign tool *(Linux read)* | `srmod/build.py` — `run_blockpar` uses `srmod/vendor/srblockpar`; media encoding is the only part that wants `rson-decompiler`, and this mod ships no media |
| `srmod build` finishes green on Windows, with `rsmc.exe` doing the compile *(previous source revision)* | `tools/run_compile.py` on Windows: `SbHello.scr` (2860 bytes) plus `Lang.dat`, `Main.dat`, `CacheData.dat`, exit 0; the player-binding lifecycle fix has not been built yet |
| Junction deployment works *(Windows, previous source revision)* | `srmod deploy` exit 0 **and** every file readable through the link: `ModuleInfo.txt`, `CFG\Main.dat`, `CFG\Rus\Lang.dat`, `CFG\CacheData.dat`, `DATA\Script\SbHello.scr`. Caveat found on the way: an earlier link was **dangling** (target `C:\CY\=\sr2-mod\...\build` never existed) while deploy still exited 0, so the game saw nothing — `compile.py` now clears a stale entry and verifies the new link resolves |
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

## Lifecycle finding from reverse-engineered engine source (not a game run)

The user reported that the probe appeared at the first station, then not after
undocking and docking again. Inspection of
[`pakompom/SpaceRangersHD_decomp`](https://github.com/pakompom/SpaceRangersHD_decomp)
explains it:

* `source/screens/fRuinsTalk.pas` invokes `RunDialogCode` for each active script
  while building the station menu, so an active script can re-inject on later
  visits.
* `source/game/aGalaxy.pas` removes a script at end-of-turn when
  `Script.Ships.Count < 1`.
* `source/script/aScript.pas` binds a group member to the player only when the
  group has `addPlayer`/`IncludePlayer`; the `ship(player: true, ...)` template
  requirement alone does not add a bound ship. A count of one with
  `addPlayer: true` is the player alone, not an extra NPC.
* `GCntRun` records starts even after the active instance is deleted. Therefore
  the old `if (!GCntRun(GScriptName)) GRun();` guard prevented a second start.

`world.rsm` now binds the player as the sole `SbGroup` member (`countMin = 1`,
`countMax = 1`, `addPlayer = true`). This is source-reviewed but not yet rebuilt
with the user's Windows `rsmc.exe` or verified in the game.

## NOT verified — needs the game

1. **That the probe and research item appear again after travel and docking.**
   The source lifecycle bug is fixed; runtime behavior still needs a rebuild,
   new game, and repeat-docking test.
2. Whether `'SB'`/`'CB'` covers every Science-base variant and whether the
   dialog text/answer flow behaves correctly in-game.
3. The latest group change has not been compiled/deployed on Windows yet. The
   earlier Windows build was of the previous source revision.
4. Save-game compatibility and interaction with other mods.

The previous build/deploy passed on Windows, but this update needs a fresh
`tools\run_compile.cmd` run. Then enable the mod in a NEW game: the RC probe
should be followed by another probe at a Science base, and the actual research
item should appear for station type `SB` or `CB`.
