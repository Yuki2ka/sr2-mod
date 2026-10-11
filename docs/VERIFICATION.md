# What is actually verified

Honest split between "proved by tooling/source review", "proved in the game" and
"still needs the game". Updated after the fourth pass (fast iteration + the
«Проходит время» phase): see `docs/FAST_ITERATION.md` and ADDENDUM 4 in
`investigation.txt`.

## Verified in the game (player's own machine)

| Claim | Evidence |
|---|---|
| The mod reaches the Science base dialog and the injected item works | player report: «i tested and it works» — after the `SbGroup` player-binding fix (`countMin = countMax = 1`, `addPlayer = true`) and the removal of the `GCntRun` guard, the probe and **«Спросить о текущих исследованиях»** appear at the science base |
| The headless build pipeline produces a mod the game accepts | `tools\run_compile.cmd` on Windows: `SbHello.scr` + `Lang.dat`, `Main.dat`, `CacheData.dat`, junction-deployed into `<game>\Mods\SbHello`, loaded by the game |

The current source revision (`CFG/Main.txt` BV hooks, `vStartTurn`, the
`'CB'` removal, `mods/FastGalaxy`) has **not** been compiled with `rsmc.exe` or
played yet — that is item 5 below.

## Verified by running the tools (nothing below is a guess)

Rows marked *Linux* were proved in the headless sandbox that had no game and no
`rsmc.exe`; the rest were proved on the Windows machine, through
`tools/run_compile.py`:

| Claim | How it was proved |
|---|---|
| Latest `srmod lint` passes on `mods/SbHello` **and** `mods/FastGalaxy` with zero findings *(Linux)* | `tools/compile.py --stage lint` per mod, and one `tools/run_compile.py` run over both (DSL check against `data/rsm-dsl.json`, extracted from `rsmc.exe`) |
| All `.rsm` are valid UTF-8 without BOM; all `src/**/*.txt` are UTF-16LE+BOM *(Linux)* | `srmod.build.assert_rsm_is_utf8` / `assert_not_utf8_datnik` over every module |
| `scriptName("SbHello")` == `srmod.json:name` == entry path *(Linux)* | `tools/compile.py` preflight — and for a config-only mod (`"script": {"engine": "none"}`) preflight now says the name check is skipped instead of failing |
| `src/CFG/Main.txt` is a valid DAT source and survives the build *(Linux)* | `srblockpar.read_text` → `text_to_dat` → `read_dat`: byte-identical tree |
| The `BV/OnStart` and `BV/OnLoad` hooks execute the intended code *(Linux)* | preflight step 4b replays the engine's `ConcatenateValues` (`$8499BC`) per handler and prints the resulting text |
| The mod's `Main.dat` merges into the game's without clobbering it *(Linux)* | simulated `TBlockParEC.MergeFrom` against a fake vanilla tree: `BV.BV = 2.1.2500` and the game's `10_Game` handlers survive, ours are appended (semantics read from `EC_BlockPar.pas:1299-1359`) |
| `mods/FastGalaxy` builds and its `Lang.dat` overrides one value only *(Linux)* | `tools/compile.py --stage build --mod-dir mods/FastGalaxy` → `build/{CFG/Rus/Lang.dat, ModuleInfo.txt}`; read back: `GalaxyCountStars = 45`; simulated merge keeps `GalaxySizeX/GalaxySizeY/Name1` and changes 73 → 45. Preflight skips the `rsmc.exe` requirement for a script-less mod, so this one builds on **any** OS |
| The four `Main.txt` traps are actually caught *(Linux)* | negative test: a crafted `Main.txt` with `//` in a value, a `BV` param, a `ScriptRun('Wrong')` name and an unguarded `OnLoad` fires all four; the real mods stay clean |
| `ShipType(...) == 'SB'` is the Science base — and `'CB'` is **not** a science-base variant *(Linux read)* | the engine's own tables: `TShipType` (`aGalaxyStruct.pas:75-90`) lined up with `ShipTypeNames` (`aConst.pas:381`) via `GetTypeNameKey` (`aShip.pas:2197`) → `SB` = `rstScienceBase`, `CB` = `rstDominion`. See `docs/STATIONS.md` |
| «Проходит время» = 300 warmup turns and is not moddable *(Linux read)* | `GalaxyWarmupTurns = 300` (`aGalaxyStruct.pas:7`) used directly by the loop in `TThreadCreateNewGame.Execute` (`screens/fGameSettings.pas`), `NewGameGenerationStage := 6` around it, `TurnToDateTime` subtracting it, and no config key reading it |
| The star count *is* moddable through `Lang.dat` *(Linux read)* | `aConst.pas:1491 InitializeGameplayConfig` reads `Constellations.GalaxyCountStars/GalaxySizeX/GalaxySizeY` from `LanguageDataConfig`, which `LoadDatConfigAndModOverrides` fills with the mod's `CFG\Rus\Lang.dat` |
| Only `rsmc.exe` is required; DAT/Lang/CacheData need no foreign tool *(Linux read)* | `srmod/build.py` — `run_blockpar` uses `srmod/vendor/srblockpar`; media encoding is the only part that wants `rson-decompiler` |
| `rsmc` is a Windows-only binary *(Linux read)* | Win32 `.exe`; the build stage refuses to run it on `os.name != 'nt'` |
| Junction deployment works *(Windows, earlier revision)* | `srmod deploy` exit 0 **and** every file readable through the link. Caveat found on the way: an earlier link was **dangling** (target never existed) while deploy still exited 0 — `compile.py` now clears a stale entry and verifies the new link resolves |

## Verified by reading engine source (not executed)

These are the claims `docs/FAST_ITERATION.md` rests on. Every one names the
routine, so it can be re-checked in
[`pakompom/SpaceRangersHD_decomp`](https://github.com/pakompom/SpaceRangersHD_decomp).

* **A save load re-reads the `.scr` from disk.** `TScript.LoadState` (`$657690`)
  starts with `LoadFromFile` (`$656D1C`), which evicts its cache entry in a
  `finally`; `TScript.SaveState` (`$656E90`) excludes compiled instructions.
* **Templates, variables, stars, planets, items and groups are restored by
  name**; a missing template is a warning (`Warning: Script not found - X`), an
  unknown variable is a warning, a missing star raises.
* **`BV/OnLoad` runs on every save load** (`RunConfigOnLoadHandlers`,
  `aGalaxy.pas $7A3A2C`, called from `aSaveLoad.pas:270` and `:590`), and
  **`BV/OnStart` runs at generation `Stage := 16`** — before the warmup loop
  (`Stage := 17`).
* **`ScriptRun` needs an `IsScriptActive` guard**: `SF_ScriptRun` (`$61EB20`)
  matches `ScriptFileName` first, then falls back to the template name, and
  `TryStartScriptInstanceFromTemplate` (`aScript.pas:1112`) creates
  unconditionally.
* **In-process mod reload without restarting the exe**: `Rangers.dpr:690-745`
  re-runs `LoadDatConfigAndModOverrides` + runtime re-init when
  `ReloadScriptTemplates or ReloadModsRequested`; «Применить»
  (`fMods.pas:884 ApplyClick`) writes `Mods\ModCFG.txt` and raises the flag.
* **A mod-set mismatch on load is only logged** (`aGalaxy.pas:1400-1410`).
* **No script function can suspend or shorten the simulation.** All 755
  `Scope.Add` registrations scanned: the only galaxy field written is
  `CurrentTurn` (`SF_CurTurn`, `$608800`). `StasisModEnabled` — the flag
  `TThreadCalc.Execute` (`$7E4BC4`) checks before `Galaxy.NextDay` — is written
  only by init, save load and the `ZAWARUDO` cheat (`CheatCode.pas:1509`).
* **Your script runs 300 times during generation** (`NextDay` →
  `Script.RunTurnCode`), which is why a heavy `onTurn` hangs the phase.
* Lifecycle finding from the third pass (probe appeared once, then never):
  `fRuinsTalk.pas` runs dialog code per active script; `aGalaxy.pas` deletes a
  script with no bound ships at end of turn; `GCntRun` counts starts even after
  deletion, so the old guard blocked the restart.

## NOT verified — needs the game

1. **The `start=`/`now=` probe experiment** (`docs/FAST_ITERATION.md` §1.5):
   `start=0 now=301` on a new game (1 galaxy turn before the warmup loop +
   300 inside it), `start=0 now=<save turn>` after loading a
   save that already had the instance, `start=<turn> now=<turn>` when
   `BV/OnLoad` had to create one. This is the direct proof that iteration needs
   no new game.
2. **That «Применить» alone is enough** after a `Main.txt`/`Lang.txt` change,
   without closing the exe.
3. **`mods/FastGalaxy` in game**: real generation time, and whether 45 stars
   produce a sane galaxy (constellation count is hardcoded at 20,
   `aGalaxy.pas:821`). If generation dies, `#####add.log` will say
   `Galaxy create exception, label = <Stage> seed = <seed>`.
4. **Writing `vProbe` at runtime** with the `SUDO` cheat (`CheatSudo`,
   `CheatCode.pas:1706`) — the mechanism is read from source, the keystrokes and
   the exact text form are not confirmed.
5. **The current source revision on Windows**: `CFG/Main.txt`, `vars.rsm`
   (`vStartTurn`), `code.rsm` (`'CB'` removed, probe text), and `FastGalaxy`
   have never been through `rsmc.exe`/`srmod build` on the player's machine.
6. Interaction with other mods (star-count mods in particular change the same
   `Constellations` block — last enabled mod wins).

## Next run on Windows

```bat
tools\run_compile.cmd        :: builds SbHello and FastGalaxy, deploys both
```

then, in the game: Mods → enable what you want → **«Применить»** → start **one**
new game (FastGalaxy only affects new games) → and from then on rebuild +
**load that save** for every further change.
