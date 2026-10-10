# What is actually verified

Honest split between "proved by tooling" and "needs the game". Updated after the
second investigation pass (see the addendum at the bottom of
`investigation.txt`).

## Verified in this sandbox (Linux, headless, no game installed)

Everything below was executed here, not read from a forum:

| Claim | How it was proved |
|---|---|
| `srmod lint` passes on `mods/SbHello` with **zero** findings | `python -m srmod lint` (DSL check against `data/rsm-dsl.json`, which is extracted from `rsmc.exe` itself) |
| All `.rsm` are valid UTF-8 without BOM | `srmod.build.assert_rsm_is_utf8` over every module |
| All `src/**/*.txt` are UTF-16LE+BOM | `srmod.build.assert_not_utf8_datnik` over every file (the gate that fails the build on UTF-8 Cyrillic) |
| `scriptName("SbHello")` == `srmod.json:name` == entry path | `tools/compile.py` preflight |
| `tools/compile.py --fix-encodings` repairs broken encodings | round-trip test on a deliberately broken copy: detected 3 problems, fixed all 3, lint clean again |
| `ShipType(...) == 'SB'` is the Science base | two sources: a real line of code in sr-modkit's corpus-built `data/lexicon.json`, and `t_SB` in `rsmc`'s own constant list (see `docs/STATIONS.md`) |
| `AddDialogInject` argument order and meaning | `data/lexicon.json` (function manual + corpus) **and** XenoModKit issue #17, which quotes the engine sources: arg 1 is a *jump target*, not the injection target |
| Only `rsmc.exe` is required; DAT/Lang/CacheData need no foreign tool | reading `srmod/build.py` — `run_blockpar` uses `srmod/vendor/srblockpar`, and the media step is skipped because this mod ships no media |
| `rsmc` needs Windows | it is a Win32 `.exe`; no Wine in the sandbox, so the build stage refuses early with a clear message instead of a confusing crash |

## Verified earlier by reading tool sources (not executed)

* `rsmc build <entry.rsm> -o <out.scr> [--lang-txt F] [--lang-dat F]` — CLI shape
  from the RScript README and from `srmod.build.run_rsmc`, which builds exactly
  that argv.
* `srmod build` step order and its gates (`docs/STAGE0.md` + `build.py`).
* Language table: rsmc writes `Script/<ScriptName>/<n>` into the staged
  `Lang.txt`, which then becomes `CFG/<lang>/Lang.dat`.
* XenoModKit's runtime advice: prefer `restart` over `fastexit` for
  station/planet dialogs (`dialog-fastexit-on-station`).

## NOT verified — needs your Windows machine and the game

1. **That rsmc accepts this exact source.** The build stage has never run: it is
   the one step that cannot happen here. Lint and the encodings are clean, so
   the risk is small, not zero.
2. **That the menu item appears on a Science base in game.** Static checks
   cannot prove runtime behaviour. If it does not, `vProbe = 1` shows the real
   `ShipType` (see `docs/STATIONS.md`).
3. Whether `'SB'` also covers every science-base variant — a real mod tested
   `'SB' || 'CB'` together, so `'CB'` may be needed too.
4. Whether an empty group (`countMin: 0, countMax: 0`) is accepted by the
   installed rsmc version. It is a documented, supported shape in RScript, but
   this exact source has not been compiled.
5. Junction deployment (`srmod deploy`) — Windows-only, needs the game folder.
6. Save-game compatibility and interaction with other mods.

## How to turn 1–5 into verified facts

Run once on Windows:

```bat
python tools\compile.py --stage all --srmod-root C:\tools\sr-modkit ^
  --rsmc C:\tools\rsmc\rsmc.exe --game "C:\Games\Space Rangers HD A War Apart"
```

and, when it is green, paste the output into a file in this repo (or open an
issue). Then the table above can be updated from "not verified" to "verified".
