#!/bin/sh
# Собирает артефакт для эмулятора: сжимает исходник и кладёт его в образ диска.
#
#   emulator/make-disk.sh <образ.dsk>
#
# Образ должен уже существовать и быть размечен под RT-11: утилита rt11dsk
# умеет добавлять файл в готовый том, но не умеет создавать том с нуля.
# Берите тот же диск, с которого грузится БЕЙСИК-система, либо любой другой
# рабочий образ RT-11 и подключайте его вторым дисководом.
#
# rt11dsk собирается из ukncbtl-utils при первом запуске в build/rt11dsk.
set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
image=${1:-}
build="$root/build"
utils="$build/ukncbtl-utils"
rt11dsk="$build/rt11dsk"

if [ -z "$image" ]; then
    echo "укажите образ диска: emulator/make-disk.sh <образ.dsk>" >&2
    exit 2
fi
if [ ! -f "$image" ]; then
    echo "нет файла образа: $image" >&2
    exit 2
fi

mkdir -p "$build"

echo "сжимаю исходник"
python3 "$root/tools/pack_bas.py" "$root/src/TETRIS.BAS" > "$build/TETRIS.BAS"
python3 "$root/tools/test_tetris.py" "$build/TETRIS.BAS"

if [ ! -x "$rt11dsk" ]; then
    echo "собираю rt11dsk"
    if [ ! -d "$utils" ]; then
        git clone --depth 1 https://github.com/nzeemin/ukncbtl-utils.git "$utils"
    fi
    make -C "$utils/rt11dsk"
    cp "$utils/rt11dsk/rt11dsk" "$rt11dsk"
fi

echo "кладу TETRIS.BAS в $image"
cd "$build"
"$rt11dsk" d "$image" TETRIS.BAS >/dev/null 2>&1 || true
"$rt11dsk" a "$image" TETRIS.BAS
"$rt11dsk" l "$image" | grep -i tetris

cat <<'EOF'

Готово. Дальше в эмуляторе:
  1. подключить образ (Configuration > Floppy MZ0: или MZ1:);
  2. загрузить БЕЙСИК-систему;
  3. LOAD "MZ1:TETRIS.BAS"   (имя устройства проверить по приглашению системы);
  4. RUN.
EOF
