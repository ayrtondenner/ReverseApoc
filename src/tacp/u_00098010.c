/*
 * src/tacp/u_00098010.c: translation unit u_00098010 of TACP.EXE, 0x00098010..0x00098C00 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00098010`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00098010);
extern float D_0030C884[];
extern char D_0030C89C[];

int func_000983B0(int a, int b, int *out, int *handle, char *name);
void func_0009F330(int a, int handle, char *name, int count, float *dst);

void func_00098300(int a, int b, int row, int *out, float *mean)
{
    int handle;
    float w;
    float sum;
    int i;
    int k;

    *out = -1;
    *mean = 0;
    if (func_000983B0(a, b, out, &handle, D_0030C89C) == 0) {
        func_0009F330(8, handle, D_0030C89C, 6, D_0030C884);
        k = row * 3;
        sum = 0;
        for (i = 0; i < 3; i++) {
            w = D_0030C884[k + i];
            *mean += i * w;
            sum += w;
        }
        *mean /= sum;
    }
}

INCLUDE_ASM(func_000983B0);
INCLUDE_ASM(func_00098A20);
