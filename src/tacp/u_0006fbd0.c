/*
 * src/tacp/u_0006fbd0.c: translation unit u_0006fbd0 of TACP.EXE, 0x0006FBD0..0x0006FD00 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0006fbd0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0006FC40);

#include <stdarg.h>

extern void *D_002E47E0;

int func_000C40B6(void *, char *, va_list);

/* void: EAX at ret holds only the callee's result. */
void func_0006FBD0(char *fmt, ...)
{
    va_list args;

    va_start(args, fmt);
    func_000C40B6(D_002E47E0, fmt, args);
    va_end(args);
}

extern char D_000E2AA8[];
extern char D_002B3C54[];

int fputs(char *, char *);
void exit(int);

void func_0006FC00(char *fmt, ...)
{
    va_list args;

    va_start(args, fmt);
    func_0006FBD0(fmt, args);
    va_end(args);
    fputs(D_000E2AA8, D_002B3C54);
    exit(1);
}
