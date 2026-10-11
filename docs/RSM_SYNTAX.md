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
export function onInit() {        // an instance was created (new game, BV/OnLoad, GRun)
  //;                            // empty body needs at least a comment statement
}
export function onTurn() {}       // every game turn, while the instance is alive
export function onDialogBegin() {}// game builds a station/planet/ship dialog
export function onGlobal() {      // fallback self-start, see below
    GRun();
}
```

`onGlobal` is **not** "every turn regardless of state": the engine's
`RunGlobalScriptsForContext` (`$64DEB8`) evaluates `ConditionCode` only for
templates **without** an active instance, at a fixed set of moments (planet,
government and ruins-talk screens; hangar; jump; the main form; arcade battle;
and once at the end of new-game generation, `Stage := 19`). `GRun()` itself
(`SF_GRun`, `$605480`) only sets `ScriptTemplateStartRequested`, so calling it
unguarded is harmless — it asks for an instance that already exists to be left
alone.

Do **not** guard it with `GCntRun(GScriptName)`: that reads the template's
`UseCount`, which survives instance deletion *and is stored in the save*, so the
guard fires once and then blocks every restart for the rest of the campaign.
That was this mod's original bug (see `docs/STATIONS.md`).

### Start the script from `CFG/Main.txt` instead (recommended)

`onGlobal` can only ever be a fallback. The reliable way — and the reason a
rebuild does not need a new game — is the engine's own `BV` hooks, executed as
script text from the merged `Main.dat`:

```
BV ^{
    OnStart ^{
        0DayScripts ^{
            Handler1=ScriptRun(ShipStar(Player()), GetShipPlanet(Player()), 'MyScript');
        }
    }
    OnLoad ^{
        Runtime ^{
            Handler1=if(!IsScriptActive('MyScript')) ScriptRun(ShipStar(Player()), GetShipPlanet(Player()), 'MyScript');
        }
    }
}
```

(`^` marks a *sorted* block in the DAT text form — the same thing `srmod new`
writes; `~` is unsorted. The parameter names inside a handler are irrelevant:
`ConcatenateValues` drops them and joins the values.)

* `RunConfigOnStartHandlers` runs `BV/OnStart` once, at generation `Stage := 16`
  — before the 300 warmup turns, and after the player and the starting stations
  exist.
* `RunConfigOnLoadHandlers` runs `BV/OnLoad` on **every save load**, after the
  galaxy and the scripts are restored, so the mod re-attaches itself to a save
  made before it existed.
* `ScriptRun` takes the template **name** from `Data/Script` (not
  `Script.<Name>`), matches a running instance by `ScriptFileName` first, and
  otherwise creates one unconditionally — hence the `IsScriptActive` guard.
* Each hook holds one or more **handler blocks** (`0DayScripts ^{ … }` above),
  and the engine executes every handler's concatenated values as one script;
  never put a param named `BV`
  inside `BV` (it would overwrite the game version `BV.BV = 2.1.2500`), and
  never put `//` inside a value (values are truncated there, silently).

`tools/compile.py --stage lint` parses `src/CFG/Main.txt` and prints what each
hook will execute, checking all of the above. Full chain, with addresses:
[`docs/FAST_ITERATION.md`](FAST_ITERATION.md).

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
