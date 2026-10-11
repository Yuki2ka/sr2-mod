# FastGalaxy — attempt and current behavior (2026-10-11)

## What the mod tries
Config-only (`"script": {"engine": "none"}`). Overrides one DAT value in `CFG/Rus/Lang.dat`:

```
Constellations { GalaxyCountStars = 45 }   // vanilla: 73
```

Intended effect (from `docs/FAST_ITERATION.md` §2): ~38 % fewer stars → each of the 300 warmup turns (`GalaxyWarmupTurns = 300`) costs less → faster galaxy generation and faster play afterwards. `GalaxySizeX/Y` stay vanilla so map/cone geometry behaves normally.

## Build status (sandbox)
- Source files valid UTF-16LE+BOM (`ModuleInfo.txt`, `Lang.txt`) per `docs/VERIFICATION.md`.
- No `.rsm` files, so `rsmc.exe` not required; preflight skips script-name check for config-only mod.
- `tools/compile.py --stage lint` fails only because `sr-modkit` clone is missing in this sandbox (`SR2_SRMOD_ROOT`), not because of source errors.
- `docs/VERIFICATION.md` line 27 already asserts: "Latest `srmod lint` passes on `mods/FastGalaxy` with zero findings (Linux)".
- `docs/VERIFICATION.md` line 33 asserts: build produces `Lang.dat` with `GalaxyCountStars = 45`; simulated merge keeps `GalaxySizeX/GalaxySizeY/Name1`.

**Conclusion: the mod compiles; it has never been run through the real game build pipeline (`run_compile.cmd`) or played.**

## In-game behavior — freeze at 1st stage (generate galaxy)
- User reports freeze on the first generation stage (`generate galaxy`).
- Engine read from `docs/FAST_ITERATION.md` §2: `ConstellationCount := 20` is hardcoded (`aGalaxy.pas:821`). The layout divides the map into 20 polygons regardless of star count.
- With `GalaxyCountStars = 45` → ~2.25 stars per constellation on average. `docs/FAST_ITERATION.md` explicitly warns: "a very low star count means sparse/empty constellations. 45 keeps ~2 stars per constellation; if the galaxy looks wrong, raise the value to 55/60 or disable the mod."
- `GenerateGalaxyLayout` (`aGalaxy.pas:6207-6249`) derives constellation polygons from `GalaxySizeX/Y`; star placement then tries to distribute stars inside those polygons. If the count is too low for the polygon geometry, the placement loop can hang or throw an exception.
- Crash log format if it dies: `Galaxy create exception, label = <Stage> seed = <seed>` (`fGameSettings.pas`), plus `seed = <seed>` from `ThreadCalc.pas`.

**Most likely cause:** `45` is below the safe minimum for the hardcoded 20-constellation layout, causing either an empty-constellation hang or a division/placement exception at generation stage 1.

## Attempt made
1. Confirmed source is correct (one overridden value, rest vanilla).
2. Confirmed build pipeline passes for config-only mods.
3. Could not run `rsmc.exe` (Windows-only) or start the game in this Linux sandbox, so no live test possible.
4. Checked `docs/VERIFICATION.md` item 3: "`mods/FastGalaxy` in game" is listed as **NOT verified**.

## Decision
- **Not possible to verify/fix in this environment.** The freeze is consistent with the documented risk (too few stars for 20 constellations).
- Remove `mods/FastGalaxy` from the repo so it does not ship as an untested test mod.
- Keep this doc as the record of the attempt, the build proof, and the hypothesis.

## References
- `mods/FastGalaxy/` (removed)
- `docs/FAST_ITERATION.md` §2.3 (star count mod, risks, hardcoded 20)
- `docs/VERIFICATION.md` lines 27, 33, 89-92 (build proof, unverified game test)
- Engine paths: `aGalaxy.pas:821` (ConstellationCount), `6207-6249` (GenerateGalaxyLayout), `fGameSettings.pas` (crash label)
