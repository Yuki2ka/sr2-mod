# Station / base types (the `'SB'` question) — resolved from the engine

The open question from `investigation.txt` — *is `'SB'` really the Science
base?* — is answered from the engine's own tables, not from inference.

## The mapping, straight out of the game

`ShipType(ship)` returns the **string** name of the ship/station type,
`ShipTypeN(ship)` the numeric one. Both come from `TShip.TypeId` and the same
table:

* `aShip.pas:2197 GetTypeNameKey` → `Result := ShipTypeNames[TypeId].Name`
* `aShip.pas:2204 GetLocalizedTypeName` →
  `LocalizedText('ShipType.TypeName.' + GetTypeNameKey)`
* `aConst.pas:381` → `ShipTypeNames: array[TShipType] of TShipTypeInfo`
* `aGalaxyStruct.pas:75-90` → `TShipType` (and `TStationType =
  rstRangerCenter..rstCustomStation`)

A Delphi array constructor is filled in ordinal order, so lining the enum up
with the table gives the complete, exhaustive list:

| Id | `TShipType` | `ShipType` string | What it is in game |
|---|---|---|---|
| 0 | `stKling` | `Kling` | dominator ship |
| 1 | `stRanger` | `Ranger` | ranger |
| 2 | `stTransport` | `Transport` | transport |
| 3 | `stPirate` | `Pirate` | pirate |
| 4 | `stWarrior` | `Warrior` | warrior |
| 5 | `stTranclucator` | `Tranclucator` | tranclucator |
| 6 | `rstRangerCenter` | `RC` | ranger centre (центр рейнджеров) |
| 7 | `rstPirateBase` | `PB` | pirate base (пиратская база) |
| 8 | `rstMilitaryBase` | `WB` | military base (военная база) |
| 9 | `rstScienceBase` | **`SB`** | **science base (научная база)** |
| 10 | `rstBusinessCenter` | `BK` | business centre (бизнес-центр) |
| 11 | `rstMedicalBase` | `MC` | medical base (медицинская база) |
| 12 | `rstDominion` | `CB` | the Dominion — a mobile special station (`aGalaxy.pas:8281`: `TypeId = rstDominion` + `FlyToStar`) |
| 13 | `rstCustomStation` | `UB` | custom (mod-made) station |

Corroborations, all consistent:

* `fGameSettings.pas` stage 14 of new-game generation creates, in the player's
  starting system, `rstRangerCenter`, `rstScienceBase` and `rstMedicalBase`
  (plus pirate/business/military bases near it) — three distinct station
  types, matching `RC`/`SB`/`MC`.
* The rsmc grammar ships the constants `t_RC t_PB t_WB t_SB t_BK t_MC t_CB
  t_UB` — exactly the eight station ordinals 6..13.
* sr-modkit's lexicon: «сменить … основной числовой тип базы, например `t_RC`
  на `t_CB` … в пределах **восьми основных типов станций**».
* The official RScript `Example/` mod tests `ShipType(...) == 'PB'`.

## What this changed in SbHello

The first version injected the research item at `SB` **or** `CB`, because a
real-mod corpus example reads:

```c
if(ShipType(GetShipRuins(Player()))=='SB' || ShipType(GetShipRuins(Player()))=='CB') {
```

`CB` is not a science-base variant — it is the Dominion. That example is a mod
that serves both station kinds on purpose, not evidence about `SB`.
`onDialogBegin` in `mods/SbHello/src/DATA/Script/SbHello.src/code.rsm` now
tests `vStationType == 'SB'` only. Behaviour at a science base is unchanged.

## Tokens that are *not* in the table

Corpus code also contains `ShipType(...) == 'TC'`, `StarRuins(star, 'AS')` and
`'MB_licensed'`. None of those exist in `ShipTypeNames`: mods may **set** a
station's type name (`ShipType(ship, name)` second argument) or change its
numeric type (`RuinsChangeType`, `BuildRuins(..., t_BK)`), so any string can
appear at runtime. Compare against a vanilla token from the table only when you
mean a vanilla station; otherwise expect custom names.

`ShipTypeN` numeric constants (`t_SB`, `t_PB`, …) are the ordinals above and
are safe; the string form is what real mods use, and it is what the `SB`
comparison in this mod uses.

## Probe and the one-time-item bug

`vProbe` is currently **on** in `mods/SbHello/src/DATA/Script/SbHello.src/vars.rsm`.
It deliberately adds diagnostic items to every station dialog so the returned
ruins id, station type, start turn and current turn can be read. At the ranger
centre the type probe reads `RC`; the research item appears only at a science
base (`SB`). Note that `vProbe` is a `globalVar`, so **its value comes from the
save**: changing it in the source affects new games, not a loaded one (see
[`docs/FAST_ITERATION.md`](FAST_ITERATION.md)).

The report that the probe appeared only once was traced to a script-lifecycle
bug, not to `RC` or the `'SB'` comparison. The old `SbGroup` had
`countMin/countMax = 0` and `addPlayer = false`, so the active script had no
bound ships. The engine removes an active script with no bound ships at the end
of a turn. Since `onGlobal` only called `GRun()` while `GCntRun` was zero, that
removed script never restarted. The `ship({player:true, ...})` declaration is
only a start-matching requirement; it does not keep the instance alive.

Fixed source: `SbGroup` now has `countMin = 1`, `countMax = 1`, and
`addPlayer = true`. The player is the one group member, so this creates no NPCs
and keeps the dialog hook active. On top of that the mod now starts itself from
`CFG/Main.txt` (`BV/OnStart`, `BV/OnLoad`) instead of relying on `onGlobal`;
see [`docs/RSM_SYNTAX.md`](RSM_SYNTAX.md#keep-a-dialog-injection-script-alive)
and [`docs/VERIFICATION.md`](VERIFICATION.md).

Other reasons a station dialog can stay empty:

* the script did not start (no `BV` hook, no active instance, `GRun()` never
  reached);
* the script has no player binding (`group(... addPlayer: true ...)`), so it is
  deleted at the next turn;
* `Script/<Name>` was hand-created in `Lang.txt`, so rsmc could not merge its
  text table (see `docs/RSM_SYNTAX.md`);
* `ModCFG.txt` / the in-game mod manager still has the mod switched off, or you
  rebuilt the mod but did not press «Применить» in the mod manager — a config
  change needs that (or a game restart); a rebuilt `.scr` needs neither.
