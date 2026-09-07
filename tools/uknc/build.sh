#!/bin/sh
# Собирает безголовый УКНЦ: ядро эмулятора из ukncbtl-wasm плюс наш драйвер.
#
# Исходники ядра не копируются в репозиторий: они под LGPL и живут у автора.
# Скрипт забирает их в build/ и патчит две вещи, которые есть только у
# emscripten-сборки: обратный слэш в include и макрос EMSCRIPTEN_KEEPALIVE.
set -eu

root=$(cd "$(dirname "$0")/../.." && pwd)
build="$root/build/uknc"
src="$build/ukncbtl-wasm"

mkdir -p "$build"

if [ ! -d "$src" ]; then
    echo "беру ядро эмулятора"
    git clone --depth 1 -q https://github.com/nzeemin/ukncbtl-wasm.git "$src"
fi

# Крючок на чтение памяти: им ищется таблица знакогенератора — какие адреса
# машина читает, когда печатает знак. Больше он ни на что не влияет.
if [ ! -f "$build/Memory.cpp" ] || [ "$src/emubase/Memory.cpp" -nt "$build/Memory.cpp" ]; then
    sed -e 's|^uint16_t CMemoryController::GetWord(uint16_t address, bool okHaltMode, bool okExec)$|void (*g_readHook)(const void*, uint16_t, int) = 0;\nuint16_t CMemoryController::GetWord(uint16_t address, bool okHaltMode, bool okExec)|' \
        -e 's|^    int addrtype = TranslateAddress(address, okHaltMode, okExec, \&offset);$|    int addrtype = TranslateAddress(address, okHaltMode, okExec, \&offset);\n    if (g_readHook) g_readHook(this, address, addrtype);|' \
        -e 's|^uint8_t CMemoryController::GetByte(uint16_t address, bool okHaltMode)$|uint8_t CMemoryController::GetByte(uint16_t address, bool okHaltMode)\n{ if (g_readHook) g_readHook(this, address, -1); return GetByteInner(address, okHaltMode); }\nuint8_t CMemoryController::GetByteInner(uint16_t address, bool okHaltMode)|' \
        "$src/emubase/Memory.cpp" > "$build/Memory.cpp"
    # правленая копия лежит рядом с исходниками ядра, чтобы её include нашёл соседей
    cp "$build/Memory.cpp" "$src/emubase/Memory-hooked.cpp"
fi

if [ ! -f "$build/Emulator.cpp" ] || [ "$src/Emulator.cpp" -nt "$build/Emulator.cpp" ]; then
    echo "правлю ядро под обычный компилятор"
    sed -e 's|emubase\\Emubase.h|emubase/Emubase.h|' \
        -e 's|#include <emscripten/emscripten.h>|#define EMSCRIPTEN_KEEPALIVE|' \
        -e 's|^int main()|int emulator_unused_main()|' \
        "$src/Emulator.cpp" > "$build/Emulator.cpp"
fi

echo "собираю"
cd "$build"
g++ -std=c++11 -O2 -w -I"$src" -o uknc_run \
    "$root/tools/uknc/headless.cpp" \
    Emulator.cpp \
    "$src/emubase/Board.cpp" \
    "$src/emubase/Memory-hooked.cpp" \
    "$src/emubase/Processor.cpp" \
    "$src/emubase/Floppy.cpp" \
    "$src/emubase/Hard.cpp" \
    "$src/emubase/Disasm.cpp" \
    "$src/miniz/zip.c"

echo "готово: $build/uknc_run"
