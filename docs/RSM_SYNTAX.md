# `.rsm` quick reference

Verified, not guessed: the declaration tables below are extracted from
`rsmc.exe` itself (sr-modkit ships them as `data/rsm-dsl.json`), and the call
shapes are taken from the official `Example/` mod in the RScript repo and from
`data/lexicon.json` (977 functions, built from a corpus of 330 real mods).

## File layout

A script is a **directory of modules** plus one entry point. Import order does
not matter; `main.rsm` is whatever `srmod.json` points `script.entry` at.

```
SbHello.src/
  main.rsm      scriptName("SbHello") + import from './….rsm';
  vars.rsm      variables
  world.rsm     star / planet / ship / group
  states.rsm    state (behaviour of groups)
  dialogs.rsm   dialog / dialogMsg / dialogAnswer
  code.rsm      export function onInit / onTurn / onDialogBegin / onGlobal
```

```js
scriptName("SbHello");

import from './vars.rsm';
import from './dialogs.rsm';
```

## Two hard encoding rules

| File | Encoding | Why |
|---|---|---|
| `*.rsm` | **UTF-8, no BOM** | `srmod` rejects a BOM outright |
| `src/**/*.txt` (`ModuleInfo.txt`, `CFG/Main.txt`, `CFG/<lang>/Lang.txt`) | **UTF-16LE + BOM** | the game reads only UTF-16; UTF-8 with Cyrillic is silently mangled — no error at build, garbage in game |

`tools/compile.py --fix-encodings` repairs both in place.

## Declarations

`positional` = arguments before the options object; `required` = rsmc errors
without them; `strictFields` = unknown field is an error.

| Declaration | Positional | Notable fields | Required |
|---|---|---|---|
| `scriptName(name)` | name | — | — |
| `star(name, {...})` | name | `constellation`, `noKling`, `noComeKling` | — |
| `planet(name, {...})` | name | `star`, `race`, `owner`, `economy`, `government`, `rangeMin/Max`, `dialog` | `star` |
| `ship({...})` | — | `star`, `player`, `count`, `owner`, `type`, `speedMin/Max`, `status*`, `ruins` | `star` |
| `group(name, {...})` | name | `planet`, `state`, `countMin/Max`, `addPlayer`, `type`, `dialog`, `distSearch` | `planet`, `state` |
| `state(name, {...})` | name | `move`, `onTalk`, `onTalkCode`, `onActCode`, `code`, `transitions:[{to,when}]` | — |
| `dialog(name, {...})` | name | `message`, `code` | — |
| `dialogMsg(name, {...})` | name | `text`, `command`, `code`, `answers:[{name,names,when}]` | — |
| `dialogAnswer(name, {...})` | name | `text`, `next`, `answerCommand`, `code` | — |
| `item(name, {...})` | name | `mainType`, `type`, `size`, `level`, `radius`, `owner`, `useless` | — |
| `place(name, {...})` | name | `type` (`free`,`nearPlanet`,`inPlanet`,`toStar`,`nearItem`,`fromShip`,`coords`), `star`, `obj1`, `obj2` | `type` |
| `ether(name, {...})` | name | `type`, `msg`, `unique` | `msg` |
| `localVar/globalVar(name, type, init?)` | name, type | types: `unknown`, `int`, `dword`, `str`, `float`, `array` | — |

Enum samples straight from rsmc (full lists in `data/rsm-dsl.json`):

* `planet.owner`: `Maloc Peleng People Fei Gaal Kling None Pirate ByPlayer GroupToggle`
* `ship.type` / `group.type`: `Ranger Warrior Pirate Transport Liner Diplomat Blazer0-7 Keller0-7 Terron0-7 Tranclucator`
* `planet.government`: `Anarchy Dictatorship Monarchy Republic Democracy`
* `state.move`: `none move follow jump landing free`
* `dialogAnswer.answerCommand`: `restart exit shop hangar planet block fastexit`

> Six fields rsmc does **not** validate at all — a typo builds silently and
> breaks only in game: `item.type`, `item.useless`,
> `dialogAnswer.answerCommand`, `ether.type`, `groupLink.rel1`,
> `starLink.hole`.

## The four hooks

```js
export function onInit() {        // script start, new game
  //;                            // empty body needs at least a comment statement
}
export function onTurn() {}       // every game turn, while the script runs
export function onDialogBegin() {}// game builds a station/planet/ship dialog
export function onGlobal() {      // every turn, regardless of script state
    if (!GCntRun(GScriptName)) {
        GRun();                  // start this script once per playthrough
    }
}
```

### Keep a dialog-injection script alive

`ship({player: true, ...})` is a template-matching requirement; it does **not**
by itself bind the player to the running script instance. The engine removes an
instance after a turn when it has zero script-bound ships. If `onGlobal` uses
`if (!GCntRun(GScriptName)) GRun();`, that removed instance will not restart:
`GCntRun` still records the first run. This produces exactly the symptom where
an injected item appears at the first station and vanishes after leaving it.

For a persistent dialog hook, make the player a member of a group:

```js
group("SbGroup", {planet: "SbPlanet", state: "SbIdle",
      countMin: 1, countMax: 1, addPlayer: true});
```

The player counts toward the group's `1`, so no extra NPC is spawned. Keep the
state inert if the group exists only to retain the script. On station, planet,
and ship dialog construction, the game runs the dialog hook for each active
script, so the hook can add its menu item again on every visit. This lifecycle
rule was traced in the reverse-engineered engine source; still verify the final
behavior in the target game.

## Dialogs

```js
dialog("DialogSbHello", {code: function() {
    DChange('MsgSbHello');        // by name — or DChange(0) by declaration index
    exit;
}});

dialogMsg("MsgSbHello", {text: "Replica text. <br> and <Player> work.", code: function() {
    DAdd('AnsSbHelloBack');       // attach an answer to this replica
}});

dialogAnswer("AnsSbHelloBack", {text: "Player's line.", answerCommand: "restart"});
```

* `DChange` / `DAdd` / `ChangeState` accept **name or index**, index counts from 0
  in declaration order. Names survive reordering — prefer them.
* Dialog text goes in `text:` only. `DText(CT(...))` inside `code:` produces a
  double `CT(CT(...))` in rsmc and an extra empty replica; `srmod lint` catches it.
* `answerCommand: "restart"` returns to the station menu. On planets and
  stations `fastexit` does **not** close the branch reliably — use `restart`.

## Injecting into a game dialog (how this mod hooks the Science base)

```js
export function onDialogBegin() {
    if (GetShipRuins(Player()) > 0) {                        // docked somewhere
        vStationType = ShipType(GetShipRuins(Player()));
        if (vStationType == 'SB') {                          // science base
            AddDialogInject('DialogSbHello', '', "Ask about the research", 1);
        }
    }
}
```

`AddDialogInject(dialogName, greetingAdd, answerText, priority, …)`:
1. **dialogName** — the dialog *started when the player clicks the new item*.
   It is a jump target, not the injection target: the item is added to whatever
   station menu is open.
2. **greetingAdd** — text appended to the NPC greeting (`''` to add nothing).
3. **answerText** — the menu item caption; may be any string expression,
   including `Format(...)` and `CT('Script.Name.N')`.
4. **priority** — higher floats above other injections.

Related: `AddDialogOverride(dialog, priority, GAnswerData?)` replaces the whole
opening replica; `AddDialogBlock(answerText, 2)` hides an existing menu item
(must run *before* the injection you want to filter);
`InjectAnswer(dialog, text, GAnswerData, code?)` adds an item to a script dialog.

## Text and formatting

* `CT('Items.Engine.Type.8')` reads a Lang key; `Format("…<0>…", "<0>", value)`
  substitutes; `<br>` line break; `<Player>` player name;
  `<color=r,g,b>…</color>` colour; `<clr>`/`<clrEnd>` highlight.
* Every `text:` value is written by the build into
  `CFG/<lang>/Lang.dat` under `Script/<ScriptName>/<n>`. **Never** create that
  section by hand in `Lang.txt` — rsmc then cannot merge its own table and the
  mod goes mute with zero errors.
* Avoid typographic dashes and «quotes» in visible game text: they exist in
  CP1251 but not necessarily in the game's bitmap fonts.

## Traps `srmod lint` checks for you

1. `DText(...)` inside a `dialogMsg` `code:` block (double `CT`).
2. `state("12", …)` — a numeric state name makes `ChangeState(12)` resolve by
   name instead of by index.
3. Unknown / misspelled declaration fields (silently dropped by rsmc).
4. A flag-like field given as a string: write `race: ["Maloc"]`, not `race: "Maloc"`
   — the latter compiles but never reaches the game.
