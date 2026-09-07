// Проверяет разборщик Бейсика, встроенный в веб-страницу, без браузера.
//
// Страница собирается из шаблона, и её JavaScript легко разъезжается с
// питоновским стендом: тот же диалект, но другая реализация. Поэтому здесь
// прогоняются те же вещи, что и на стенде: таблицы, разница отрисовки,
// поворот T, отбой I у пола и целая партия до game over.
//
//   node tools/test_web.js

const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "web", "tetris-uknc.html"), "utf8");

// из страницы берём только интерпретатор: всё до пульта
const scriptMatch = html.match(/<script>\n"use strict";([\s\S]*?)\/\* ----+ пульт \*\//);
if (!scriptMatch) {
  console.error("не нашёлся интерпретатор в собранной странице");
  process.exit(1);
}
const source = scriptMatch[1] + "\nmodule.exports = { Basic, Screen, BasicError, tokenize, koi7 };";
const module_ = { exports: {} };
new Function("module", "exports", source)(module_, module_.exports);
const { Basic } = module_.exports;

const progDiff = html.match(/<script type="text\/plain" id="src-diff">([\s\S]*?)<\/script>/)[1].trim();
const progClassic = html.match(/<script type="text\/plain" id="src-classic">([\s\S]*?)<\/script>/)[1].trim();

let failed = 0;
function test(name, fn) {
  try {
    fn();
    console.log("[ок]     " + name);
  } catch (err) {
    failed++;
    console.log("[ПРОВАЛ] " + name + "\n         " + err.message);
  }
}
function assert(cond, msg) {
  if (!cond) throw new Error(msg || "не сошлось");
}

function boot(src) {
  const b = new Basic(src);
  b.start(100);
  const stopAt = b.resolve(250);
  for (let i = 0; i < 200000 && b.running; i++) {
    if (b.pc[0] === stopAt && b.pc[1] === 0) break;
    b.step();
  }
  b.setVar("LV%", 0);
  return b;
}

function shape(b, t, r, x, y) {
  const si = (t - 1) * 4 + r;
  const cells = [];
  for (let i = 0; i < 4; i++) {
    cells.push([x + b.getArray("SX%", [si, i]), y + b.getArray("TY%", [si, i])]);
  }
  return cells;
}

function place(b, t, r, x, y) {
  b.setVar("CT%", t); b.setVar("CR%", r); b.setVar("CX%", x); b.setVar("CY%", y);
  b.setVar("UP%", 0); b.setVar("GR%", 0); b.setVar("LR%", 0); b.setVar("GT%", 300);
  for (let i = 0; i < 4; i++) { b.setArray("AX%", [i], -9); b.setArray("AY%", [i], -9); }
  call(b, 5100);
  b.setVar("DC%", 0); b.setVar("EC%", 0);
}

function call(b, line) {
  const depth = b.callStack.length;
  b.callStack.push([b.lines.length, 0]);
  b.pc = [b.resolve(line), 0];
  b.running = true;
  let guard = 500000;
  while (b.running && guard-- > 0) {
    b.step();
    if (b.callStack.length === depth) break;
  }
  b.running = false;
  if (guard <= 0) throw new Error("подпрограмма " + line + " не вернулась");
}

test("страница несёт обе программы", () => {
  assert(progDiff.includes("TETRIS.BAS") || progDiff.includes("CELL DIFF"), "нет немигающей");
  assert(progClassic.includes("WIPED AND PRINTED AGAIN"), "нет мигающей");
});

test("таблицы фигур читаются", () => {
  const b = boot(progDiff);
  const rots = [];
  for (let t = 1; t <= 7; t++) rots.push(b.getArray("NR%", [t]));
  assert(JSON.stringify(rots) === JSON.stringify([2, 1, 4, 2, 2, 4, 4]), "ориентации: " + rots);
});

test("сдвиг горизонтальной I — одна клетка вместо восьми", () => {
  const b = boot(progDiff);
  place(b, 1, 0, 3, 8);
  call(b, 3010);
  assert(b.getVar("DC%") === 1 && b.getVar("EC%") === 1,
    "напечатано " + b.getVar("DC%") + ", стёрто " + b.getVar("EC%"));
});

test("сбалансированный поворот T — одна клетка", () => {
  const b = boot(progDiff);
  place(b, 3, 0, 4, 8);
  call(b, 4000);
  assert(b.getVar("DC%") === 1 && b.getVar("EC%") === 1,
    "напечатано " + b.getVar("DC%") + ", стёрто " + b.getVar("EC%"));
});

test("лежащая I встаёт у пола и возвращается на пол", () => {
  const b = boot(progDiff);
  place(b, 1, 0, 3, 18);
  call(b, 4000);
  assert(b.getVar("CR%") === 1, "I не повернулась");
  let bottom = Math.max(...shape(b, 1, 1, b.getVar("CX%"), b.getVar("CY%")).map(c => c[1]));
  assert(bottom === 19, "нижняя клетка не у пола: " + bottom);
  call(b, 4000);
  bottom = Math.max(...shape(b, 1, 0, b.getVar("CX%"), b.getVar("CY%")).map(c => c[1]));
  assert(b.getVar("CR%") === 0 && bottom === 19, "не вернулась на пол");
});

test("мигающая версия трогает все восемь клеток", () => {
  const b = boot(progClassic);
  place(b, 1, 0, 3, 8);
  call(b, 3010);
  assert(b.getVar("DC%") === 4 && b.getVar("EC%") === 4,
    "напечатано " + b.getVar("DC%") + ", стёрто " + b.getVar("EC%"));
});

test("партия идёт: стакан нарисован, фигура падает", () => {
  const b = new Basic(progDiff);
  b.keys.push(" ");
  b.start();
  let guard = 400000;
  while (b.running && guard-- > 0) b.step();
  const cells = b.screen.cells;
  const walls = [...cells].filter(c => c === 164).length;   // двойная вертикаль
  const floor = [...cells].filter(c => c === 186).length;   // двойная горизонталь
  // клетка фигуры — две половинки дорисованного квадрата, 128 и 129
  const left = [...cells].filter(c => c === 128).length;
  const right = [...cells].filter(c => c === 129).length;
  let text = "";
  for (let r = 0; r < 24; r++) {
    for (let c = 0; c < 64; c++) text += String.fromCharCode(cells[r * 64 + c]);
    text += "\n";
  }
  assert(walls >= 40, "стены стакана не нарисованы: " + walls);
  assert(floor === 20, "пол стакана не из двадцати знаков: " + floor);
  assert(text.includes("SCORE"), "нет панели");
  assert(left >= 4 && left === right, "клетки фигур не из половинок квадрата: " + left + "/" + right);
  assert(!text.includes("+---"), "верхняя планка всё ещё рисуется");
  assert(b.running, "игра остановилась сама, хотя должна крутиться");
});

test("широкий режим: клетка в один знак, стакан вдвое уже", () => {
  const src = progDiff.replace(/^105 CW%=\d+$/m, "105 CW%=1");
  const b = new Basic(src);
  b.keys.push(" ");
  b.start();
  let guard = 400000;
  while (b.running && guard-- > 0) b.step();
  const floor = [...b.screen.cells].filter(c => c === 186).length;
  assert(floor === 10, "пол стакана не сузился до десяти знаков: " + floor);
  assert([...b.screen.cells].filter(c => c === 130).length >= 4, "нет клетки в один знак");
  assert([...b.screen.cells].filter(c => c === 128).length === 0, "в широком формате половинок быть не должно");
});

test("уровень выбирается той же клавишей, что запускает игру", () => {
  for (const [key, level] of [[" ", 0], ["7", 7], ["Z", 0]]) {
    const b = new Basic(progDiff);
    b.keys.push(key);
    b.start();
    const stopAt = b.resolve(400);
    let guard = 400000;
    while (b.running && guard-- > 0) {
      if (b.pc[0] === stopAt && b.pc[1] === 0) break;
      b.step();
    }
    assert(b.getVar("LV%") === level, "клавиша " + key + ": уровень " + b.getVar("LV%"));
  }
});

test("рекорды: строковый массив, MID$ и вставка строки в таблицу", () => {
  const b = boot(progDiff);
  const names = [], points = [];
  for (let i = 0; i < 5; i++) { names.push(b.getArray("HS$", [i])); points.push(b.getArray("HP", [i])); }
  assert(names.every(n => typeof n === "string" && n.length), "таблица не прочиталась: " + names);

  b.setVar("SR", points[4] - 1);
  call(b, 7400);
  assert(b.getVar("HI%") === -1, "проигравший попал в таблицу");

  b.setVar("SR", points[0] + 1);
  b.keys.push("A", "B", String.fromCharCode(8), "C", String.fromCharCode(13));
  call(b, 7400);
  assert(b.getVar("HI%") === 0, "строка " + b.getVar("HI%"));
  assert(b.getArray("HS$", [0]) === "AC", "имя с забоем: " + b.getArray("HS$", [0]));
  assert(b.getArray("HS$", [1]) === names[0], "старая первая строка не сдвинулась");
});

test("двоеточие как разделитель операторов отвергается", () => {
  let threw = false;
  try { new Basic("10 A=1 : B=2"); } catch (e) { threw = true; }
  assert(threw, "двоеточие проехало");
});

console.log("");
console.log(failed ? failed + " сценариев провалились" : "все сценарии веб-версии прошли");
process.exit(failed ? 1 : 0);
