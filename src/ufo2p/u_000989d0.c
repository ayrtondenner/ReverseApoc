/*
 * src/ufo2p/u_000989d0.c: translation unit u_000989d0 of UFO2P.EXE, 0x000989D0..0x0009A420 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000989d0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000989D0);
INCLUDE_ASM(func_00098A70);
INCLUDE_ASM(func_00099050);
INCLUDE_ASM(func_00099710);
INCLUDE_ASM(func_00099B50);
INCLUDE_ASM(func_00099CE0);
INCLUDE_ASM(func_00099DB0);
INCLUDE_ASM(func_0009A0A0);

extern int daily_history[27][56];

extern volatile int D_00182CB0;
extern int *D_00182D5C;
extern int *D_00182D78;
extern char D_000D2B0C[], D_000D2B10[], D_000D2B14[], D_000D2AD8[], D_001285DC[];
int func_0002E430(void);
void func_0002F220(int);
void func_0002E470(int, int);
int func_00063800(int);
signed char func_000B7800(char *);
void func_00099880(void);
int func_0002E640(int, int, int, int, int, int *, int, void (*)(void), int);
void func_0002F7F0(int, int, int *, int, int, char *);

void func_00099950(void)
{
    int a;
    int b;

    func_0002F220(func_0002E430());
    a = D_00182CB0;
    func_0002E470(a, 128);
    func_0002E640(602, 40, 640, 75, 0, D_00182D5C + D_00182D78[79], func_000B7800(D_000D2B0C), func_00099880, func_00063800(22));
    a = func_0002E640(568, 46, 590, 70, 0, D_00182D5C + D_00182D78[1], func_000B7800(D_000D2B10), 0, 0);
    b = func_0002E640(568, 352, 590, 374, 0, D_00182D5C + D_00182D78[0], func_000B7800(D_000D2B14), 0, 0);
    func_0002F7F0(a, b, D_00182D5C + D_00182D78[4], 0, 90, D_001285DC);
    func_0002E640(602, 443, 640, 480, 0, D_00182D5C + D_00182D78[5], func_000B7800(D_000D2AD8), 0, 0);
}

int func_00099830(int *a, int *b)
{
    int x;
    int y;

    x = daily_history[*a][0];
    y = daily_history[*b][0];
    if (x == 200) {
        x = 0;
    }
    if (y == 200) {
        y = 0;
    }
    return y - x;
}

extern signed char D_000E12FC[10];
extern int D_001A88C8[25];
extern int D_001285E0;
extern void qsort(void *base, unsigned n, unsigned size, int (*cmp)(int *, int *));

void func_00099880(void)
{
    int i;
    int j;
    int v;
    signed char n;
    signed char c;

    i = 0;
    n = i + 2;
    do {
        D_001A88C8[i] = i + 2;
        c = n;
        j = 0;
        do {
            if (D_000E12FC[j] == c) {
                D_000E12FC[j] = -1;
                break;
            }
            j++;
        } while (j < 10);
        n++;
        i++;
    } while (i < 25);
    qsort(D_001A88C8, 25, 4, func_00099830);
    i = 0;
    do {
        if (daily_history[D_001A88C8[i]][0] > 0 && daily_history[D_001A88C8[i]][0] < 200) {
            c = D_001A88C8[i];
            for (j = 0; j < 10; j++) {
                if (D_000E12FC[j] == -1) {
                    D_000E12FC[j] = c;
                    break;
                }
            }
        }
        i++;
    } while (i != 10);
    D_001285E0 = 1;
}
