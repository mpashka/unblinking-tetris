# Запуск под Linux

Три пути: от «работает прямо сейчас» до «настоящий УКНЦ в окне».

## 1. Безголовый эмулятор — то, чем проверялась игра

Собирается одним `g++`, ничего ставить не нужно:

```sh
tools/uknc/build.sh
cd build/uknc
python3 ../../tools/pack_bas.py ../../src/TETRIS.BAS > T.BAS
./uknc_run --cart romctr_basic.bin --script run3.txt
python3 ../../tools/uknc/screen_text.py t3.ppm    # экран как текст
```

Это ядро настоящего эмулятора УКНЦ без окна: сценарий вместо клавиатуры, снимок
вместо экрана. Им набрана программа, сняты коды клавиш и измерена скорость
машины. Устройство — [tools/uknc/README.md](../tools/uknc/README.md).

🚨 Нужны два чужих файла, которых нет в репозитории: ПЗУ машины `uknc_rom.bin`
(берётся автоматически вместе с ядром) и картридж `romctr_basic.bin` из
[релиза UKNCBTL 2023.1](https://github.com/nzeemin/ukncbtl/releases/tag/release-2023.1).

## 2. UKNCBTL-Qt — поиграть руками

[ukncbtl-qt](https://github.com/nzeemin/ukncbtl-qt) — единственная сборка с окном,
которая собирается под Linux.

```sh
sudo apt install build-essential qtbase5-dev qtmultimedia5-dev qt5-qmake
git clone --depth 1 https://github.com/nzeemin/ukncbtl-qt.git
cd ukncbtl-qt/QtUkncBtl
qmake && make -j$(nproc)
```

Дальше: подключить картридж (`Configuration > Cartridge 1`), в загрузочном меню
выбрать «2 — кассета ПЗУ», дождаться `Ok` и либо загрузить сохранённое состояние
(`build/tetris-uknc.uknc`, см. [README-web.md](README-web.md)), либо набрать
программу.

🚨 На этой машине Qt-сборка не собиралась и не запускалась: проверялась только
безголовая. Собирается rt11dsk из ukncbtl-utils — им кладут файл в образ RT-11,
если хочется грузить программу с диска.

## 3. Страница в браузере

`web/tetris-uknc.html` — Бейсик и тетрис без всякой установки,
см. [README-web.md](README-web.md).

## Управление

`A` `D` — вбок, `S` — вниз, `W` — поворот, пробел — сброс, `P` — пауза,
`Q` — выход. Раскладка БК-0010 `7` `9` `8` `5` работает тоже.
