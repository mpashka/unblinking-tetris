#!/bin/sh
# Отправить страницы из wiki/ в вики репозитория.
#
# Вики — отдельный git-репозиторий (`<репозиторий>.wiki.git`), и GitHub заводит его
# только после того, как первая страница создана руками в интерфейсе:
# https://github.com/mpashka/unblinking-tetris/wiki -> «Create the first page» -> Save.
# 🚨 Пока это не сделано, push отвечает «repository not found», и никакой токен не помогает —
# программного способа завести вики у GitHub нет.
#
# Дальше страницы живут в этом репозитории (каталог wiki/), а сюда только копируются:
# так они правятся вместе с кодом и не расходятся с ним.
set -e
root=$(cd "$(dirname "$0")/.." && pwd)
remote=${1:-git@github.com:mpashka/unblinking-tetris.wiki.git}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
git clone --quiet "$remote" "$work"
cp "$root"/wiki/*.md "$work"/
cd "$work"
if git diff --quiet && git diff --cached --quiet && [ -z "$(git status --porcelain)" ]; then
    echo "вики уже совпадает с wiki/"
    exit 0
fi
git add -A
git commit --quiet -m "${2:-Обновление страниц из репозитория}"
git push --quiet
echo "вики обновлена: $(git log --oneline -1)"
