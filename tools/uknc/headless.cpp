// Безголовый УКНЦ: гоняет настоящий эмулятор без окна и без человека.
//
// Ядро берётся из ukncbtl-wasm (nzeemin, LGPL) — те же файлы, что крутятся в
// браузерной сборке, только вместо canvas и клавиатуры браузера здесь скрипт и
// снимок экрана в PPM. Нужно это ради одной вещи: проверять BASIC-программу на
// настоящем Вильнюс-Бейсике из картриджа, а не на догадках о его синтаксисе.
//
//   uknc_run --cart romctr_basic.bin --script script.txt
//
// Команды скрипта:
//   frames N        прокрутить N кадров (кадр = 1/25 секунды машинного времени)
//   key NAME        нажать и отпустить клавишу (ENTER, SPACE, ESC, LEFT, ...);
//                   служебные клавиши УКНЦ по надписи: UST, POM, ISP, SBROS, K1..K5
//   type ТЕКСТ      набрать строку (без перевода строки)
//   line ТЕКСТ      набрать строку и нажать ENTER
//   file ПУТЬ       набрать файл построчно, каждая строка с ENTER
//   shot ПУТЬ.ppm   снимок экрана
//   delay N         сколько кадров тратить на один символ (по умолчанию 3)
//   echo ТЕКСТ      напечатать в лог

#include "stdafx.h"
#include "emubase/Emubase.h"

#include <cstdio>
#include <cstring>
#include <string>
#include <fstream>
#include <iostream>
#include <vector>

extern "C" {
    void Emulator_Init();
    void Emulator_Start();
    void Emulator_SystemFrame();
    void* Emulator_PrepareScreen(int screenViewMode);
    void Emulator_KeyEvent(uint8_t keyscan, bool pressed);
}
extern CMotherboard* g_pBoard;
extern uint32_t m_dwEmulatorUptime;

// Позиционное соответствие клавиш PC и УКНЦ, латинский регистр.
// Таблица перенесена из ukncbtl/emulator/ScreenView.cpp (arrPcscan2UkncscanLat),
// индекс — код виртуальной клавиши Windows.
static const unsigned char VK2UKNC[256] =
{
    /*0*/    0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0132, 0026, 0000, 0000, 0000, 0153, 0166, 0000,
    /*1*/    0105, 0000, 0000, 0000, 0107, 0000, 0000, 0000, 0000, 0000, 0000, 0006, 0000, 0000, 0000, 0000,
    /*2*/    0113, 0004, 0151, 0152, 0155, 0116, 0154, 0133, 0134, 0000, 0000, 0000, 0000, 0171, 0172, 0000,
    /*3*/    0176, 0030, 0031, 0032, 0013, 0034, 0035, 0016, 0017, 0177, 0000, 0000, 0000, 0000, 0000, 0000,
    /*4*/    0000, 0072, 0076, 0050, 0057, 0033, 0047, 0055, 0156, 0073, 0027, 0052, 0056, 0112, 0054, 0075,
    /*5*/    0053, 0067, 0074, 0111, 0114, 0051, 0137, 0071, 0115, 0070, 0157, 0000, 0000, 0106, 0000, 0000,
    /*6*/    0126, 0127, 0147, 0167, 0130, 0150, 0170, 0125, 0145, 0165, 0025, 0000, 0000, 0005, 0146, 0131,
    /*7*/    0010, 0011, 0012, 0014, 0015, 0172, 0152, 0151, 0171, 0000, 0004, 0155, 0000, 0000, 0000, 0000,
    /*8*/    0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000,
    /*9*/    0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000,
    /*a*/    0000, 0000, 0046, 0066, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000,
    /*b*/    0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0174, 0110, 0117, 0175, 0135, 0173,
    /*c*/    0007, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000,
    /*d*/    0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0036, 0136, 0037, 0077, 0000,
    /*e*/    0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000,
    /*f*/    0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000, 0000,
};

static const int VK_SHIFT_ = 0x10;

struct KeyStroke { int vk; bool shift; };

// Клавиатура УКНЦ в латинском регистре: символ -> код клавиши и верхний
// регистр. Таблица снята опытом на самой машине (tools/uknc/probe, снимок
// docs/img/keyboard-probe.png): раскладка знаков препинания у УКНЦ своя и с
// раскладкой PC не совпадает, поэтому позиционного соответствия мало.
struct AsciiKey { char ch; unsigned char scan; bool shift; };
static const AsciiKey ASCII_KEYS[] =
{
    { ' ', 0113, false },
    { '1', 0030, false }, { '2', 0031, false }, { '3', 0032, false },
    { '4', 0013, false }, { '5', 0034, false }, { '6', 0035, false },
    { '7', 0016, false }, { '8', 0017, false }, { '9', 0177, false },
    { '0', 0176, false },
    { '!', 0030, true }, { '"', 0031, true }, { '#', 0032, true },
    { '$', 0013, true },                        // на экране КОИ-7 это знак ¤
    { '%', 0034, true }, { '&', 0035, true }, { '\'', 0016, true },
    { '(', 0017, true }, { ')', 0177, true },
    { ';', 0007, false }, { '+', 0007, true },
    { '-', 0175, false }, { '=', 0175, true },
    { '/', 0173, false }, { '?', 0173, true },
    { ':', 0174, false }, { '*', 0174, true },
    { '.', 0135, false }, { '>', 0135, true },
    { ',', 0117, false }, { '<', 0117, true },
    { '^', 0110, false }, { '\\', 0136, false }, { '|', 0136, true },
    { '[', 0036, false }, { '{', 0036, true },
    { ']', 0037, false }, { '}', 0037, true },
    { '_', 0155, false }, { '@', 0077, false }, { '`', 0077, true },
    { 'A', 0072, false }, { 'B', 0076, false }, { 'C', 0050, false },
    { 'D', 0057, false }, { 'E', 0033, false }, { 'F', 0047, false },
    { 'G', 0055, false }, { 'H', 0156, false }, { 'I', 0073, false },
    { 'J', 0027, false }, { 'K', 0052, false }, { 'L', 0056, false },
    { 'M', 0112, false }, { 'N', 0054, false }, { 'O', 0075, false },
    { 'P', 0053, false }, { 'Q', 0067, false }, { 'R', 0074, false },
    { 'S', 0111, false }, { 'T', 0114, false }, { 'U', 0051, false },
    { 'V', 0137, false }, { 'W', 0071, false }, { 'X', 0115, false },
    { 'Y', 0070, false }, { 'Z', 0157, false },
};

static bool AsciiToScan(char ch, unsigned char& scan, bool& shift)
{
    if (ch >= 'a' && ch <= 'z') ch = char(ch - 'a' + 'A');
    for (size_t i = 0; i < sizeof(ASCII_KEYS) / sizeof(ASCII_KEYS[0]); i++)
    {
        if (ASCII_KEYS[i].ch == ch) { scan = ASCII_KEYS[i].scan; shift = ASCII_KEYS[i].shift; return true; }
    }
    return false;
}

static bool AsciiToKey(char ch, KeyStroke& out)
{
    out.shift = false;
    if (ch >= 'A' && ch <= 'Z') { out.vk = ch; return true; }
    if (ch >= 'a' && ch <= 'z') { out.vk = ch - 'a' + 'A'; return true; }
    if (ch >= '0' && ch <= '9') { out.vk = ch; return true; }
    if (ch == ' ') { out.vk = 0x20; return true; }
    return false;
}

// Служебные клавиши самой машины: у них нет соответствия на PC-клавиатуре,
// поэтому они называются по надписи на клавише и шлются кодом УКНЦ напрямую.
struct UkncKey { const char* name; unsigned char scan; };
static const UkncKey UKNC_KEYS[] =
{
    { "UST", 0152 },      // УСТ — системное меню «установка режимов»
    { "POM", 0172 },      // ПОМ
    { "ISP", 0151 },      // ИСП
    { "SBROS", 0171 },    // СБРОС
    { "AR2", 0006 },      // АР2
    { "GRAF", 0066 },     // ГРАФ
    { "ALF", 0106 },      // АЛФ
    { "FIKS", 0107 },     // ФИКС
    { "UPR", 0046 },      // УПР
    { "K1", 0010 }, { "K2", 0011 }, { "K3", 0012 }, { "K4", 0014 }, { "K5", 0015 },
};

static bool NamedUkncKey(const std::string& name, unsigned char& scan)
{
    for (size_t i = 0; i < sizeof(UKNC_KEYS) / sizeof(UKNC_KEYS[0]); i++)
    {
        if (name == UKNC_KEYS[i].name) { scan = UKNC_KEYS[i].scan; return true; }
    }
    return false;
}

static int NamedKey(const std::string& name)
{
    if (name == "ENTER") return 0x0D;
    if (name == "SPACE") return 0x20;
    if (name == "ESC") return 0x1B;
    if (name == "TAB") return 0x09;
    if (name == "BACKSPACE") return 0x08;
    if (name == "LEFT") return 0x25;
    if (name == "UP") return 0x26;
    if (name == "RIGHT") return 0x27;
    if (name == "DOWN") return 0x28;
    if (name == "STOP") return 0x1B;
    if (name.size() == 1) { KeyStroke k; if (AsciiToKey(name[0], k)) return k.vk; }
    return 0;
}

static int g_charDelay = 3;
static long g_frames = 0;

static void RunFrames(int count)
{
    for (int i = 0; i < count; i++) { Emulator_SystemFrame(); g_frames++; }
}

static void PressScan(unsigned char scan, bool shift)
{
    const unsigned char shiftScan = 0105;
    if (shift) { Emulator_KeyEvent(shiftScan, true); RunFrames(1); }
    Emulator_KeyEvent(scan, true);
    RunFrames(g_charDelay);
    Emulator_KeyEvent(scan, false);
    RunFrames(1);
    if (shift) { Emulator_KeyEvent(shiftScan, false); RunFrames(1); }
}

static void PressKey(int vk, bool shift)
{
    unsigned char scan = VK2UKNC[vk & 0xFF];
    if (scan == 0)
    {
        fprintf(stderr, "нет кода для клавиши vk=0x%02X\n", vk);
        return;
    }
    unsigned char shiftScan = VK2UKNC[VK_SHIFT_];
    if (shift) { Emulator_KeyEvent(shiftScan, true); RunFrames(1); }
    Emulator_KeyEvent(scan, true);
    RunFrames(g_charDelay);
    Emulator_KeyEvent(scan, false);
    RunFrames(1);
    if (shift) { Emulator_KeyEvent(shiftScan, false); RunFrames(1); }
}

static void TypeText(const std::string& text)
{
    for (size_t i = 0; i < text.size(); i++)
    {
        unsigned char scan; bool shift;
        if (!AsciiToScan(text[i], scan, shift))
        {
            fprintf(stderr, "не набирается символ '%c' (0x%02X)\n", text[i], (unsigned char)text[i]);
            continue;
        }
        PressScan(scan, shift);
    }
}

// Снимок состояния машины в формате UKNCBTL: его понимают и родной эмулятор,
// и браузерная сборка (параметр state= в адресе). Так набранная программа
// доезжает до человека, которому не хочется вводить шестьсот строк руками.
static bool SaveState(const char* path)
{
    FILE* fp = fopen(path, "w+b");
    if (fp == NULL) return false;
    uint8_t* image = (uint8_t*)calloc(UKNCIMAGE_SIZE, 1);
    if (image == NULL) { fclose(fp); return false; }
    uint32_t* header = (uint32_t*)image;
    *header++ = UKNCIMAGE_HEADER1;
    *header++ = UKNCIMAGE_HEADER2;
    *header++ = UKNCIMAGE_VERSION;
    *header++ = UKNCIMAGE_SIZE;
    g_pBoard->SaveToImage(image);
    *(uint32_t*)(image + 16) = m_dwEmulatorUptime;
    size_t written = fwrite(image, 1, UKNCIMAGE_SIZE, fp);
    free(image);
    fclose(fp);
    return written == UKNCIMAGE_SIZE;
}

static bool LoadState(const char* path)
{
    FILE* fp = fopen(path, "rb");
    if (fp == NULL) return false;
    uint8_t* image = (uint8_t*)calloc(UKNCIMAGE_SIZE, 1);
    if (image == NULL) { fclose(fp); return false; }
    size_t read = fread(image, 1, UKNCIMAGE_SIZE, fp);
    fclose(fp);
    if (read != UKNCIMAGE_SIZE) { free(image); return false; }
    uint32_t* header = (uint32_t*)image;
    if (header[0] != UKNCIMAGE_HEADER1 || header[1] != UKNCIMAGE_HEADER2) { free(image); return false; }
    g_pBoard->LoadFromImage(image);
    m_dwEmulatorUptime = *(uint32_t*)(image + 16);
    free(image);
    return true;
}

static bool SaveScreen(const char* path)
{
    const int width = 640, height = 288;
    uint32_t* bits = (uint32_t*)Emulator_PrepareScreen(1);
    if (bits == NULL) return false;
    FILE* fp = fopen(path, "wb");
    if (fp == NULL) return false;
    fprintf(fp, "P6\n%d %d\n255\n", width, height);
    std::vector<unsigned char> row(width * 3);
    for (int y = 0; y < height; y++)
    {
        for (int x = 0; x < width; x++)
        {
            uint32_t c = bits[y * width + x];
            row[x * 3 + 0] = (unsigned char)((c >> 16) & 0xFF);
            row[x * 3 + 1] = (unsigned char)((c >> 8) & 0xFF);
            row[x * 3 + 2] = (unsigned char)(c & 0xFF);
        }
        fwrite(&row[0], 1, row.size(), fp);
    }
    fclose(fp);
    return true;
}

// Ждать, пока картинка на экране изменится: так меряется скорость машины
// (сколько кадров занимает шаг программы) и так же ловится момент, когда
// БЕЙСИК ответил на ввод.
static long WaitChange(long maxFrames)
{
    const size_t bytes = 640 * 288 * 4;
    std::vector<unsigned char> before(bytes);
    memcpy(&before[0], Emulator_PrepareScreen(1), bytes);
    for (long i = 1; i <= maxFrames; i++)
    {
        RunFrames(1);
        if (memcmp(&before[0], Emulator_PrepareScreen(1), bytes) != 0)
            return i;
    }
    return -1;
}

// То же самое, но следим только за прямоугольником экрана. Нужно потому, что
// мигающий курсор меняет картинку сам по себе и портит всякий замер времени.
static long WaitRegion(int x1, int y1, int x2, int y2, long maxFrames)
{
    const int width = 640;
    std::vector<uint32_t> before;
    for (int y = y1; y <= y2; y++)
    {
        uint32_t* bits = (uint32_t*)Emulator_PrepareScreen(1);
        for (int x = x1; x <= x2; x++) before.push_back(bits[y * width + x]);
    }
    for (long i = 1; i <= maxFrames; i++)
    {
        RunFrames(1);
        uint32_t* bits = (uint32_t*)Emulator_PrepareScreen(1);
        size_t k = 0;
        bool same = true;
        for (int y = y1; y <= y2 && same; y++)
            for (int x = x1; x <= x2; x++)
                if (before[k++] != bits[y * width + x]) { same = false; break; }
        if (!same) return i;
    }
    return -1;
}

static void TypeFile(const std::string& path)
{
    std::ifstream in(path.c_str());
    if (!in) { fprintf(stderr, "нет файла %s\n", path.c_str()); return; }
    std::string line;
    int count = 0;
    while (std::getline(in, line))
    {
        while (!line.empty() && (line[line.size() - 1] == '\r' || line[line.size() - 1] == ' '))
            line.erase(line.size() - 1);
        if (line.empty()) continue;
        TypeText(line);
        PressKey(0x0D, false);
        RunFrames(2);
        count++;
        if (count % 25 == 0)
            fprintf(stderr, "  набрано строк: %d (кадров %ld)\n", count, g_frames);
    }
    fprintf(stderr, "  набрано строк: %d\n", count);
}

static bool LoadCartridge(int slot, const char* path)
{
    FILE* fp = fopen(path, "rb");
    if (fp == NULL) return false;
    uint8_t* image = (uint8_t*)calloc(24 * 1024, 1);
    size_t read = fread(image, 1, 24 * 1024, fp);
    fclose(fp);
    if (read != 24 * 1024) { free(image); return false; }
    g_pBoard->LoadROMCartridge(slot, image);
    free(image);
    return true;
}

int main(int argc, char** argv)
{
    const char* cart = NULL;
    const char* disk = NULL;
    const char* script = NULL;
    for (int i = 1; i < argc; i++)
    {
        std::string arg = argv[i];
        if (arg == "--cart" && i + 1 < argc) cart = argv[++i];
        else if (arg == "--disk" && i + 1 < argc) disk = argv[++i];
        else if (arg == "--script" && i + 1 < argc) script = argv[++i];
        else { fprintf(stderr, "непонятный аргумент %s\n", argv[i]); return 2; }
    }

    Emulator_Init();
    if (cart != NULL && !LoadCartridge(1, cart))
    {
        fprintf(stderr, "не загрузился картридж %s\n", cart);
        return 1;
    }
    if (disk != NULL && !g_pBoard->AttachFloppyImage(0, disk))
    {
        fprintf(stderr, "не подключился образ %s\n", disk);
        return 1;
    }
    Emulator_Start();

    std::istream* in = &std::cin;
    std::ifstream file;
    if (script != NULL)
    {
        file.open(script);
        if (!file) { fprintf(stderr, "нет скрипта %s\n", script); return 1; }
        in = &file;
    }

    std::string line;
    while (std::getline(*in, line))
    {
        if (line.empty() || line[0] == '#') continue;
        size_t space = line.find(' ');
        std::string cmd = line.substr(0, space);
        std::string rest = (space == std::string::npos) ? "" : line.substr(space + 1);
        if (cmd == "frames") RunFrames(atoi(rest.c_str()));
        else if (cmd == "delay") g_charDelay = atoi(rest.c_str());
        else if (cmd == "key")
        {
            unsigned char scan = 0;
            if (NamedUkncKey(rest, scan)) PressScan(scan, false);
            else { int vk = NamedKey(rest); if (vk) PressKey(vk, false); else fprintf(stderr, "нет клавиши %s\n", rest.c_str()); }
        }
        else if (cmd == "raw") { unsigned scan = 0; int shift = 0; sscanf(rest.c_str(), "%o %d", &scan, &shift); PressScan((unsigned char)scan, shift != 0); }
        else if (cmd == "type") TypeText(rest);
        else if (cmd == "line") { TypeText(rest); PressKey(0x0D, false); }
        else if (cmd == "file") TypeFile(rest);
        else if (cmd == "loadstate")
        {
            if (LoadState(rest.c_str())) fprintf(stderr, "состояние загружено: %s\n", rest.c_str());
            else fprintf(stderr, "не загрузилось состояние %s\n", rest.c_str());
        }
        else if (cmd == "save")
        {
            if (SaveState(rest.c_str())) fprintf(stderr, "состояние %s (кадр %ld)\n", rest.c_str(), g_frames);
            else fprintf(stderr, "не записалось состояние %s\n", rest.c_str());
        }
        else if (cmd == "shot") { if (SaveScreen(rest.c_str())) fprintf(stderr, "снимок %s (кадр %ld)\n", rest.c_str(), g_frames); }
        else if (cmd == "echo") fprintf(stderr, "%s\n", rest.c_str());
        else if (cmd == "waitregion")
        {
            int x1 = 0, y1 = 0, x2 = 0, y2 = 0; long limit = 0;
            sscanf(rest.c_str(), "%d %d %d %d %ld", &x1, &y1, &x2, &y2, &limit);
            if (limit <= 0) limit = 5000;
            long got = WaitRegion(x1, y1, x2, y2, limit);
            if (got < 0) fprintf(stderr, "область не изменилась за %ld кадров\n", limit);
            else fprintf(stderr, "область изменилась через %ld кадров (%.2f c)\n", got, got / 25.0);
        }
        else if (cmd == "waitchange")
        {
            long limit = atol(rest.c_str());
            if (limit <= 0) limit = 2000;
            long got = WaitChange(limit);
            if (got < 0) fprintf(stderr, "экран не изменился за %ld кадров\n", limit);
            else fprintf(stderr, "экран изменился через %ld кадров (%.2f c)\n", got, got / 25.0);
        }
        else fprintf(stderr, "непонятная команда: %s\n", cmd.c_str());
    }
    fprintf(stderr, "всего кадров: %ld\n", g_frames);
    return 0;
}
