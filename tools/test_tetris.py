#!/usr/bin/env python3
"""Приёмочные сценарии TETRIS.BAS, прогоняемые на интерпретаторе из uknc_basic.py.

Проверяется не картинка, а поведение: состояние массивов и **число клеток**,
которые игра нарисовала и стёрла. Ради этого игра держит счётчики DC% и EC%,
а стенд дополнительно разбирает журнал заливок и переводит его обратно в
координаты стакана — так видно не только сколько клеток изменилось, но и какие.

Запуск: python3 tools/test_tetris.py [-v]
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from uknc_basic import BasicError, Interpreter  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else ROOT / "src" / "TETRIS.BAS"
SOURCE = SRC.read_text()

TYPES = {1: "I", 2: "O", 3: "T", 4: "S", 5: "Z", 6: "J", 7: "L"}

LEFT, RIGHT, SOFT, ROTATE, HARD = 3000, 3010, 3020, 4000, 3040
GRAVITY, LOCK = 3100, 6000
SNAPSHOT, DIFF, AFTER_ACTION = 5000, 5100, 3400
SPAWN, NEXT_TYPE, SCORE_ROWS = 2000, 2100, 6200
CONFIG, TITLE, NEW_GAME, MAIN_LOOP, GAME_OVER = 100, 250, 300, 400, 500


# --------------------------------------------------------------------- стенд


def boot(seed=1):
    """Инициализация: конфигурация и таблицы, но без заставки и игры."""
    b = Interpreter(SOURCE, seed=seed)
    b.run(start_line=CONFIG, stop_at={TITLE})
    b.set_var("LV%", 0)
    b.set_var("FL%", 0)
    b.set_var("SR", 0)
    return b


def rots(b, t):
    return b.get_array("NR%", [t])


def shape(b, t, r, x=0, y=0):
    si = (t - 1) * 4 + r
    return {
        (x + b.get_array("SX%", [si, i]), y + b.get_array("TY%", [si, i]))
        for i in range(4)
    }


def piece_cells(b):
    return shape(b, b.get_var("CT%"), b.get_var("CR%"), b.get_var("CX%"), b.get_var("CY%"))


def place(b, t, r, x, y, draw=True):
    b.set_var("CT%", t)
    b.set_var("CR%", r)
    b.set_var("CX%", x)
    b.set_var("CY%", y)
    b.set_var("UP%", 0)
    b.set_var("GR%", 0)
    b.set_var("LR%", 0)
    b.set_var("GT%", 30)
    if draw:
        for i in range(4):
            b.set_array("AX%", [i], -9)
            b.set_array("AY%", [i], -9)
        b.call(DIFF)
    reset_counters(b)


def reset_counters(b):
    b.set_var("DC%", 0)
    b.set_var("EC%", 0)
    b.screen.ops.clear()


def counters(b):
    return b.get_var("DC%"), b.get_var("EC%")


def touched(b):
    """Журнал вывода, переведённый в клетки стакана: (x, y, занята ли)."""
    bx, by, cw = b.get_var("BX%"), b.get_var("BY%"), b.get_var("CW%")
    block, blank = b.get_var("CB$"), b.get_var("CE$")
    out = []
    for op in b.screen.ops:
        if op[0] != "print":
            continue
        _, col, row, text, _color = op
        if text not in (block, blank):
            continue
        if (col - bx) % cw:
            continue
        cx, cy = (col - bx) // cw, row - by
        if 0 <= cx < b.get_var("BW%") and 0 <= cy < b.get_var("BH%"):
            out.append((cx, cy, text == block))
    return out


def drawn_erased(b):
    cells = touched(b)
    return ({(x, y) for x, y, f in cells if f}, {(x, y) for x, y, f in cells if not f})


def board(b):
    w, h = b.get_var("BW%"), b.get_var("BH%")
    return [[b.get_array("BD%", [x, y]) for x in range(w)] for y in range(h)]


def set_board(b, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            b.set_array("BD%", [x, y], v)


def empty_rows(b):
    return [[0] * b.get_var("BW%") for _ in range(b.get_var("BH%"))]


# --------------------------------------------------------------------- тесты

TESTS = []


def test(name):
    def deco(fn):
        TESTS.append((name, fn))
        return fn

    return deco


@test("имена переменных умещаются в две значимые буквы")
def t_names():
    b = boot()
    assert not b.name_warnings, f"имена длиннее двух букв: {sorted(b.name_warnings)}"


@test("таблицы фигур прочитаны целиком и осмысленны")
def t_tables():
    b = boot()
    assert [rots(b, t) for t in range(1, 8)] == [2, 1, 4, 2, 2, 4, 4]
    for t in range(1, 8):
        for r in range(rots(b, t)):
            cells = shape(b, t, r)
            assert len(cells) == 4, f"{TYPES[t]} r{r}: {cells}"
            for x, y in cells:
                assert 0 <= x <= 3 and 0 <= y <= 3, f"{TYPES[t]} r{r} вне 4x4: {cells}"


@test("сдвиг влево и вправо трогает только изменившиеся клетки")
def t_shift_diff():
    for t in range(1, 8):
        for r in range(rots(b_probe := boot(), t)):
            for sub, dx in ((LEFT, -1), (RIGHT, 1)):
                b = boot()
                place(b, t, r, 4, 8)
                old = piece_cells(b)
                b.call(sub)
                assert b.get_var("CX%") == 4 + dx, f"{TYPES[t]} r{r} не сдвинулся"
                new = piece_cells(b)
                drawn, erased = drawn_erased(b)
                assert erased == old - new, f"{TYPES[t]} r{r}: стёрли {erased}, ждали {old - new}"
                assert drawn == new - old, f"{TYPES[t]} r{r}: нарисовали {drawn}, ждали {new - old}"
                assert counters(b) == (len(new - old), len(old - new))
    del b_probe


@test("горизонтальная I двигается вбок за одно стирание и одну отрисовку")
def t_i_shift_minimal():
    b = boot()
    place(b, 1, 0, 3, 8)
    b.call(RIGHT)
    assert counters(b) == (1, 1), counters(b)


@test("падение на одну клетку идёт разницей, а не перерисовкой")
def t_gravity_diff():
    for t in range(1, 8):
        b = boot()
        place(b, t, 0, 4, 6)
        old = piece_cells(b)
        b.call(GRAVITY)
        assert b.get_var("CY%") == 7
        new = piece_cells(b)
        drawn, erased = drawn_erased(b)
        assert erased == old - new and drawn == new - old, TYPES[t]


@test("все переходы ориентаций против часовой: фигура цела, разница минимальна")
def t_all_rotations():
    for t in range(1, 8):
        n = rots(boot(), t)
        for r in range(n):
            b = boot()
            place(b, t, r, 4, 8)
            old = piece_cells(b)
            b.call(ROTATE)
            new = piece_cells(b)
            expected_rot = (r - 1) % n
            assert b.get_var("CR%") == expected_rot, f"{TYPES[t]} r{r} -> r{b.get_var('CR%')}"
            assert len(new) == 4
            drawn, erased = drawn_erased(b)
            assert erased == old - new, f"{TYPES[t]} r{r}: стёрли лишнее"
            assert drawn == new - old, f"{TYPES[t]} r{r}: нарисовали лишнее"


@test("четыре поворота возвращают фигуру на то же место")
def t_rotation_cycle():
    for t in range(1, 8):
        b = boot()
        n = rots(b, t)
        place(b, t, 0, 4, 8)
        start = piece_cells(b)
        for _ in range(n):
            b.call(ROTATE)
        assert b.get_var("CR%") == 0, TYPES[t]
        assert piece_cells(b) == start, f"{TYPES[t]}: цикл поворотов сместил фигуру"


@test("сбалансированный поворот T: одна клетка стёрта, одна нарисована")
def t_balanced_t():
    b = boot()
    place(b, 3, 0, 4, 8)
    for r in range(4):
        reset_counters(b)
        b.call(ROTATE)
        assert counters(b) == (1, 1), f"T r{r}: {counters(b)}"


@test("O не меняет экран при повороте")
def t_o_rotation():
    b = boot()
    place(b, 2, 0, 4, 8)
    b.call(ROTATE)
    assert counters(b) == (0, 0)
    assert b.get_var("CR%") == 0


@test("S и Z в повороте сохраняют две клетки из четырёх")
def t_sz_overlap():
    for t in (4, 5):
        b = boot()
        place(b, t, 0, 4, 8)
        b.call(ROTATE)
        assert counters(b) == (2, 2), f"{TYPES[t]}: {counters(b)}"


@test("лежащая на полу I встаёт вертикально и остаётся прижатой к полу")
def t_i_floor_kick():
    b = boot()
    place(b, 1, 0, 3, 18)
    assert max(y for _, y in piece_cells(b)) == 19
    b.call(ROTATE)
    assert b.get_var("CR%") == 1, "I не повернулась у пола"
    cells = piece_cells(b)
    assert max(y for _, y in cells) == 19, f"нижняя клетка не у пола: {cells}"
    assert b.get_var("UP%") == 2, "подъём не записан"


@test("обратный поворот I возвращает её на пол, а не оставляет висеть")
def t_i_floor_return():
    b = boot()
    place(b, 1, 0, 3, 18)
    b.call(ROTATE)
    b.call(ROTATE)
    assert b.get_var("CR%") == 0
    assert max(y for _, y in piece_cells(b)) == 19, "I осталась поднятой"
    assert b.get_var("UP%") == 0


@test("чередование поворотов не поднимает фигуру вверх")
def t_anti_climb():
    b = boot()
    place(b, 1, 0, 3, 18)
    for _ in range(20):
        b.call(ROTATE)
        assert max(y for _, y in piece_cells(b)) == 19, "фигура вскарабкалась"


@test("ALLOW_ROTATION_CLIMB=1 оставляет подъём без компенсации")
def t_climb_option():
    b = boot()
    b.set_var("AC%", 1)
    place(b, 1, 0, 3, 18)
    b.call(ROTATE)
    b.call(ROTATE)
    assert max(y for _, y in piece_cells(b)) == 17, "экспериментальный режим не сработал"


@test("повороты у обеих стен либо удаются в пределах стакана, либо отменяются")
def t_wall_rotation():
    w = boot().get_var("BW%")
    for t in range(1, 8):
        for r in range(rots(boot(), t)):
            for x in (-1, 0, 1, w - 4, w - 3, w - 2):
                b = boot()
                place(b, t, r, x, 8)
                before = piece_cells(b)
                if any(cx < 0 or cx >= w for cx, _ in before):
                    continue
                b.call(ROTATE)
                cells = piece_cells(b)
                assert all(0 <= cx < w for cx, _ in cells), f"{TYPES[t]} r{r} x={x}: {cells}"
                if b.get_var("CR%") == r:
                    assert counters(b) == (0, 0), "отменённый поворот трогал экран"


@test("поворот среди блоков не выполняется и не трогает экран")
def t_rotation_blocked():
    b = boot()
    place(b, 3, 0, 4, 8)
    keep = piece_cells(b)
    rows = empty_rows(b)
    for y in range(20):
        for x in range(10):
            if (x, y) not in keep:
                rows[y][x] = 2
    set_board(b, rows)
    reset_counters(b)
    b.call(ROTATE)
    assert b.get_var("CR%") == 0, "поворот прошёл сквозь блоки"
    assert piece_cells(b) == keep
    assert counters(b) == (0, 0)


@test("hard drop опускает до упора, даёт очки и не фиксирует фигуру")
def t_hard_drop():
    b = boot()
    place(b, 3, 0, 4, 0)
    b.set_var("SR", 0)
    b.call(HARD)
    cells = piece_cells(b)
    assert max(y for _, y in cells) == 19, cells
    assert b.get_var("SR") == 2 * 17 * 1, b.get_var("SR")
    assert b.get_var("GR%") == 1, "hard drop не включил grounded"
    assert b.get_var("LK%") == b.get_array("LD%", [0]), "нет окна манёвра"
    assert b.get_var("FL%") == 0
    drawn, erased = drawn_erased(b)
    assert len(drawn) == 4 and len(erased) == 4, (drawn, erased)


@test("после hard drop ещё можно двигать и поворачивать")
def t_hard_drop_manoeuvre():
    b = boot()
    place(b, 1, 0, 3, 0)
    b.call(HARD)
    assert max(y for _, y in piece_cells(b)) == 19
    x0 = b.get_var("CX%")
    b.call(LEFT)
    assert b.get_var("CX%") == x0 - 1, "после hard drop не сдвинуть"
    b.call(ROTATE)
    assert b.get_var("CR%") == 1, "после hard drop не повернуть"
    assert max(y for _, y in piece_cells(b)) == 19


@test("продления lock delay ограничены MAX_LOCK_RESETS")
def t_lock_reset_limit():
    b = boot()
    place(b, 3, 0, 4, 0)
    b.call(HARD)
    limit = b.get_var("ML%")
    full = b.get_array("LD%", [0])
    grace = b.get_array("AG%", [0])
    for i in range(limit):
        b.set_var("LK%", 1)
        b.call(AFTER_ACTION)
        assert b.get_var("LK%") == full, f"продление {i} не дало полного интервала"
    for _ in range(5):
        b.set_var("LK%", 1)
        b.call(AFTER_ACTION)
        assert b.get_var("LR%") == limit, "счётчик продлений пробит"
        assert b.get_var("LK%") == grace, "после лимита выдан полный интервал"


@test("soft drop даёт очко за клетку с учётом уровня")
def t_soft_drop_score():
    b = boot()
    b.set_var("LV%", 3)
    place(b, 3, 0, 4, 0)
    b.set_var("SR", 0)
    b.call(SOFT)
    assert b.get_var("SR") == 4, b.get_var("SR")


@test("удаление 1-4 строк: доска, очки и число линий")
def t_line_clears():
    expected = {1: 100, 2: 300, 3: 600, 4: 1000}
    for n in range(1, 5):
        b = boot()
        rows = empty_rows(b)
        for y in range(20 - n, 20):
            for x in range(1, 10):
                rows[y][x] = 2
        set_board(b, rows)
        place(b, 1, 1, -1, 20 - n - (4 - n), draw=False)
        model = [row[:] for row in rows]
        for x, y in piece_cells(b):
            model[y][x] = 1
        model = [row for row in model if not all(row)]
        model = [[0] * 10 for _ in range(20 - len(model))] + model
        b.set_var("SR", 0)
        b.set_var("NT%", 2)
        b.call(LOCK)
        assert b.get_var("NC%") == n, f"{n}: посчитано {b.get_var('NC%')}"
        assert b.get_var("LN%") == n
        assert b.get_var("SR") == expected[n], f"{n}: очки {b.get_var('SC')}"
        assert board(b) == model, f"{n}: стакан после удаления разъехался"


@test("после удаления строк перерисованы только изменившиеся клетки")
def t_line_clear_redraw():
    b = boot()
    rows = empty_rows(b)
    for x in range(1, 10):
        rows[19][x] = 2
    rows[18][5] = 2
    set_board(b, rows)
    place(b, 1, 1, -1, 16, draw=False)
    b.set_var("NT%", 2)
    reset_counters(b)
    b.call(LOCK)
    after = board(b)
    assert after[19] == [1, 0, 0, 0, 0, 2, 0, 0, 0, 0], after[19]
    assert after[18] == [1] + [0] * 9 and after[16] == [0] * 10
    drawn, erased = drawn_erased(b)
    assert erased == {(x, 19) for x in list(range(1, 5)) + list(range(6, 10))} | {(5, 18), (0, 16)}, erased
    assert not drawn & {(x, y) for x in range(10) for y in range(16, 20)}, (
        "клетка перерисована там, где картинка не изменилась"
    )


@test("NEXT становится текущей, а превью обновляется только при спавне")
def t_next_and_spawn():
    b = boot()
    b.set_var("NT%", 5)
    ops_before = len(b.screen.ops)
    b.call(SPAWN)
    assert b.get_var("CT%") == 5, "NEXT не стала текущей"
    assert 1 <= b.get_var("NT%") <= 7
    assert len(b.screen.ops) > ops_before, "превью не перерисовано"
    assert b.get_var("FL%") == 0
    b.call(LEFT)
    ops_before = len(b.screen.ops)
    b.call(RIGHT)
    assert all(op[0] != "cls" for op in b.screen.ops[ops_before:])


@test("game over, когда новая фигура не помещается")
def t_game_over():
    b = boot()
    rows = empty_rows(b)
    for y in range(6):
        for x in range(10):
            rows[y][x] = 2
    set_board(b, rows)
    b.set_var("NT%", 3)
    b.call(SPAWN)
    assert b.get_var("FL%") == 1, "игра не заметила переполнения"


@test("уровень растёт каждые десять строк, а задержки убывают")
def t_levels():
    b = boot()
    b.set_var("LN%", 9)
    b.set_var("NC%", 1)
    b.call(SCORE_ROWS)
    assert b.get_var("LN%") == 10 and b.get_var("LV%") == 1
    delays = [b.get_array("GD%", [i]) for i in range(10)]
    assert delays == sorted(delays, reverse=True) and len(set(delays)) == 10, delays
    locks = [b.get_array("LD%", [i]) for i in range(10)]
    assert min(locks) >= 15, "на быстрых уровнях не остаётся окна для манёвра"
    graces = [b.get_array("AG%", [i]) for i in range(10)]
    assert all(g >= 10 for g in graces)


@test("очки за линии умножаются на уровень")
def t_line_score_level():
    b = boot()
    b.set_var("LV%", 4)
    b.set_var("NC%", 4)
    b.set_var("SR", 0)
    b.call(SCORE_ROWS)
    assert b.get_var("SR") == 1000 * 5, b.get_var("SR")


@test("генератор выдаёт все семь фигур без длинных серий")
def t_randomizer():
    b = boot(seed=7)
    seen = []
    for _ in range(700):
        b.call(NEXT_TYPE)
        seen.append(b.get_var("NT%"))
    counts = {t: seen.count(t) for t in range(1, 8)}
    assert set(counts) == set(range(1, 8)), counts
    assert min(counts.values()) > 50, counts
    run = best = 1
    for a, c in zip(seen, seen[1:]):
        run = run + 1 if a == c else 1
        best = max(best, run)
    assert best <= 5, f"серия из {best} одинаковых фигур"


@test("обычная игра не очищает экран и не перерисовывает стакан")
def t_no_cls():
    b = boot()
    place(b, 6, 0, 4, 4)
    cls_before = b.screen.cls_count
    for sub in (LEFT, RIGHT, ROTATE, SOFT, GRAVITY, HARD):
        b.call(sub)
    assert b.screen.cls_count == cls_before, "в игровом цикле сработал CLS"
    assert b.get_var("DC%") + b.get_var("EC%") < 40, "слишком много графики на шесть действий"


@test("главный цикл: фигура падает сама и доходит до фиксации")
def t_main_loop_gravity():
    b = Interpreter(SOURCE, seed=3)
    b.keys.append(" ")
    b.run(start_line=CONFIG, stop_at={MAIN_LOOP})
    settled = b.screen.cls_count
    b.run(start_line=MAIN_LOOP, stop_at={LOCK}, max_steps=2_000_000)
    assert b.stopped_at == LOCK, "фигура так и не зафиксировалась"
    assert max(y for _, y in piece_cells(b)) == 19, "зафиксировалась не у пола"
    assert b.screen.cls_count == settled, "в игровом цикле сработал CLS"


@test("главный цикл: клавиша выхода завершает игру")
def t_main_loop_quit():
    b = Interpreter(SOURCE, seed=3)
    b.keys.extend([" ", "q"])
    b.run(start_line=CONFIG, stop_at={NEW_GAME})
    b.run(start_line=NEW_GAME, stop_at={GAME_OVER}, max_steps=2_000_000)
    assert b.get_var("FL%") == 2


@test("случайная партия целиком доигрывается до game over без ошибок")
def t_playthrough():
    import random

    b = Interpreter(SOURCE, seed=11)
    rnd = random.Random(5)
    b.keys.append(" ")
    b.run(start_line=CONFIG, stop_at={MAIN_LOOP})
    b.keys.extend(rnd.choice("adws ") for _ in range(4000))
    b.run(start_line=MAIN_LOOP, stop_at={GAME_OVER}, max_steps=40_000_000)
    assert b.stopped_at == GAME_OVER and b.get_var("FL%") == 1, "партия не завершилась переполнением"
    assert b.get_var("DC%") > 1000 and b.get_var("EC%") > 1000
    assert abs(b.get_var("DC%") - b.get_var("EC%")) < b.get_var("DC%") * 0.1, (
        "нарисовано и стёрто разошлись: где-то остаются следы фигур"
    )
    assert b.screen.cls_count == 2, f"экран чистился {b.screen.cls_count} раз"


@test("заставка и HUD рисуются без ошибок исполнения")
def t_ui_smoke():
    b = Interpreter(SOURCE, seed=3)
    b.keys.append(" ")
    b.run(start_line=CONFIG, stop_at={MAIN_LOOP})
    assert b.get_var("CT%") != 0, "первая фигура не появилась"
    assert b.screen.ops, "экран пуст"


@test("клавиши: WASD, раскладка БК 7/9/8/5 и стрелки как ESC плюс буква")
def t_keys():
    b = boot()
    table = {b.get_array("KA%", [i]): b.get_array("KV%", [i]) for i in range(b.get_var("NK%"))}
    for code, action in ((65, 1), (68, 2), (83, 3), (87, 4), (32, 5), (80, 6), (81, 7)):
        assert table.get(code) == action, f"код {code}"
    for code, action in ((55, 1), (57, 2), (53, 3), (56, 4)):
        assert table.get(code) == action, f"раскладка БК: код {code}"
    # стрелки приходят двумя байтами: 27 и буква. Влево-вправо двигают,
    # вверх поворачивает, вниз сбрасывает фигуру целиком.
    for letter, action in (("A", 4), ("B", 5), ("C", 2), ("D", 1)):
        b.set_var("ES%", 0)
        b.keys.extend([chr(27), letter])
        b.call(1000)
        assert b.get_var("AK%") == 0 and b.get_var("ES%") == 1, "ESC не запомнен"
        b.call(1000)
        assert b.get_var("AK%") == action, f"стрелка ESC {letter}"
        assert b.get_var("ES%") == 0


@test("мигающий двойник: та же логика, но восемь клеток вместо двух")
def t_classic():
    classic = (ROOT / "src" / "TETRISC.BAS").read_text()
    generated = __import__("make_classic").make_classic(SOURCE)
    assert classic == generated, (
        "src/TETRISC.BAS разошёлся с генератором: пересоберите его "
        "командой python3 tools/make_classic.py > src/TETRISC.BAS"
    )
    b = Interpreter(classic, seed=1)
    b.run(start_line=CONFIG, stop_at={TITLE})
    b.set_var("LV%", 0)
    # горизонтальная I: у аккуратной версии 1 и 1, у мигающей 4 и 4
    place(b, 1, 0, 3, 8)
    b.call(RIGHT)
    assert counters(b) == (4, 4), f"мигающая версия должна трогать все клетки: {counters(b)}"
    # поворот T: у аккуратной версии 1 и 1
    place(b, 3, 0, 4, 8)
    b.call(ROTATE)
    assert counters(b) == (4, 4), counters(b)
    # но игровая логика та же: поворот против часовой стрелки
    assert b.get_var("CR%") == 3
    place(b, 2, 0, 4, 8)
    b.call(ROTATE)
    assert counters(b) == (0, 0), "O не вращается, значит и печатать нечего"


@test("вспомогательные программы KEYTEST и BENCH разбираются без ошибок")
def t_helpers():
    for name in ("KEYTEST.BAS", "BENCH.BAS"):
        Interpreter((ROOT / "src" / name).read_text())


# ------------------------------------------------------------------- запуск


def main():
    verbose = "-v" in sys.argv
    failed = 0
    for name, fn in TESTS:
        try:
            fn()
        except (AssertionError, BasicError) as exc:
            failed += 1
            print(f"[ПРОВАЛ] {name}\n         {exc}")
        else:
            if verbose:
                print(f"[ок]     {name}")
    total = len(TESTS)
    print(f"\n{total - failed} из {total} сценариев прошли")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
