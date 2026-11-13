/*
 * src/tacp/u_0009d140.c: translation unit u_0009d140 of TACP.EXE, 0x0009D140..0x0009F330 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0009d140`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0009D1D0);
INCLUDE_ASM(func_0009D250);
INCLUDE_ASM(func_0009D760);
INCLUDE_ASM(func_0009E930);
INCLUDE_ASM(func_0009E960);
INCLUDE_ASM(func_0009EC00);
INCLUDE_ASM(func_0009EE90);

/* Runtime calls: open_ is varargs (stack arguments), write_ and close_ take registers. */
extern int open(char *name, int flags, ...);
extern u32 write(int fd, void *buf, u32 count);
extern int close(int fd);

extern char D_000E327C[];
extern char D_001CAE18[];
extern char D_001CF120[];

int func_0009D140(void)
{
    int fd;
    u32 n;

    fd = open(D_000E327C, 0x221, 0x180);
    if (fd == -1) {
        return 1;
    }
    n = write(fd, D_001CAE18, 0x4308);
    if (n < 0x4308) {
        return 2;
    }
    n = write(fd, D_001CF120, 0x4308);
    if (n < 0x4308) {
        return 2;
    }
    if (close(fd) == -1) {
        return 3;
    }
    return 0;
}
