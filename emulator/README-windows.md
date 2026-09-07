# Запуск под Windows

Эмулятор: [UKNCBTL](https://github.com/nzeemin/ukncbtl/releases) — родная
сборка под Windows, самый обжитой вариант. Qt-сборка тоже работает, но смысла
в ней под Windows нет.

🚨 Не проверялось: Windows-машины под рукой не было.

## Порядок

1. Скачать архив со страницы релизов и распаковать.
2. Запустить `UKNCBTL.exe`.
3. `Configuration > Floppy MZ0:` — выбрать образ диска с игрой.
4. В загрузочном меню УКНЦ — «1 — диск», `Enter`.
5. Дождаться приглашения БЕЙСИК-системы (`Ok`), набрать:

   ```
   LOAD "MZ0:TETRIS.BAS"
   RUN
   ```

## Как положить игру в образ

Под Windows проще всего собрать `rt11dsk` из
[ukncbtl-utils](https://github.com/nzeemin/ukncbtl-utils) (в репозитории есть
проект для Visual Studio) и выполнить:

```
python tools\pack_bas.py src\TETRIS.BAS > build\TETRIS.BAS
cd build
rt11dsk d образ.dsk TETRIS.BAS
rt11dsk a образ.dsk TETRIS.BAS
rt11dsk l образ.dsk
```

Обратите внимание: под Windows у `rt11dsk` признак ключа — `/`, а не `-`.

Тот же порядок под Linux и Mac делает один скрипт `emulator/make-disk.sh`.

## Клавиатура

`A`/`D` — влево-вправо, `S` — вниз на клетку, `W` — поворот, пробел —
мгновенный сброс, `P` — пауза, `Q` — выход. Плюс раскладка БК-0010:
`7`/`9`/`8`/`5`.

Стрелки пока не назначены: их коды в КОИ-7 надо сначала измерить
`src/KEYTEST.BAS` и вписать в таблицу клавиш (строка 10500 в `TETRIS.BAS`,
там для этого оставлены четыре строки `-1`). Результат — в матрицу в
[docs/TESTING.md](../docs/TESTING.md).
