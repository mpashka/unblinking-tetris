#!/usr/bin/env python3
"""Сжимает исходник для ввода в машину: выкидывает комментарии и лишние пробелы.

Память БЕЙСИК-системы УКНЦ невелика (переполнение — ошибка 7), а набирать или
передавать четырнадцать килобайт комментариев незачем. Читаемый исходник —
`src/TETRIS.BAS`, в машину едет результат этой программы.

Строка-комментарий удаляется, только если на неё никто не прыгает: номера из
GOTO, GOSUB, THEN, ELSE, ON ... GOTO/GOSUB и RESTORE собираются заранее.
Строка, на которую ссылаются, остаётся, но от неё оставляется только `REM`.

    python3 tools/pack_bas.py src/TETRIS.BAS > build/TETRIS.BAS
"""

import re
import sys

JUMP_RE = re.compile(r"\b(?:GOTO|GOSUB|THEN|ELSE|RESTORE)\s+([\d,\s]+)")


def referenced_lines(lines):
    refs = set()
    for _, body in lines:
        for m in JUMP_RE.finditer(body):
            for part in m.group(1).split(","):
                part = part.strip()
                if part.isdigit():
                    refs.add(int(part))
    return refs


def parse(text):
    out = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        m = re.match(r"(\d+)\s?(.*)", raw)
        if not m:
            raise SystemExit(f"строка без номера: {raw!r}")
        out.append((int(m.group(1)), m.group(2)))
    return out


def is_comment(body):
    return body.strip().startswith("REM")


def squeeze(body):
    parts = re.split(r'("[^"]*")', body)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"\s*([:,=+\-*/()<>])\s*", r"\1", parts[i])
        parts[i] = re.sub(r"\s+", " ", parts[i])
    return "".join(parts).strip()


def pack(text):
    lines = parse(text)
    refs = referenced_lines(lines)
    packed = []
    for number, body in lines:
        if is_comment(body):
            if number not in refs:
                continue
            body = "REM"
        else:
            body = squeeze(body)
        line = f"{number} {body}"
        if len(line) > 255:
            raise SystemExit(f"строка {number} длиннее 255 символов после сжатия")
        packed.append(line)
    return "\n".join(packed) + "\n"


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    with open(sys.argv[1]) as fh:
        source = fh.read()
    sys.stdout.write(pack(source))


if __name__ == "__main__":
    main()
