#!/usr/bin/env python3
"""Отдаёт каталог build/ по http с разрешением на межсайтовый доступ.

Браузерная сборка эмулятора качает образы дисков средствами JavaScript, а
значит упирается в правила межсайтовых запросов (CORS): страница на
nzeemin.github.io не возьмёт файл с локального сервера, если тот не разрешил
это заголовком. Штатный `python3 -m http.server` заголовок не ставит, поэтому
здесь стоит его тонкая надстройка.

    emulator/serve-disk.py [порт]

Печатает готовую ссылку на онлайн-эмулятор с подключённым образом.
"""

import http.server
import pathlib
import sys
import urllib.parse

ONLINE = "https://nzeemin.github.io/ukncbtl-online.html"
ROOT = pathlib.Path(__file__).resolve().parent.parent / "build"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    if not ROOT.is_dir():
        raise SystemExit(f"нет каталога {ROOT}: сначала соберите артефакт")
    disks = sorted(p.name for p in ROOT.iterdir() if p.suffix in (".dsk", ".rtd", ".zip"))
    base = f"http://localhost:{port}/"
    print(f"каталог: {ROOT}")
    print(f"сервер:  {base}")
    if disks:
        link = urllib.parse.quote(base + disks[0], safe=":/")
        print(f"ссылка:  {ONLINE}?disk0={link}&run=1")
    else:
        print("образов дисков в каталоге нет — положите .dsk и перезапустите")
    print("остановить: Ctrl+C", flush=True)
    with http.server.ThreadingHTTPServer(("", port), Handler) as srv:
        srv.serve_forever()


if __name__ == "__main__":
    main()
