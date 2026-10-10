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

## If the dialog still does not appear

Set the diagnostic flag in `mods/SbHello/src/DATA/Script/SbHello.src/vars.rsm`:

```js
globalVar("vProbe", "int", "1");   // was 0
```

Rebuild. At **any** station the menu will now show an item like
`[SB probe] type=SB`, which is literally what the game returned. Then either
put the real token into `code.rsm` (`if (vStationType == 'SB')`) or widen the
condition to `== 'SB' || == 'CB'`, and set `vProbe` back to `0`.

Other reasons a station dialog can stay empty:

* the script never started (no `GRun()` / the player ship does not match the
  `ship({player:true, …})` requirement in `world.rsm`);
* `Script/<Name>` was hand-created in `Lang.txt`, so rsmc could not merge its
  text table (see `docs/RSM_SYNTAX.md`);
* `ModCFG.txt` / the in-game mod manager still has the mod switched off, or you
  loaded an old save — **mods require a new game**.
