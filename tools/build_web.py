#!/usr/bin/env python3
"""Собирает веб-страницу: шаблон плюс обе программы и шрифт с самой машины.

Страница — не запись экрана и не картинка: в неё встроен разборщик того же
подмножества Бейсика, что и в `tools/uknc_basic.py`, только на JavaScript.
Поэтому листинг в ней настоящий: его правят, записывают в память и запускают.

Шрифт берётся не из системы, а из ПЗУ УКНЦ: `tools/uknc/font.json` собран по
снимку экрана, где машина напечатала все коды от 32 до 255.

    python3 tools/build_web.py            собрать web/tetris-uknc.html
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "web" / "template.html"
OUT = ROOT / "web" / "tetris-uknc.html"
FONT = ROOT / "tools" / "uknc" / "font.json"
FONT_SHOT = ROOT / "build" / "uknc" / "font.ppm"


def font_hex():
    """224 знака по восемь строк развёртки, строка — байт."""
    sys.path.insert(0, str(ROOT / "tools" / "uknc"))
    import screen_text as st

    if not FONT_SHOT.exists():
        raise SystemExit(
            f"нет снимка шрифта {FONT_SHOT}: снимите его эмулятором "
            f"(tools/uknc/README или docs/UKNC_BASIC_NOTES.md)"
        )
    width, _height, pix = st.read_ppm(FONT_SHOT)
    layout = [(2, 32, 95), (3, 96, 127), (4, 128, 191), (5, 192, 255)]
    bits = {}
    for row, first, last in layout:
        for col, code in enumerate(range(first, last + 1)):
            bits[code] = st.cell_bits(pix, width, col, row)
    out = []
    for code in range(32, 256):
        row_bits = bits.get(code, "0" * 64)
        out.append(bytes(int(row_bits[i * 8:(i + 1) * 8], 2) for i in range(8)).hex())
    return "".join(out)


def main():
    for name in ("TETRIS.BAS", "TETRISC.BAS"):
        if not (ROOT / "src" / name).exists():
            raise SystemExit(f"нет src/{name}")
    page = TEMPLATE.read_text()
    page = page.replace("@@PROG_DIFF@@", (ROOT / "src" / "TETRIS.BAS").read_text().rstrip())
    page = page.replace("@@PROG_CLASSIC@@", (ROOT / "src" / "TETRISC.BAS").read_text().rstrip())
    page = page.replace("@@FONT@@", font_hex())
    OUT.write_text(page)
    print(f"{OUT} — {len(page) // 1024} КБ")


if __name__ == "__main__":
    main()
