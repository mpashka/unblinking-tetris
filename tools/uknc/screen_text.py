#!/usr/bin/env python3
"""Читает снимок экрана УКНЦ как текст 64x24.

Эмулятор отдаёт картинку, а проверять хочется словами: «в этой строке написано
Ошибка 24», а не «сравните два снимка глазами». Поэтому таблица начертаний
снимается с самой машины — программой, которая печатает подряд все коды от 32
до 255, — и дальше каждая знакоместная клетка снимка ищется в этой таблице.

    python3 tools/uknc/screen_text.py снимок.ppm          напечатать экран
    python3 tools/uknc/screen_text.py --build шрифт.ppm   пересобрать таблицу

Таблица лежит рядом, в font.json: без неё модуль бесполезен.
"""

import json
import pathlib
import sys

COLS, ROWS = 64, 24
# Геометрия снята с самого снимка: текст занимает x 65..575 (64 клетки по 8
# точек), строки идут с шагом 11 начиная с y=13, начертание высотой 8.
X0, Y0, CW, CH, GH = 65, 13, 8, 11, 8
FONT_PATH = pathlib.Path(__file__).resolve().parent / "font.json"


def read_ppm(path):
    data = pathlib.Path(path).read_bytes()
    if not data.startswith(b"P6"):
        raise SystemExit(f"{path}: не PPM формата P6")
    parts = data.split(b"\n", 3)
    width, height = map(int, parts[1].split())
    return width, height, parts[3]


def cell_bits(pix, width, col, row):
    """Знакоместо как строка из 0 и 1: белый текст на цветном фоне."""
    bits = []
    for dy in range(GH):
        y = Y0 + row * CH + dy
        for dx in range(CW):
            x = X0 + col * CW + dx
            i = (y * width + x) * 3
            bits.append("1" if pix[i + 1] > 128 else "0")
    return "".join(bits)


def load_font():
    if not FONT_PATH.exists():
        raise SystemExit(f"нет таблицы начертаний {FONT_PATH}: соберите её с --build")
    return json.loads(FONT_PATH.read_text())


def build_font(path):
    """Снимок charset-программы -> таблица «начертание -> код символа».

    Строка 0 занята эхом RUN, строки 1-2 держат коды 32..127, строки 3-6 —
    128..255. Порядок задан самой программой, поэтому подписывать нечего.
    """
    width, _height, pix = read_ppm(path)
    font = {}
    layout = [(2, 32, 95), (3, 96, 127), (4, 128, 191), (5, 192, 255)]
    for row, first, last in layout:
        for col, code in enumerate(range(first, last + 1)):
            font.setdefault(cell_bits(pix, width, col, row), code)
    FONT_PATH.write_text(json.dumps(font))
    return len(font)


def screen_text(path, font=None):
    font = font or load_font()
    width, _height, pix = read_ppm(path)
    blank = "0" * (CW * GH)
    lines = []
    for row in range(ROWS):
        chars = []
        for col in range(COLS):
            bits = cell_bits(pix, width, col, row)
            if bits == blank:
                chars.append(" ")
                continue
            code = font.get(bits)
            chars.append(chr(code) if code is not None else "�")
        lines.append("".join(chars).rstrip())
    return lines


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    if args[0] == "--build":
        count = build_font(args[1])
        print(f"начертаний в таблице: {count}")
        return
    for line in screen_text(args[0]):
        print(line)


if __name__ == "__main__":
    main()
