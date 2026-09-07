#!/usr/bin/env python3
"""Делает из TETRIS.BAS его мигающего двойника TETRISC.BAS.

В БЕЙСИКе нет ни модулей, ни включаемых файлов: две версии игры — это две
полные копии программы. Копию, которую правят руками, через неделю сравнивать
уже бесполезно, поэтому мигающая версия не пишется отдельно, а собирается из
основной заменой ровно одной подпрограммы — той самой, ради которой весь
проект и затевался.

Разница между версиями:

* основная (5100) сравнивает старый и новый набор клеток и трогает только
  разницу: сдвиг горизонтальной I — одно стирание и одна отрисовка;
* мигающая (5100) стирает все четыре старые клетки и печатает все четыре
  новые, как это делает наивная реализация: восемь операций вместо двух,
  и между стиранием и печатью фигура на экране исчезает.

    python3 tools/make_classic.py > src/TETRISC.BAS
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "TETRIS.BAS"

CLASSIC_RENDER = """5100 REM ---- CLASSIC RENDER: WIPE THE PIECE, THEN PRINT IT AGAIN ----
5101 REM THIS IS THE NAIVE WAY THE PROJECT WARNS ABOUT. IT ERASES ALL
5102 REM FOUR OLD CELLS AND PRINTS ALL FOUR NEW ONES EVEN WHERE THEY
5103 REM OVERLAP, SO THE PIECE BLINKS ON EVERY MOVE AND EVERY TURN.
5104 SI%=(CT%-1)*4+CR%
5105 FOR I%=0 TO 3
5106 GX%=AX%(I%)
5107 GY%=AY%(I%)
5108 GOSUB 8100
5109 NEXT I%
5110 FOR I%=0 TO 3
5111 GX%=CX%+SX%(SI%,I%)
5112 GY%=CY%+TY%(SI%,I%)
5113 GOSUB 8000
5114 NEXT I%
5115 LOCATE HX%,BY%+19
5116 RETURN
"""

HEADER_SWAPS = [
    (
        "REM * THE ACTIVE PIECE IS UPDATED BY CELL DIFF: A MOVE REPRINTS    *",
        "REM * THE ACTIVE PIECE IS WIPED AND PRINTED AGAIN ON EVERY MOVE    *",
    ),
    (
        "REM * ONLY THE CELLS THAT REALLY CHANGED, SO IT DOES NOT BLINK.    *",
        "REM * AND EVERY TURN, SO IT BLINKS. IT IS HERE FOR COMPARISON.     *",
    ),
    (
        "REM * THE BLINKING TWIN OF THIS PROGRAM IS TETRISC.BAS.            *",
        "REM * THE FLICKER-FREE ORIGINAL IS TETRIS.BAS.                     *",
    ),
]


def make_classic(source):
    text = source
    for old, new in HEADER_SWAPS:
        if old not in text:
            raise SystemExit(f"в исходнике нет строки шапки: {old!r}")
        text = text.replace(old, new)
    start = text.index("5100 REM ")
    end = text.index("6000 REM ")
    block = text[start:end]
    if "5131 LOCATE" not in block and "5115 LOCATE" not in block:
        raise SystemExit("подпрограмма 5100 изменилась: проверьте замену вручную")
    return text[:start] + CLASSIC_RENDER + text[end:]


def main():
    if not SOURCE.exists():
        raise SystemExit(f"нет {SOURCE}")
    sys.stdout.write(make_classic(SOURCE.read_text()))


if __name__ == "__main__":
    main()
