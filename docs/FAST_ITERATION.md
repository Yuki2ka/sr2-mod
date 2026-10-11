# Fast iteration: no new game per change, and the «Проходит время» phase

Two questions from the task, two answers.

| Question | Answer |
|---|---|
| Do I have to start a new game every time I change the mod? | **No.** One new game, then rebuild → load that same save forever. Details: [§1](#1-changing-the-mod-without-starting-a-new-game) |
| Can a mod skip «Проходит время»? | **No — but it can make it much shorter.** The phase is a fixed loop of `GalaxyWarmupTurns = 300` simulated days; no config key and no script function reaches that number. What a mod *can* change is how much work each of those 300 days costs, by shrinking the galaxy: [`mods/FastGalaxy`](../mods/FastGalaxy). Details: [§2](#2-the-проходит-время-phase) |

Everything below is read out of the engine (a full Delphi decompilation of
SRHD 2.1.2500) with file and routine names, so any claim can be checked. What
still needs a game run is listed in [`docs/VERIFICATION.md`](VERIFICATION.md)
and marked **[in-game]** here.

---

## 1. Changing the mod without starting a new game

### 1.1 The recipe

1. Edit `src/`, then rebuild — double-click `tools\run_compile.cmd`, or:

   ```bat
   python tools\compile.py --stage build
   ```

2. In the game: **Mods → «Применить»** — only if you changed something the game
   reads at startup (`CFG/Main.txt`, `CFG/Rus/Lang.txt`, `ModuleInfo.txt`, the
   mod list itself). A pure `.rsm` change does not need it.
3. **Load the existing save.** That is the whole loop.

A new game is only needed for changes to the galaxy itself — star count, size,
custom rules, races — because those are read once during generation and then
live inside the save.

### 1.2 Why that works (the engine chain)

**Config side.** `LoadDatConfigAndModOverrides` (`GR_Main.pas`, routine at
`$4CC738`) reads `Mods\ModCFG.txt` (`CurrentMod=`), then merges every enabled
mod's `CFG\Main.dat`, `CFG\<lang>\Lang.dat` and `CFG\CacheData.dat` into the
game's own config trees. It runs at process start and again whenever
`ReloadScriptTemplates or ReloadModsRequested` (`Rangers.dpr:690-745`), which
also re-initialises the runtime, refreshes ship derived state, rebinds script
imports and jumps straight to the load screen. «Применить» in the mod manager
(`fMods.pas:884 ApplyClick`) writes `ModCFG.txt` and raises
`ReloadModsRequested` — so that whole re-read happens **without restarting the
exe**.

**Script side.** Loading a save (`aSaveLoad.pas LoadGameFromSaveBuffer` →
`TGalaxy.LoadFromBuffer`) does, in order:

1. Matches saved script templates **by name**. A template that no longer exists
   is skipped with a log line `Warning: Script not found - <Name>`; the load
   continues.
2. Restores shared script variables **by name** (`SharedScriptVariables.GetVarNE`);
   a saved variable the new definition does not have produces a warning only.
3. For each saved instance calls `TScript.LoadState` (`$657690`), whose **first
   statement is `LoadFromFile(ScriptFileName)`** (`$656D1C`) — i.e. the `.scr`
   is re-read from disk on every single save load, and `LoadFromFile` evicts its
   cache entry in a `finally` block, so there is no stale in-memory copy.
4. Rebinds stars/planets/items/ships **by name** (`GetStar(Name)` etc.).
5. Runs `Galaxy.RunConfigOnLoadHandlers` (`aSaveLoad.pas:270` and `:590` →
   `aGalaxy.pas $7A3A2C`) — every sub-block of `MainDataConfig.BV/OnLoad` is
   executed through `ExecuteScriptText(Handler.ConcatenateValues, nil)`.

`TScript.SaveState` (`$656E90`) is explicit that **compiled instructions are
not saved**: only Ether text, variable values, object ids, ship bindings, groups
and states go into the save. Code always comes from the `.scr` on disk. That is
the whole reason iteration does not need a new game.

This is also what `mods/SbHello/src/CFG/Main.txt` uses:

```
BV ^{
    OnStart ^{
        0DayScripts ^{
            SbHello=ScriptRun(ShipStar(Player()), GetShipPlanet(Player()), 'SbHello');
        }
    }
    OnLoad ^{
        Runtime ^{
            01=if(!IsScriptActive('SbHello')) ScriptRun(ShipStar(Player()), GetShipPlanet(Player()), 'SbHello');
        }
    }
}
```

(`^` marks a *sorted* block in the DAT text form — the same thing `srmod new`
writes; `~` is unsorted. The parameter names inside a handler are irrelevant:
`ConcatenateValues` drops them and joins the values.)

* `OnStart` fires from `RunConfigOnStartHandlers` at generation `Stage := 16`
  (`fGameSettings.pas`, before the warmup — see §2.1), so a brand-new game gets
  the instance the usual way.
* `OnLoad` fires on **every** save load, so the mod attaches itself to a save
  made before the mod existed, and heals itself if the instance was lost.
  `IsScriptActive` (`SF_IsScriptActive`, `$6057C8`) guards it: `ScriptRun`
  (`SF_ScriptRun`, `$61EB20`) first looks for a running instance whose
  `ScriptFileName` matches, and otherwise creates one unconditionally from the
  template (`TryStartScriptInstanceFromTemplate`, `aScript.pas:1112`) — so
  without the guard you would get a second instance.
* A save made with a different mod set is **not rejected**: the mismatch is only
  logged (`aGalaxy.pas:1400-1410`, `Warning! Mod sets mismatch: …`).

### 1.3 What each kind of change needs

| you changed | rebuild | «Применить»/restart | new game |
|---|---|---|---|
| `.rsm` logic (`code.rsm`, `dialogs.rsm`, `states.rsm`, `world.rsm` bodies) | yes | no | **no** |
| dialog text (`Lang.txt` → `Lang.dat`) | yes | yes | no |
| `CFG/Main.txt` (BV hooks, `Data/Script` registration) | yes | yes | no |
| `ModuleInfo.txt`, `srmod.json install`, enabling/disabling a mod | yes + redeploy | yes | no |
| **new** script name (a name not yet registered in `Data/Script`) | yes | yes | no |
| galaxy shape: star count, size, races, custom rules, warmup | yes | yes | **yes** |

«Restart» = closing and reopening the exe; both paths end in the same
`LoadDatConfigAndModOverrides` + runtime re-init.

### 1.4 What *does* break an existing save

* **Renaming a `star`/`planet`/`item`/`group` declared in `world.rsm`.** Step 4
  above rebinds by name and `GetStar(Name)` raises when the star is unknown →
  the log shows `Error. Script.GameLoad` and the save does not load. Add new
  declarations instead of renaming old ones.
* **Renaming the script** (`scriptName()` / `srmod.json` / the `.scr` file name /
  `Script.<Name>` in `Main.txt`) — saved instances then find no template
  (`Warning: Script not found`), and the `BV/OnLoad` hook would start a fresh
  one under the new name. Keep the three places in sync (repo convention) and
  treat the name as permanent once a save depends on it.
* **Saved variable values persist and win over the source.** `globalVar`s are
  part of the galaxy save and are restored by name, so editing the initial value
  in `vars.rsm` changes new games only. That is why `vProbe` in SbHello cannot
  simply be flipped in the source for an old save: either start a new game, or
  write it at runtime — the `SUDO` cheat executes script text against the live
  galaxy (`CheatSudo`, `CheatCode.pas:1706-1750`, `$50C088`; a leading
  `'ScriptName'` scopes the text to that script). **[in-game]** exact keystrokes
  not yet confirmed.
* Rebuilding while a save is loaded is harmless (the `.scr` is read at load
  time), but do it from the main menu anyway: `srmod build` rewrites the whole
  `build/` tree that the junction points at, and there is no reason to have the
  game reading it mid-write.

### 1.5 The 30-second experiment that proves it in game **[in-game]**

`onInit` in `code.rsm` stores `vStartTurn = CurTurn()` and the probe prints
`probe: type=<0> start=<1> now=<2>`. `CurTurn()` reads `Galaxy.CurrentTurn`
(`SF_CurTurn`, `$608800`), which is 0 when `BV/OnStart` runs (stage 16, before
any turn) and 301 when generation ends (§2.1):

| probe reads | what happened |
|---|---|
| `start=0 now=301` | new game; the instance was created by `BV/OnStart` at stage 16 and survived all 301 generation turns |
| `start=0 now=<save turn>` | the save already had the instance and its globals were restored by name — **no new game, no restart** |
| `start=<save turn> now=<save turn>` | the save had no instance (mod added later, or the engine had dropped it): `BV/OnLoad` created one — the hook works |

`vStartTurn` is a `localVar`, so a *restored* instance keeps the value stored in
the save; only a freshly created instance takes the current turn.

Also useful: generation stage 14 creates the **ranger centre, the science base
and the medical base in the player's own starting system** (pirate base at
`StarDistances[3]`, business centre at `[1]`, military base at `[2]`), so
testing the science-base dialog needs no flying at all.

### 1.6 Faster still, without rebuilding

`SUDO` (`CheatSudo`) runs arbitrary script text in the live game, which is the
cheapest possible way to test one function's behaviour — no rebuild, no reload,
no save. Use it for logic questions; use the rebuild-and-load loop for anything
touching dialogs, Lang text or hooks.

---

## 2. The «Проходит время» phase

### 2.1 What it is, exactly

Two counters drive new-game generation in `TThreadCreateNewGame.Execute`
(`screens/fGameSettings.pas`): `Stage` (internal, 0..19, only used by the crash
log) and `NewGameGenerationStage` (0..8, what the intro screen shows —
`fIntroduction.pas:208` walks the labels `ICW1..ICW8`/`MCW1..MCW8` up to it).

```pascal
Stage := 16;
Galaxy.RunConfigOnStartHandlers;        // <- BV/OnStart: mods get control here
Galaxy.AppendIntegritySnapshot;
NewGameGenerationStage := 6;            // <- the sixth intro-screen label
Stage := 17;
CalculateGalaxyTurnAndWait;
if ExitScreenLoop then Exit;
for I := 1 to GalaxyWarmupTurns do      // GalaxyWarmupTurns = 300
begin
  if I mod 20 = 0 then SysUtils.Sleep(1);
  CalculatePlayerStarTurnAndWait;
  if ExitScreenLoop then Exit;
  CalculateGalaxyTurnAndWait;
  if ExitScreenLoop then Exit;
end;
Stage := 18;   // dock at the RC, starting skills, starting equipment
Stage := 19;   // ApplyCharacterPreset, RunGlobalScriptsForContext(star, 0)
NewGameGenerationStage := 8;            // generation finished
```

`GalaxyWarmupTurns = 300` and `TurnsPerYear = 365` are compile-time constants
(`aGalaxyStruct.pas:7`), so the phase simulates **300 days** of history — the
war, the economy, ranger ranks, dominator expansion — before the player takes
control. `Galaxy.CurrentTurn` starts at 0 (`aGalaxy.pas:1028`) and every
`Galaxy.NextDay` does `Inc(CurrentTurn)` (`:2340`); with the single
`CalculateGalaxyTurnAndWait` before the loop plus 300 inside it, the player
takes control at **`CurrentTurn = 301`**. The calendar is defined around the
same constant: `TGalaxy.TurnToDateTime(Turn) = Turn + 511341.5 -
GalaxyWarmupTurns`, i.e. the end of the warmup *is* day one of the game, and
many gameplay gates compare against it (`Achievements.pas:427/458`,
`aGalaxy.pas:2301`, `:2453`, `:5414`).

Stage 6 is the sixth of the eight labels the intro screen lights up in order
(`fIntroduction.pas:190 UpdateGenerationProgress` activates
`ICW<n>`/`MCW<n>` as `DisplayedGenerationStage` catches up with
`NewGameGenerationStage`, and generation is over at 8). The label *text* lives
in the interface data, not in the code, so calling it «Проходит время» is an
identification from three directions rather than a string found in the source:
it is the phase right before the player is placed in the galaxy, it is the one
that takes 300 full galaxy turns, and it is the phase XenoModKit's docs name
when describing mods that hang there.

That the phase is a well-known pain point is corroborated independently:
XenoModKit's README documents runtime patterns «связанные с зависанием на
"Проходит время"», and its scripting guide describes an infinite
«Проходит время» as the symptom of a heavy per-turn script.

### 2.2 Why a mod cannot skip it

Every door was checked:

* **The loop bound is an immediate constant**, not data. No `Main.dat`,
  `Lang.dat`, `CacheData.dat` or `newgame.txt` key anywhere in the engine reads
  a warmup/history length. (`newgame.txt` CustomRules has `KlingStrength`,
  `KlingAggro`, `KlingSpawn`, `PirateAggro`, `CoalAggro`, … and no turn count.)
* **The only engine flag that suspends the simulation is `Galaxy.StasisModEnabled`.**
  `TThreadCalc.Execute` (`ThreadCalc.pas`, `$7E4BC4`) wraps the whole
  `Galaxy.NextDay` block in `if Galaxy.StasisModEnabled <> 1`, so setting it
  would make warmup turns nearly free. It is written in exactly three places:
  initialisation to 0 (`aGalaxy.pas:871`), save load (`aGalaxy.pas:1771/1778`)
  and the **`ZAWARUDO` cheat** (`CheatCode.pas:1509 CheatZawarudo`). It is not
  reachable from config, and no script function assigns it — all 755
  `Scope.Add` registrations were scanned; the only galaxy field any script
  function writes is `CurrentTurn` (`CurTurn(N)`). It is also saved with the
  galaxy and permanently clears the "clean game" flag
  (`aGalaxy.pas:4287`), so it is a cheat, not a knob.
* **`ExitScreenLoop` is the window-close path, not an abort.** `Exit` inside the
  loop skips `Stage := 18/19` (docking, starting equipment,
  `ApplyCharacterPreset`, `RunGlobalScriptsForContext`) and never sets
  `NewGameGenerationStage := 8`, so the intro screen would wait forever.
* **`ForceNextDay()`** only sets `ScriptEndTurnRequested`, which the UI
  dispatches via `TryDispatchScriptEndTurn` — meaningless during generation.
* **`loadlibrary`/`libraryfunction`** exist in the DSL, so a DLL could in
  principle write the constant — but Delphi evaluates a `for` bound once at loop
  entry, so it would have to land before `Stage := 17`, and it would ship a
  version-specific memory patch with the mod. Not a modding solution; listed
  only for completeness.

So: **the number of warmup turns is not moddable.** What is moddable is how
expensive each turn is, and what the galaxy looks like when they finish.

### 2.3 What a mod *can* do: fewer stars → shorter phase

Each warmup turn runs the normal turn machinery: `TGalaxy.NextDay`
(`aGalaxy.pas:2310-2360`) loops `Star.NextDay(False)` over **every star**, runs
script Turn/Global code, `Inc(CurrentTurn)`, then stations, constellation
statistics, prices, ranger quotas and `RefreshTechLevel`. The cost per turn
scales with the number of stars and the ships on them.

Star count is genuinely data-driven and mod-overridable:

* `aConst.pas:1491 InitializeGameplayConfig` — called from
  `InitializeGlobalUiRuntime` (`Globals.pas:675`, ~`:1194`) **after**
  `LoadDatConfigAndModOverrides` — reads `Constellations.GalaxyCountStars`
  (**73**), `GalaxySizeY` (**100**) and `GalaxySizeX` (**145**) out of
  `LanguageDataConfig`, i.e. out of the merged `CFG\Rus\Lang.dat`.
* `TThreadCreateNewGame.Execute` then creates that many stars, and
  `GenerateGalaxyLayout` (`aGalaxy.pas:6207-6249`) derives constellation
  polygons from `GalaxySizeX/Y`.
* Merge semantics (`TBlockParEC.MergeFrom`, `EC_BlockPar.pas:1299-1359`): a
  same-named **block** from the mod merges recursively (nothing is lost), while a
  same-named **parameter** is deleted and re-added — so the mod's value wins and
  its neighbours (`Name1`, `GalaxySizeX`, …) survive.
* Community precedent for exactly this key: `RefABitMoreStars` /
  `RefABitMoreStars5` / `RefABitMoreStars10` add 10/15/20 star systems, and
  `FairanGalaxy` adds star types and background systems — all shipped as
  Lang-only mods.

**`mods/FastGalaxy`** is that lever pointed the other way: a script-less
(`"script": {"engine": "none"}`) config-only mod whose whole content is

```
Constellations { GalaxyCountStars = 45 }   // vanilla: 73
```

Expected effect: ~38 % fewer stars, so each of the 300 warmup turns and every
later turn costs proportionally less — roughly 2-3× faster generation on a
typical machine (estimate, **[in-game]** not measured). The galaxy is also
smaller to fly around, which keeps helping after generation.

Risks and how to handle them:

* `ConstellationCount := 20` is hardcoded (`aGalaxy.pas:821`) and the layout
  divides the map into 20 polygons regardless, so a very low star count means
  sparse/empty constellations. 45 keeps ~2 stars per constellation; if the
  galaxy looks wrong, raise the value to 55/60 or disable the mod.
* Generation failures are diagnosable: the crash log line is
  `Galaxy create exception, label = <Stage> seed = <seed>`
  (`fGameSettings.pas`, outer handler) plus `seed = <seed>` from
  `ThreadCalc.pas`. `label` tells you which stage died; `#####add.log` in the
  game folder has it.
* The value is read **once at startup** — enabling the mod needs «Применить» or
  a restart, and it only affects **new** games (the galaxy is in the save).
* Nothing else is touched: `GalaxySizeX/Y` stay vanilla so the map, jumps and
  constellation geometry behave normally.

Other, non-mod levers for the same phase (no code needed):

* `newgame.txt` CustomRules — `KlingStrength/KlingAggro/KlingSpawn/PirateAggro/CoalAggro = 0`
  means far less to simulate and a galaxy much closer to its initial condition
  at turn 300. The in-game «тонкая настройка» UI edits the same values.
* `CurTurn(N)` from `BV/OnStart` moves the calendar (and every `CurrentTurn`
  gate) without simulating anything — the cheap way a mod can "start later". It
  does **not** shorten the warmup and it desynchronises the date from the actual
  state of the galaxy, so SbHello does not use it.

### 2.4 Keep your own mod out of the way

Your script runs 300 times during generation: `RunConfigOnStartHandlers`
creates the instance at `Stage := 16`, then every warmup turn calls
`NextDay` → `Script.RunTurnCode` → your `onTurn`/`onGlobal`. An `onTurn` that
loops over stars or ships is what makes *other people's* games hang on
«Проходит время». SbHello's `onTurn` is empty and its `onInit` is O(1) — keep
it that way. `Ether(0, '', text)` (`SF_Ether`, `$60C800`) is safe during
generation: it only calls `AddOrUpdatePlayerBubble` and dereferences no object.

---

## 3. Reproducing the headless checks

No game is needed for the config/DAT half. `sr-modkit` vendors a pure-Python
BlockPar reader (`srmod/vendor/srblockpar`), and `tools/compile.py --stage lint`
now uses it to parse `src/CFG/Main.txt` the way the engine does. Preflight step
**4b `check_main_dat`** reports a problem when:

* a DAT **value** contains `//` — values are cut at `//`, and both the game
  parser and `srblockpar` strip it while parsing, so the check runs on the raw
  file text; the engine would execute a truncated statement and report nothing;
* a param named `BV` sits inside the `BV` block — it overwrites the game version
  (`BV.BV = 2.1.2500`, checked in `GR_Main.pas:2983`) in the merged `Main.dat`;
* `BV/OnStart` or `BV/OnLoad` has no handler **block**, or a handler is empty
  (the engine executes every block inside the hook as one script via
  `ConcatenateValues`, `$8499BC`);
* a hook runs `ScriptRun('<name>')` where `<name>` is not one of the
  `Data/Script` registrations — `ScriptRun` takes the template name, not the
  `Script.<Name>` path;
* `BV/OnLoad` calls `ScriptRun` without an `IsScriptActive` guard — a second
  instance on every load.

It also *prints* each hook's concatenated text, so you can read what the engine
will execute before rsmc and before the game:

```bat
python tools\compile.py --stage lint --srmod-root C:\tools\sr-modkit
python tools\compile.py --stage lint --mod-dir mods\FastGalaxy --srmod-root C:\tools\sr-modkit
```

```
[preflight] Main.txt: BV/OnStart/0DayScripts executes: ScriptRun(ShipStar(Player()), GetShipPlanet(Player()), 'SbHello');
[preflight] Main.txt: BV/OnLoad/Runtime executes: if(!IsScriptActive('SbHello')) ScriptRun(ShipStar(Player()), GetShipPlanet(Player()), 'SbHello');
```

Two further properties were verified once with `srblockpar` directly rather than
on every run (steps and results are recorded in `investigation.txt`, ADDENDUM 4):

* `Main.txt` round-trips losslessly: `read_text` → `text_to_dat` → `read_dat`
  gives a byte-identical tree, so the build's `.dat` carries exactly what the
  source says;
* a simulated `TBlockParEC.MergeFrom` of the mod tree into a fake vanilla tree
  (`BV.BV = 2.1.2500` plus the game's own `10_Game` handlers) keeps the version
  param and the vanilla handlers and appends ours — the merge is additive for
  blocks and last-wins for params, matching `EC_BlockPar.pas:1299-1359`. The
  same simulation on `mods/FastGalaxy`'s `Lang.dat` keeps
  `GalaxySizeX/GalaxySizeY/Name1` while overriding `GalaxyCountStars` 73 → 45.

See [`docs/TOOLS.md`](TOOLS.md) and [`docs/VERIFICATION.md`](VERIFICATION.md).
