"""Интерпретатор подмножества УКНЦ-Бейсика — стенд для TETRIS.BAS без машины.

Диалект — кассетный Вильнюс-Бейсик 1988.09.28 из картриджа ПЗУ, тот самый, что
крутится в эмуляторе. Его свойства сняты опытом на живой машине
(tools/uknc/headless.cpp, снимки в docs/img/), и интерпретатор намеренно
строг ровно там же, где строга она:

* **один оператор в строке** — двоеточие как разделитель эта система не знает
  (Ошибка 2), поэтому `A=1 : B=2` здесь тоже ошибка;
* **значимы две первые буквы имени** — `SCORE` и `SCREEN` для машины одно и то
  же, и стенд запоминает каждое имя, которое пришлось обрезать;
* **графики нет вовсе** — LINE и PSET отвечают Ошибкой 5, поэтому их здесь
  просто не существует;
* экран текстовый, 64x24, `LOCATE <столбец>,<строка>` считает от нуля и
  ругается на выход за 63 и 23;
* `RND` требует аргумента.

Экран — сетка символов с цветом. Каждый вывод запоминается в журнале, чтобы
тест проверял не картинку, а какие именно клетки поля изменились.
"""

import math
import random
import re

KEYWORDS = {
    "REM", "LET", "IF", "THEN", "ELSE", "GOTO", "GOSUB", "RETURN", "FOR", "TO",
    "STEP", "NEXT", "READ", "DATA", "RESTORE", "DIM", "END", "STOP", "PRINT",
    "COLOR", "CLS", "LOCATE", "BEEP", "ON", "AND", "OR", "NOT",
}

FUNCTIONS = {"INT", "ABS", "RND", "SGN", "ASC", "LEN", "SQR", "CHR", "STRING"}

SCREEN_COLS = 64
SCREEN_ROWS = 24

TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<num>\d+\.\d*|\.\d+|\d+)
  | (?P<str>"[^"]*")
  | (?P<name>[A-Z][A-Z0-9]*[%!#$]?)
  | (?P<op><>|<=|>=|[-+*/^=<>(),:;@$])
    """,
    re.VERBOSE,
)


class BasicError(Exception):
    pass


class Token:
    __slots__ = ("kind", "text", "value")

    def __init__(self, kind, text, value=None):
        self.kind = kind
        self.text = text
        self.value = value

    def __repr__(self):
        return f"<{self.kind}:{self.text}>"


def tokenize(text):
    tokens = []
    pos = 0
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise BasicError(f"не разобран символ {text[pos]!r} в {text!r}")
        pos = m.end()
        if m.lastgroup == "ws":
            continue
        if m.lastgroup == "num":
            raw = m.group()
            value = float(raw) if "." in raw else int(raw)
            tokens.append(Token("num", raw, value))
        elif m.lastgroup == "str":
            tokens.append(Token("str", m.group(), m.group()[1:-1]))
        elif m.lastgroup == "name":
            name = m.group()
            kind = "kw" if name in KEYWORDS else "name"
            tokens.append(Token(kind, name))
        else:
            tokens.append(Token("op", m.group()))
        if tokens and tokens[-1].kind == "kw" and tokens[-1].text == "REM":
            tokens[-1] = Token("kw", "REM")
            break
    return tokens


class Line:
    __slots__ = ("number", "tokens", "source")

    def __init__(self, number, tokens, source):
        self.number = number
        self.tokens = tokens
        self.source = source


class Screen:
    """Текстовый экран 64x24: символ и цвет в каждой клетке плюс журнал вывода."""

    def __init__(self):
        self.fg = 7
        self.bg = 0
        self.col = 0
        self.row = 0
        self.cells = [[(" ", 7) for _ in range(SCREEN_COLS)] for _ in range(SCREEN_ROWS)]
        self.ops = []
        self.cls_count = 0
        self.scrolls = 0

    def cls(self):
        self.cls_count += 1
        self.cells = [[(" ", self.fg) for _ in range(SCREEN_COLS)] for _ in range(SCREEN_ROWS)]
        self.col = 0
        self.row = 0
        self.ops.append(("cls",))

    def locate(self, col, row):
        if not 0 <= col < SCREEN_COLS:
            raise BasicError(f"LOCATE: столбец {col} вне 0..{SCREEN_COLS - 1}")
        if not 0 <= row < SCREEN_ROWS:
            raise BasicError(f"LOCATE: строка {row} вне 0..{SCREEN_ROWS - 1}")
        self.col = col
        self.row = row
        self.ops.append(("locate", col, row))

    def write(self, text):
        if text:
            self.ops.append(("print", self.col, self.row, text, self.fg))
        for ch in text:
            if self.col >= SCREEN_COLS:
                self.newline()
            self.cells[self.row][self.col] = (ch, self.fg)
            self.col += 1

    def newline(self):
        self.col = 0
        self.row += 1
        if self.row >= SCREEN_ROWS:
            self.scroll()

    def scroll(self):
        self.scrolls += 1
        self.cells.pop(0)
        self.cells.append([(" ", self.fg) for _ in range(SCREEN_COLS)])
        self.row = SCREEN_ROWS - 1
        self.ops.append(("scroll",))

    def char_at(self, col, row):
        return self.cells[row][col][0]

    def color_at(self, col, row):
        return self.cells[row][col][1]

    def text_at(self, col, row, length):
        return "".join(self.cells[row][col + i][0] for i in range(length))

    def dump(self):
        return "\n".join("".join(c for c, _ in row).rstrip() for row in self.cells)


class Interpreter:
    def __init__(self, source, seed=1234, strict_names=True):
        self.lines = []
        self.index = {}
        self.strict_names = strict_names
        self.name_warnings = set()
        self._load(source)
        self.vars = {}
        self.arrays = {}
        self.screen = Screen()
        self.keys = []
        self.data = []
        self.data_pos = 0
        self.data_line_index = {}
        self._collect_data()
        self.rng = random.Random(seed)
        self.call_stack = []
        self.for_stack = []
        self.output = []
        self.steps = 0
        self.beeps = 0
        self.finished = False
        self.stopped_at = None
        self.pc = (0, 0)

    # ---------------------------------------------------------------- загрузка

    def _load(self, source):
        for raw in source.splitlines():
            stripped = raw.strip()
            if not stripped:
                continue
            m = re.match(r"(\d+)\s?(.*)", stripped)
            if not m:
                raise BasicError(f"строка без номера: {raw!r}")
            number = int(m.group(1))
            body = m.group(2)
            if len(raw) > 255:
                raise BasicError(f"строка {number} длиннее 255 символов")
            tokens = tokenize(body)
            for t in tokens:
                if t.kind == "op" and t.text == ":":
                    raise BasicError(
                        f"строка {number}: двоеточие — кассетный БЕЙСИК не знает "
                        f"разделителя операторов, нужен один оператор в строке"
                    )
            if number in self.index:
                raise BasicError(f"повтор номера строки {number}")
            self.index[number] = len(self.lines)
            self.lines.append(Line(number, tokens, body))
        if not self.lines:
            raise BasicError("пустая программа")

    def _collect_data(self):
        for li, line in enumerate(self.lines):
            toks = line.tokens
            if not toks or toks[0].text != "DATA":
                continue
            self.data_line_index[line.number] = len(self.data)
            i = 1
            while i < len(toks):
                t = toks[i]
                if t.kind == "op" and t.text == ",":
                    i += 1
                    continue
                if t.kind == "op" and t.text == "-":
                    nxt = toks[i + 1]
                    self.data.append(-nxt.value)
                    i += 2
                    continue
                if t.kind == "num":
                    self.data.append(t.value)
                elif t.kind == "str":
                    self.data.append(t.value)
                else:
                    self.data.append(t.text)
                i += 1

    # --------------------------------------------------------------- переменные

    def canon(self, name):
        suffix = name[-1] if name[-1] in "%!#$" else ""
        base = name[:-1] if suffix else name
        if len(base) > 2:
            if self.strict_names and name not in self.name_warnings:
                self.name_warnings.add(name)
            base = base[:2]
        return base + suffix

    def get_var(self, name):
        key = self.canon(name)
        if key in self.vars:
            return self.vars[key]
        return "" if key.endswith("$") else 0

    def set_var(self, name, value):
        key = self.canon(name)
        if key.endswith("%"):
            value = int(round(value))
            if not -32768 <= value <= 32767:
                raise BasicError(f"переполнение целого в {name}: {value}")
        elif not key.endswith("$"):
            value = float(value)
        self.vars[key] = value

    def dim(self, name, sizes):
        key = self.canon(name)
        total = 1
        for s in sizes:
            total *= s + 1
        self.arrays[key] = {"dims": sizes, "data": [0] * total}

    def _array(self, name):
        key = self.canon(name)
        if key not in self.arrays:
            self.dim(name, [10] * 1)
        return self.arrays[key]

    def _offset(self, arr, idx, name):
        dims = arr["dims"]
        if len(idx) != len(dims):
            raise BasicError(f"{name}: ожидалось {len(dims)} индексов, дано {len(idx)}")
        off = 0
        for i, d in zip(idx, dims):
            if i < 0 or i > d:
                raise BasicError(f"{name}: индекс {i} вне 0..{d}")
            off = off * (d + 1) + i
        return off

    def get_array(self, name, idx):
        arr = self._array(name)
        return arr["data"][self._offset(arr, idx, name)]

    def set_array(self, name, idx, value):
        arr = self._array(name)
        key = self.canon(name)
        if key.endswith("%"):
            value = int(round(value))
        arr["data"][self._offset(arr, idx, name)] = value

    # ---------------------------------------------------------------- выражения

    def eval_expr(self, toks, i):
        return self._or(toks, i)

    def _or(self, toks, i):
        val, i = self._and(toks, i)
        while i < len(toks) and toks[i].text == "OR":
            rhs, i = self._and(toks, i + 1)
            val = -1 if (val or rhs) else 0
        return val, i

    def _and(self, toks, i):
        val, i = self._not(toks, i)
        while i < len(toks) and toks[i].text == "AND":
            rhs, i = self._not(toks, i + 1)
            val = -1 if (val and rhs) else 0
        return val, i

    def _not(self, toks, i):
        if i < len(toks) and toks[i].text == "NOT":
            val, i = self._not(toks, i + 1)
            return (0 if val else -1), i
        return self._rel(toks, i)

    def _rel(self, toks, i):
        val, i = self._add(toks, i)
        while i < len(toks) and toks[i].kind == "op" and toks[i].text in ("=", "<>", "<", ">", "<=", ">="):
            op = toks[i].text
            rhs, i = self._add(toks, i + 1)
            if op == "=":
                res = val == rhs
            elif op == "<>":
                res = val != rhs
            elif op == "<":
                res = val < rhs
            elif op == ">":
                res = val > rhs
            elif op == "<=":
                res = val <= rhs
            else:
                res = val >= rhs
            val = -1 if res else 0
        return val, i

    def _add(self, toks, i):
        val, i = self._mul(toks, i)
        while i < len(toks) and toks[i].kind == "op" and toks[i].text in ("+", "-"):
            op = toks[i].text
            rhs, i = self._mul(toks, i + 1)
            val = val + rhs if op == "+" else val - rhs
        return val, i

    def _mul(self, toks, i):
        val, i = self._unary(toks, i)
        while i < len(toks) and toks[i].kind == "op" and toks[i].text in ("*", "/"):
            op = toks[i].text
            rhs, i = self._unary(toks, i + 1)
            if op == "*":
                val = val * rhs
            else:
                if rhs == 0:
                    raise BasicError("деление на ноль")
                val = val / rhs
        return val, i

    def _unary(self, toks, i):
        if i < len(toks) and toks[i].kind == "op" and toks[i].text in ("-", "+"):
            op = toks[i].text
            val, i = self._unary(toks, i + 1)
            return (-val if op == "-" else val), i
        return self._power(toks, i)

    def _power(self, toks, i):
        val, i = self._atom(toks, i)
        while i < len(toks) and toks[i].text == "^":
            rhs, i = self._atom(toks, i + 1)
            val = val ** rhs
        return val, i

    def _atom(self, toks, i):
        if i >= len(toks):
            raise BasicError("выражение оборвано")
        t = toks[i]
        if t.kind == "num":
            return t.value, i + 1
        if t.kind == "str":
            return t.value, i + 1
        if t.kind == "op" and t.text == "(":
            val, i = self.eval_expr(toks, i + 1)
            if toks[i].text != ")":
                raise BasicError("ожидалась )")
            return val, i + 1
        if t.kind == "name":
            name = t.text
            base = name[:-1] if name[-1] in "%!#$" else name
            if base == "INKEY" and name.endswith("$"):
                return (self.keys.pop(0) if self.keys else ""), i + 1
            if base in FUNCTIONS:
                return self._call_function(base, toks, i + 1)
            if i + 1 < len(toks) and toks[i + 1].text == "(":
                idx, j = self._index_list(toks, i + 1)
                return self.get_array(name, idx), j
            return self.get_var(name), i + 1
        raise BasicError(f"неожиданный токен {t.text!r}")

    def _index_list(self, toks, i):
        assert toks[i].text == "("
        i += 1
        idx = []
        while True:
            val, i = self.eval_expr(toks, i)
            idx.append(int(val))
            if toks[i].text == ",":
                i += 1
                continue
            if toks[i].text == ")":
                return idx, i + 1
            raise BasicError("ожидалась , или ) в индексе")

    def _call_function(self, base, toks, i):
        args = []
        if i < len(toks) and toks[i].text == "(":
            args, i = self._index_list_raw(toks, i)
        if base == "RND":
            if not args:
                raise BasicError("RND без аргумента — эта система требует RND(X)")
            return self.rng.random(), i
        if base == "INT":
            return math.floor(args[0]), i
        if base == "ABS":
            return abs(args[0]), i
        if base == "SGN":
            return (args[0] > 0) - (args[0] < 0), i
        if base == "ASC":
            if not args or args[0] == "":
                raise BasicError("ASC от пустой строки")
            return ord(args[0][0]), i
        if base == "LEN":
            return len(args[0]), i
        if base == "SQR":
            return math.sqrt(args[0]), i
        if base == "SIN":
            return math.sin(args[0]), i
        if base == "COS":
            return math.cos(args[0]), i
        if base == "CHR":
            return chr(int(args[0])), i
        if base == "STRING":
            return str(args[1]) * int(args[0]), i
        raise BasicError(f"нет функции {base}")

    def _index_list_raw(self, toks, i):
        assert toks[i].text == "("
        i += 1
        args = []
        while True:
            val, i = self.eval_expr(toks, i)
            args.append(val)
            if toks[i].text == ",":
                i += 1
                continue
            if toks[i].text == ")":
                return args, i + 1
            raise BasicError("ожидалась , или ) в аргументах")

    # ---------------------------------------------------------------- выполнение

    def resolve(self, number):
        """Индекс строки с этим номером или ближайшей следующей.

        Сжатый исходник теряет строки-комментарии, поэтому стенд обращается к
        разделу по его номеру, а попадает в первую уцелевшую строку раздела.
        """
        if number in self.index:
            return self.index[number]
        for li, line in enumerate(self.lines):
            if line.number >= number:
                return li
        raise BasicError(f"нет строки {number} и следующих за ней")

    def run(self, start_line=None, max_steps=20_000_000, stop_at=None):
        """Выполнять с указанной строки; остановиться, дойдя до строки из stop_at."""
        li = 0 if start_line is None else self.resolve(start_line)
        self.pc = (li, 0)
        self.stopped_at = None
        marks = {self.lines[self.resolve(n)].number for n in (stop_at or ())}
        self._execute(max_steps, None, marks)

    def call(self, line_number, max_steps=5_000_000):
        """Вызвать подпрограмму как GOSUB и вернуться, когда она сделает RETURN."""
        depth = len(self.call_stack)
        self.call_stack.append(None)
        self.pc = (self.resolve(line_number), 0)
        self._execute(max_steps, depth, None)

    def _execute(self, max_steps, stop_depth, stop_at=None):
        stop_at = set(stop_at or ())
        steps = 0
        while True:
            steps += 1
            self.steps += 1
            if steps > max_steps:
                raise BasicError(f"превышен лимит шагов ({max_steps})")
            li, ti = self.pc
            if li >= len(self.lines):
                self.finished = True
                return
            toks = self.lines[li].tokens
            if ti == 0 and self.lines[li].number in stop_at:
                self.stopped_at = self.lines[li].number
                return
            if ti >= len(toks):
                self.pc = (li + 1, 0)
                continue
            try:
                nxt = self._exec_statement(toks, ti, li)
            except BasicError as exc:
                raise BasicError(f"строка {self.lines[li].number}: {exc}") from None
            if nxt == "END":
                self.finished = True
                return
            if nxt == "RETURNED" and stop_depth is not None and len(self.call_stack) == stop_depth:
                return

    def _skip_separator(self, toks, i, li):
        while i < len(toks) and toks[i].text in (":", ";"):
            i += 1
        if i >= len(toks):
            self.pc = (li + 1, 0)
        else:
            self.pc = (li, i)

    def _exec_statement(self, toks, i, li):
        t = toks[i]
        word = t.text if t.kind == "kw" else None

        if word == "REM" or word == "DATA":
            self.pc = (li + 1, 0)
            return None
        if word == "END" or word == "STOP":
            return "END"
        if word == "LET":
            return self._assign(toks, i + 1, li)
        if word == "GOTO":
            target, i = self.eval_expr(toks, i + 1)
            self.pc = (self.index[int(target)], 0)
            return None
        if word == "GOSUB":
            target, j = self.eval_expr(toks, i + 1)
            ret = self._after(toks, j, li)
            self.call_stack.append(ret)
            self.pc = (self.index[int(target)], 0)
            return None
        if word == "RETURN":
            if not self.call_stack:
                raise BasicError("RETURN без GOSUB")
            ret = self.call_stack.pop()
            if ret is None:
                self.pc = (len(self.lines), 0)
                return "RETURNED"
            self.pc = ret
            return "RETURNED"
        if word == "ON":
            return self._on(toks, i + 1, li)
        if word == "IF":
            return self._if(toks, i + 1, li)
        if word == "FOR":
            return self._for(toks, i + 1, li)
        if word == "NEXT":
            return self._next(toks, i + 1, li)
        if word == "DIM":
            return self._dim(toks, i + 1, li)
        if word == "READ":
            return self._read(toks, i + 1, li)
        if word == "RESTORE":
            return self._restore(toks, i + 1, li)
        if word == "PRINT":
            return self._print(toks, i + 1, li)
        if word == "COLOR":
            return self._color(toks, i + 1, li)
        if word == "CLS":
            self.screen.cls()
            self._skip_separator(toks, i + 1, li)
            return None
        if word == "BEEP":
            self.beeps += 1
            self._skip_separator(toks, i + 1, li)
            return None
        if word == "LOCATE":
            return self._locate(toks, i + 1, li)
        if t.kind == "name":
            return self._assign(toks, i, li)
        raise BasicError(f"неизвестный оператор {t.text!r}")

    def _after(self, toks, i, li):
        while i < len(toks) and toks[i].text in (":", ";"):
            i += 1
        if i >= len(toks):
            return (li + 1, 0)
        return (li, i)

    def _assign(self, toks, i, li):
        name = toks[i].text
        if toks[i].kind != "name":
            raise BasicError(f"слева от = ожидалось имя, а не {name!r}")
        if i + 1 < len(toks) and toks[i + 1].text == "(":
            idx, j = self._index_list(toks, i + 1)
            if toks[j].text != "=":
                raise BasicError("ожидалось = в присваивании")
            val, j = self.eval_expr(toks, j + 1)
            self.set_array(name, idx, val)
        else:
            j = i + 1
            if toks[j].text != "=":
                raise BasicError("ожидалось = в присваивании")
            val, j = self.eval_expr(toks, j + 1)
            self.set_var(name, val)
        self._skip_separator(toks, j, li)
        return None

    def _if(self, toks, i, li):
        cond, j = self.eval_expr(toks, i)
        if toks[j].text != "THEN":
            raise BasicError("ожидалось THEN")
        j += 1
        else_at = self._find_else(toks, j)
        if cond:
            if toks[j].kind == "num":
                self.pc = (self.index[int(toks[j].value)], 0)
                return None
            self.pc = (li, j)
            return None
        if else_at is None:
            self.pc = (li + 1, 0)
            return None
        k = else_at + 1
        if toks[k].kind == "num":
            self.pc = (self.index[int(toks[k].value)], 0)
            return None
        self.pc = (li, k)
        return None

    def _find_else(self, toks, i):
        depth = 0
        while i < len(toks):
            text = toks[i].text
            if text == "(":
                depth += 1
            elif text == ")":
                depth -= 1
            elif text == "ELSE" and depth == 0:
                return i
            i += 1
        return None

    def _on(self, toks, i, li):
        val, j = self.eval_expr(toks, i)
        kind = toks[j].text
        if kind not in ("GOTO", "GOSUB"):
            raise BasicError("после ON ожидалось GOTO или GOSUB")
        j += 1
        targets = []
        while True:
            targets.append(int(toks[j].value))
            j += 1
            if j < len(toks) and toks[j].text == ",":
                j += 1
                continue
            break
        n = int(val)
        after = self._after(toks, j, li)
        if n < 1 or n > len(targets):
            self.pc = after
            return None
        if kind == "GOSUB":
            self.call_stack.append(after)
        self.pc = (self.index[targets[n - 1]], 0)
        return None

    def _for(self, toks, i, li):
        name = toks[i].text
        if toks[i + 1].text != "=":
            raise BasicError("ожидалось = в FOR")
        start, j = self.eval_expr(toks, i + 2)
        if toks[j].text != "TO":
            raise BasicError("ожидалось TO")
        limit, j = self.eval_expr(toks, j + 1)
        step = 1
        if j < len(toks) and toks[j].text == "STEP":
            step, j = self.eval_expr(toks, j + 1)
        self.set_var(name, start)
        body = self._after(toks, j, li)
        self.for_stack.append([self.canon(name), limit, step, body])
        if (step > 0 and start > limit) or (step < 0 and start < limit):
            self._skip_to_next(name, li)
            return None
        self.pc = body
        return None

    def _skip_to_next(self, name, li):
        """Тело цикла не выполняется ни разу: перейти за парный NEXT."""
        depth = 0
        start_li, start_ti = self.pc
        for idx in range(start_li, len(self.lines)):
            toks = self.lines[idx].tokens
            begin = start_ti if idx == start_li else 0
            for ti in range(begin, len(toks)):
                text = toks[ti].text
                if text == "FOR":
                    depth += 1
                elif text == "NEXT":
                    if depth == 0:
                        after = ti + 1
                        if after < len(toks) and toks[after].kind == "name":
                            after += 1
                        self.for_stack.pop()
                        self.pc = self._after(toks, after, idx)
                        return
                    depth -= 1
        raise BasicError(f"не найден NEXT для {name}")

    def _next(self, toks, i, li):
        names = []
        j = i
        while j < len(toks) and toks[j].kind == "name":
            names.append(toks[j].text)
            j += 1
            if j < len(toks) and toks[j].text == ",":
                j += 1
                continue
            break
        if not names:
            names = [None]
        for name in names:
            if not self.for_stack:
                raise BasicError("NEXT без FOR")
            frame = self.for_stack[-1]
            if name is not None and self.canon(name) != frame[0]:
                raise BasicError(f"NEXT {name} не соответствует FOR {frame[0]}")
            value = self.vars.get(frame[0], 0) + frame[2]
            self.vars[frame[0]] = int(round(value)) if frame[0].endswith("%") else value
            value = self.vars[frame[0]]
            if (frame[2] > 0 and value <= frame[1]) or (frame[2] < 0 and value >= frame[1]):
                self.pc = frame[3]
                return None
            self.for_stack.pop()
        self._skip_separator(toks, j, li)
        return None

    def _dim(self, toks, i, li):
        j = i
        while True:
            name = toks[j].text
            idx, j = self._index_list(toks, j + 1)
            self.dim(name, idx)
            if j < len(toks) and toks[j].text == ",":
                j += 1
                continue
            break
        self._skip_separator(toks, j, li)
        return None

    def _read(self, toks, i, li):
        j = i
        while True:
            name = toks[j].text
            if self.data_pos >= len(self.data):
                raise BasicError("данные кончились (READ без DATA)")
            value = self.data[self.data_pos]
            self.data_pos += 1
            if j + 1 < len(toks) and toks[j + 1].text == "(":
                idx, j = self._index_list(toks, j + 1)
                self.set_array(name, idx, value)
            else:
                self.set_var(name, value)
                j += 1
            if j < len(toks) and toks[j].text == ",":
                j += 1
                continue
            break
        self._skip_separator(toks, j, li)
        return None

    def _restore(self, toks, i, li):
        j = i
        if j < len(toks) and toks[j].kind == "num":
            self.data_pos = self.data_line_index[int(toks[j].value)]
            j += 1
        else:
            self.data_pos = 0
        self._skip_separator(toks, j, li)
        return None

    @staticmethod
    def format_value(value):
        if isinstance(value, str):
            return value
        if value == int(value):
            text = str(int(value))
        else:
            text = repr(round(value, 6))
        return (" " + text if value >= 0 else text) + " "

    def _print(self, toks, i, li):
        j = i
        newline = True
        printed = []
        while j < len(toks):
            if toks[j].text == ";":
                newline = False
                j += 1
                continue
            if toks[j].text == ",":
                pad = 14 - (self.screen.col % 14)
                self.screen.write(" " * pad)
                newline = False
                j += 1
                continue
            value, j = self.eval_expr(toks, j)
            text = self.format_value(value)
            printed.append(text)
            self.screen.write(text)
            newline = True
        if newline:
            self.screen.newline()
        self.output.append("".join(printed))
        self.pc = (li + 1, 0)
        return None

    def _color(self, toks, i, li):
        j = i
        args = []
        while j < len(toks) and toks[j].text != ":":
            if toks[j].text == ",":
                args.append(None)
                j += 1
                continue
            val, j = self.eval_expr(toks, j)
            args.append(val)
            if j < len(toks) and toks[j].text == ",":
                j += 1
        if args and args[0] is not None:
            color = int(args[0])
            if not 0 <= color <= 8:
                raise BasicError(f"COLOR {color} вне диапазона 0..8")
            self.screen.fg = color
        if len(args) > 1 and args[1] is not None:
            self.screen.bg = int(args[1])
        self._skip_separator(toks, j, li)
        return None

    def _locate(self, toks, i, li):
        col, j = self.eval_expr(toks, i)
        if toks[j].text != ",":
            raise BasicError("LOCATE ждёт два аргумента: столбец и строку")
        row, j = self.eval_expr(toks, j + 1)
        self.screen.locate(int(col), int(row))
        self._skip_separator(toks, j, li)
        return None
