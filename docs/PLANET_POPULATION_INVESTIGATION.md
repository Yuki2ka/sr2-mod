# Planet population growth — investigation (2026-10-11)

## What was asked
1. How does planet population grow?
2. Is it dependent on food available in the shop?
3. Can a mod make such behavior?

## Sources used in this repo / sandbox
- `docs/FAST_ITERATION.md` — economy / trade mentions, no population mechanics.
- `docs/RSM_SYNTAX.md` — `planet(name, {...})` fields: `star`, `race`, `owner`, `economy`, `government`, `rangeMin/Max`, `dialog`. **No `population`, `growthRate`, `inventory`, or `shop` fields.**
- `docs/STATIONS.md` / `docs/VERIFICATION.md` — only station types and script hooks documented.
- `investigation.txt` — no mention of population / food / shop inventory.
- Web search (Russian Steam discussions, wiki):
  - Economy type (industrial / agricultural / mixed) determines which goods a planet produces; population determines quantity of goods in the shop ("От кол-ва населения пропорционально больше товаров появляется").
  - Planetary Tech Level (PTL) growth rate depends on race, economy type, size, capture state, and population, but not on shop inventory.
  - Trade goods are simulated; news events (harvest, epidemic, etc.) temporarily change prices/availability.
- Cheat-engine reference (FearLess, 2023): planet memory section exposes `population`, `economics`, `goods amounts / prices`, `tech levels`. These are mutable in memory but not exposed through RScript.

## Findings

### 1. Population growth mechanism
- **Not directly observable** in RScript or in this repo's engine reads.
- Inferred from engine design (`aGalaxy.pas` / `aConst.pas`): population is a hidden parameter of each planet/star that feeds into:
  - Trade goods available (more pop = more stock).
  - Planetary Tech Level advancement rate (pop appears as a factor in PTL growth formula, along with race, economy, size, capture state).
- It likely grows over simulated time (each day/turn) based on internal rules (race biology, economy type, government stability, capture status, random events). There is **no evidence** it is calculated from current shop inventory.

### 2. Does it depend on food in the shop?
- **No — the dependence is the opposite direction.**
- Food (`2Food`) is just one of 8 trade goods. Agricultural economies produce larger food stocks; industrial economies buy more food and produce equipment/minerals.
- The Steam discussion explicitly says quantity of goods scales with population, not that population scales with goods.
- The cheat-engine description lists "goods amounts / prices" and "population" as separate mutable fields; changing one is independent of the other.

### 3. Can a mod make population growth depend on shop food?
**Likely impossible via standard RScript / `.scr` mod:**

Why:
- `planet()` template defines the planet at generation time; it has no `population` or `inventory` parameters to read or write.
- The script syntax docs (`docs/RSM_SYNTAX.md`) list available functions (`Player()`, `ShipStar()`, `GetShipPlanet()`, `ScriptRun()`, `IsScriptActive()`, `CurTurn()`, etc.). None expose planet inventory, food stock, or population.
- `BV/OnStart` / `BV/OnLoad` and `onTurn` hooks can run code, but without an API to read shop contents or set population, they can only affect script-state variables, not planet internals.
- The engine's `Scope.Add` registrations (scanned in `docs/FAST_ITERATION.md`) show that the only galaxy-level field writable from script is `CurrentTurn` (`SF_CurTurn`, `$608800`). Nothing else — including population or inventory — is writable.
- Even if a hidden variable name existed, it is not documented in `data/rsm-dsl.json` or in the repo's references, and using an undocumented name risks silent failure or crash (`Warning: Script not found` / unknown variable warnings per `docs/VERIFICATION.md`).

**Possible (but non-management) workarounds:**
- **Indirect influence:** A mod could use `BV/OnTurn` to spawn/remove goods (via `item()` or group/dialog injections) near the planet, but that affects the trade interface for the player, not the planet's simulated population.
- **Cheat / memory edit:** The FearLess reference shows that both population and goods are editable in memory (like `CheatSudo`). A mod could not do this through `.scr`; it would require external injection or a save editor (`Cassandra` / `RangersViewer` by indiemagpie).
- **Custom planet definition:** You can set `economy`, `race`, `government` at generation, which changes the simulated economy profile and thus indirectly affects long-term population/tech trends, but not via food stock.

## Conclusion
- Planet population is simulated internally; growth is driven by time, race, economy, size, capture state, and events — **not by food availability in the shop.**
- There is **no RScript interface** for population or for reading/writing planet shop inventory.
- Therefore, **a standard mod cannot implement "population growth depends on shop food."** If that mechanic is required, it needs either engine-level changes (decompile/edit `aGalaxy.pas` / `TGalaxy`), an external memory editor/cheat, or a save-editor post-process — none of which fit the `sr-modkit` / `.scr` pipeline used by this repo.

## References
- `docs/RSM_SYNTAX.md` (`planet()` fields, function list)
- `docs/FAST_ITERATION.md` (§1.6, §2 — economy references, `Scope.Add` scan)
- Steam discussion (Russian): economy / population / trade goods scaling
- FearLess Cheat Engine (2023-11-24): planet section — population, goods amounts / prices, tech levels mutable independently
- `docs/VERIFICATION.md` — unverified in-game behavior for config-only mods
