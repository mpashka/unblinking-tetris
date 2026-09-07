#!/bin/sh
# Собирает безголовый БК-0010: ядро из bkbtl-wasm плюс наш драйвер.
# Нужен, чтобы посмотреть на эталонный тетрис БК своими глазами, а не по пересказам.
set -eu

root=$(cd "$(dirname "$0")/../.." && pwd)
build="$root/build/bk"
src="$build/bkbtl-wasm"

mkdir -p "$build"

if [ ! -d "$src" ]; then
    echo "беру ядро эмулятора БК"
    git clone --depth 1 -q https://github.com/nzeemin/bkbtl-wasm.git "$src"
fi

if [ ! -f "$build/Emulator.cpp" ] || [ "$src/Emulator.cpp" -nt "$build/Emulator.cpp" ]; then
    echo "правлю ядро под обычный компилятор"
    sed -e 's|emubase\\Emubase.h|emubase/Emubase.h|' \
        -e 's|#include <emscripten/emscripten.h>|#define EMSCRIPTEN_KEEPALIVE|' \
        -e 's|^int main()|int emulator_unused_main()|' \
        "$src/Emulator.cpp" > "$src/Emulator-native.cpp"
    cp "$src/Emulator-native.cpp" "$build/Emulator.cpp"
fi

cp -f "$src"/*.rom "$build/" 2>/dev/null || true

echo "собираю"
cd "$build"
g++ -std=c++11 -O2 -w -include cstdint -I"$src" -o bk_run \
    "$root/tools/bk/headless.cpp" \
    "$src/Emulator-native.cpp" \
    "$src/emubase/Board.cpp" \
    "$src/emubase/Processor.cpp" \
    "$src/emubase/Floppy.cpp" \
    "$src/emubase/Disasm.cpp" \
    "$src/emubase/SoundAY.cpp" 2>&1 | grep -v "^In file" | head -20

echo "готово: $build/bk_run"
