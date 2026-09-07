// Безголовый БК-0010: тот же приём, что и с УКНЦ, только машина другая.
//
// Нужен ради одной вещи: посмотреть на эталон. Тетрис для БК-0010 в этом проекте
// считается образцом ощущений (AGENTS.md, раздел 14), а до сих пор о нём было
// известно только из чужих пересказов.
//
//   bk_run --bin Tetris.bin --script script.txt
//
// Команды скрипта:
//   frames N        прокрутить N кадров (кадр = 1/25 секунды машинного времени)
//   delay N         сколько кадров держать клавишу (по умолчанию 3)
//   key NAME        клавиша: ENTER, SPACE, LEFT, RIGHT, UP, DOWN или сам знак
//   type ТЕКСТ      набрать строку (коды БК совпадают с КОИ-7)
//   loadbin ПУТЬ    положить .bin в память (заголовок: адрес и длина словами)
//   start АДРЕС     запустить монитором: S, адрес восьмеричный, ввод
//   shot ПУТЬ.ppm   снимок экрана 512x256

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
    void Emulator_InitConfiguration(uint16_t configuration);
    void Emulator_Start();
    void Emulator_Reset();
    void Emulator_SystemFrame();
    void* Emulator_PrepareScreen();
    void Emulator_KeyEvent(uint8_t keyscan, bool pressed);
}
extern CMotherboard* g_pBoard;

static int g_delay = 3;
static long g_frames = 0;

static void RunFrames(int count)
{
    for (int i = 0; i < count; i++) { Emulator_SystemFrame(); g_frames++; }
}

static void PressScan(unsigned char scan)
{
    Emulator_KeyEvent(scan, true);
    RunFrames(g_delay);
    Emulator_KeyEvent(scan, false);
    RunFrames(2);
}

// Коды клавиш БК — это КОИ-7: буква посылается своим кодом.
static int NamedKey(const std::string& name)
{
    if (name == "ENTER") return 012;
    if (name == "SPACE") return 040;
    if (name == "LEFT") return 010;
    if (name == "RIGHT") return 031;
    if (name == "UP") return 032;
    if (name == "DOWN") return 033;
    if (name == "STOP") return 003;
    if (name.size() == 1) return (unsigned char)toupper(name[0]);
    return 0;
}

// Формат .bin: слово адреса, слово длины, дальше данные.
static bool LoadBin(const char* path)
{
    FILE* fp = fopen(path, "rb");
    if (fp == NULL) return false;
    unsigned char header[4];
    if (fread(header, 1, 4, fp) != 4) { fclose(fp); return false; }
    uint16_t base = (uint16_t)(header[0] | (header[1] << 8));
    uint16_t size = (uint16_t)(header[2] | (header[3] << 8));
    std::vector<unsigned char> data((size + 1) & 0xFFFE, 0);
    size_t read = fread(&data[0], 1, size, fp);
    fclose(fp);
    if (read != size) return false;
    for (size_t i = 0; i + 1 < data.size(); i += 2)
        g_pBoard->SetRAMWord((uint16_t)(base + i), (uint16_t)(data[i] | (data[i + 1] << 8)));
    fprintf(stderr, "загружено %u байт по адресу %06o\n", (unsigned)size, base);
    return true;
}

static bool SaveScreen(const char* path)
{
    const int width = 512, height = 256;
    uint32_t* bits = (uint32_t*)Emulator_PrepareScreen();
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

int main(int argc, char** argv)
{
    const char* binfile = NULL;
    const char* script = NULL;
    for (int i = 1; i < argc; i++)
    {
        std::string arg = argv[i];
        if (arg == "--bin" && i + 1 < argc) binfile = argv[++i];
        else if (arg == "--script" && i + 1 < argc) script = argv[++i];
        else { fprintf(stderr, "непонятный аргумент %s\n", argv[i]); return 2; }
    }

    Emulator_Init();
    Emulator_InitConfiguration(0);   // БК-0010 с монитором
    Emulator_Reset();
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
        else if (cmd == "delay") g_delay = atoi(rest.c_str());
        else if (cmd == "key") { int k = NamedKey(rest); if (k) PressScan((unsigned char)k); else fprintf(stderr, "нет клавиши %s\n", rest.c_str()); }
        else if (cmd == "type") { for (size_t i = 0; i < rest.size(); i++) PressScan((unsigned char)toupper(rest[i])); }
        else if (cmd == "loadbin")
        {
            const char* path = rest.empty() ? binfile : rest.c_str();
            if (path == NULL || !LoadBin(path)) fprintf(stderr, "не загрузился %s\n", path ? path : "(нет файла)");
        }
        else if (cmd == "start")
        {
            PressScan('S');
            for (size_t i = 0; i < rest.size(); i++) PressScan((unsigned char)rest[i]);
            PressScan(012);
        }
        else if (cmd == "shot") { if (SaveScreen(rest.c_str())) fprintf(stderr, "снимок %s (кадр %ld)\n", rest.c_str(), g_frames); }
        else if (cmd == "echo") fprintf(stderr, "%s\n", rest.c_str());
        else fprintf(stderr, "непонятная команда: %s\n", cmd.c_str());
    }
    fprintf(stderr, "всего кадров: %ld\n", g_frames);
    return 0;
}
