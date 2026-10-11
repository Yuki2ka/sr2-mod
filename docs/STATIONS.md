# Station / base types (the `'SB'` question)

The open question from `investigation.txt` — *is `'SB'` really the Science
base?* — is now answered from two independent machine-readable sources.

## Verified

`ShipType(ship)` returns a **string** type; `ShipTypeN(ship)` returns the
numeric one. For bases the string is a short token.

**Token `'SB'` = Science base ("Научная база").** Evidence:

1. **Real mods.** `data/lexicon.json` in sr-modkit is built from a corpus of 330
   decompiled SRHD mods (183 657 observed calls). Its `ShipType` examples are
   copies of real code, and the first one is:

   ```c
   if(ShipType(GetShipRuins(Player()))=='SB' || ShipType(GetShipRuins(Player()))=='CB') {
   ```

   That is the exact shape this mod uses, taken from a working mod.

2. **The compiler's own constant list.** The `.rsm` grammar shipped with `rsmc`
   (`rsmc.rsm-language-0.1.0/syntaxes/rsm.tmLanguage.json`) enumerates the
   built-in constants and contains **`t_SB`** next to `t_PB`, `t_UB`, `t_WB`,
   `t_RC`, `t_MC`, `t_BK`, `t_CB`, `t_Kling`.

`'PB'` (pirate base) is confirmed by the official RScript `Example/` mod, which
does `if (ShipType(GetShipRuins(Player())) == 'PB') { … }`.

## Token table

| Token | Meaning | Confidence |
|---|---|---|
| `SB` | Science base (Научная база) | **high** — real-mod code + `t_SB` constant |
| `CB` | a science-base variant (checked together with `SB` in real code) | medium |
| `PB` | Pirate base (Пиратская база) | **high** — official example |
| `TC` | Trade centre | medium — real-mod code |
| `WB`, `MB`, `UB` | other base kinds (`t_WB`, `t_MB`-ish, `t_UB` constants) | low — constants only |
| `AS` | station looked up via `StarRuins(star,'AS')` in real mods | medium |
| `RC` | Ranger centre | low |

`ShipTypeN` numeric constants: `t_PB t_SB t_UB t_WB t_RC t_MC t_BK t_CB t_Kling …`
(ships have `t_Ranger t_Warrior t_Pirate t_Transport t_Liner t_Diplomat …`).
Numeric types are coarse — several custom string types share them — so prefer
the string comparison.

## Probe and the one-time-item bug

`vProbe` is currently **on** in `mods/SbHello/src/DATA/Script/SbHello.src/vars.rsm`.
It deliberately adds diagnostic items in dialogs so the returned ruins ID and
station type can be read. If the player starts at the Ranger Centre, seeing
`RC` there is expected; the player does not need to spawn at a Science base.
At a Science base, the type probe should read `SB` (or `CB`) and the research
item should appear.

The report that the probe appeared only once was traced to a script-lifecycle
bug, not to `RC` or the `'SB'` comparison. The old `SbGroup` had
`countMin/countMax = 0` and `addPlayer = false`, so the active script had no
bound ships. The engine removes an active script with no bound ships at the end
of a turn. Since `onGlobal` only calls `GRun()` while `GCntRun` is zero, that
removed script never restarted. The `ship({player:true, ...})` declaration is
only a start-matching requirement; it does not keep the instance alive.

Fixed source: `SbGroup` now has `countMin = 1`, `countMax = 1`, and
`addPlayer = true`. The player is the one group member, so this creates no NPCs
and keeps the dialog hook active. Rebuild/redeploy, start a **new game**, then
check the probe at RC and again at a Science base. See
[`docs/RSM_SYNTAX.md`](RSM_SYNTAX.md#keep-a-dialog-injection-script-alive) and
[`docs/VERIFICATION.md`](VERIFICATION.md) for what is source-verified vs still
needs a game run.

Other reasons a station dialog can stay empty:

* the script did not start (the initial `onGlobal` `GRun()` condition failed);
* the script has no player binding (`group(... addPlayer: true ...)`), so it is
  deleted at the next turn;
* `Script/<Name>` was hand-created in `Lang.txt`, so rsmc could not merge its
  text table (see `docs/RSM_SYNTAX.md`);
* `ModCFG.txt` / the in-game mod manager still has the mod switched off, or you
  loaded an old save — **mods require a new game**.
