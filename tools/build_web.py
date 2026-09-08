#!/usr/bin/env python3
"""Собирает веб-страницу: шаблон плюс обе программы и шрифт с самой машины.

Страница — не запись экрана и не картинка: в неё встроен разборщик того же
подмножества Бейсика, что и в `tools/uknc_basic.py`, только на JavaScript.
Поэтому листинг в ней настоящий: его правят, записывают в память и запускают.

Шрифт берётся не из системы, а из ПЗУ УКНЦ: `tools/uknc/font.json` собран по
снимку экрана, где машина напечатала все коды от 32 до 255.

    python3 tools/build_web.py            собрать web/tetris-uknc.html
"""

import datetime
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "web" / "template.html"
OUT = ROOT / "web" / "tetris-uknc.html"
SITE = ROOT / "web" / "site" / "index.html"

# Артефакт claude.ai оборачивает страницу в свой каркас сам, поэтому в OUT лежит
# только содержимое. Отдельному веб-серверу каркас никто не дописывает: без
# объявления кодировки браузер угадывает её сам и показывает кракозябры вместо
# кириллицы. Поэтому вторым файлом собирается самостоятельная страница.
SKELETON = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{head}</head>
<body>
{body}</body>
</html>
"""
FONT_HEX = ROOT / "tools" / "uknc" / "font.hex"
FONT_SHOT = ROOT / "build" / "uknc" / "font.ppm"


def font_hex():
    """224 знака по восемь строк развёртки, строка — байт.

    Обычно берётся готовый `tools/uknc/font.hex`: он в репозитории, поэтому
    страница собирается на чистой копии, без эмулятора. Снимок экрана машины
    старше файла — из него шрифт пересобирается, и файл переписывается.
    """
    if FONT_SHOT.exists():
        text = font_from_shot()
        if not FONT_HEX.exists() or FONT_HEX.read_text().strip() != text:
            FONT_HEX.write_text(text + "\n")
        return text
    if FONT_HEX.exists():
        return FONT_HEX.read_text().strip()
    raise SystemExit(
        f"нет ни {FONT_HEX}, ни снимка шрифта {FONT_SHOT}: снимите его "
        f"эмулятором (tools/uknc/README.md) или верните файл из репозитория"
    )


def font_from_shot():
    sys.path.insert(0, str(ROOT / "tools" / "uknc"))
    import screen_text as st

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


def build_stamp():
    """Метка сборки для отчёта об ошибке: по ней видно, какую страницу смотрел человек."""
    date = datetime.date.today().isoformat()
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "describe", "--always", "--dirty", "--abbrev=8"],
            capture_output=True, text=True, timeout=10,
        )
        commit = out.stdout.strip() or "без git"
    except (OSError, subprocess.SubprocessError):
        commit = "без git"
    return f"{date} {commit}"


def main():
    for name in ("TETRIS.BAS", "TETRISC.BAS"):
        if not (ROOT / "src" / name).exists():
            raise SystemExit(f"нет src/{name}")
    page = TEMPLATE.read_text()
    page = page.replace("@@PROG_DIFF@@", (ROOT / "src" / "TETRIS.BAS").read_text().rstrip())
    page = page.replace("@@PROG_CLASSIC@@", (ROOT / "src" / "TETRISC.BAS").read_text().rstrip())
    page = page.replace("@@FONT@@", font_hex())
    page = page.replace("@@BUILD@@", build_stamp())
    OUT.write_text(page)

    # Разделение простое: <title>, <link> и <style> — это голова, остальное тело.
    head_end = page.index("</style>") + len("</style>")
    site = SKELETON.format(head=page[:head_end] + "\n", body=page[head_end:].lstrip("\n"))
    SITE.parent.mkdir(parents=True, exist_ok=True)
    SITE.write_text(site, encoding="utf-8")
    print(f"{OUT} — {len(page) // 1024} КБ (артефакт)")
    print(f"{SITE} — {len(site) // 1024} КБ (самостоятельная страница)")


if __name__ == "__main__":
    main()
