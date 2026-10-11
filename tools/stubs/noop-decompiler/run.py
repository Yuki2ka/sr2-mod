#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""No-op stand-in for rson-decompiler/run.py — for mods WITHOUT media.

`srmod build` asks for the `decompiler` tool (rson-decompiler) before it even
looks at the source tree, so a mod that has no images or packages fails with

    error: не найден decompiler (rson-decompiler) — нужен для srgi (медиа)

even though nothing would ever call the encoder. This directory satisfies that
check: run.py is only executed if the mod really has media (.png, *.gai.src/,
*.hai.src/) or packages (*.pkg.src/), and then it refuses loudly on purpose so
the build fails at the right place instead of shipping a broken mod.

When you add media to a mod, install the real tool and point compile.py at it:

    git clone https://github.com/ArtYudin89/rson-decompiler <folder>
    python tools\\compile.py --decompiler <folder>      # or DECOMPILER= in run_compile.py

sr-modkit calls it as:
    python run.py gi encode <src> <dst> --format <argb|delta>
    python run.py pkg pack <staged-dir> <out.pkg>
"""

import sys

INSTALL = (
    "this mod has media or packages, which need the real rson-decompiler "
    "(srgi/srpkg encoders).\n"
    "  install:  git clone https://github.com/ArtYudin89/rson-decompiler <folder>\n"
    "  then:     --decompiler <folder>  (or DECOMPILER= in tools/run_compile.py)"
)


def main() -> int:
    print("noop-decompiler stub: refusing to encode media.", file=sys.stderr)
    print(f"  call: {' '.join(sys.argv[1:])}", file=sys.stderr)
    print(f"  {INSTALL}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
