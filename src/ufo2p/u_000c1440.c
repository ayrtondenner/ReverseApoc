/*
 * src/ufo2p/u_000c1440.c: translation unit u_000c1440 of UFO2P.EXE, 0x000C1440..0x000C1454 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000c1440`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000C1445);

int unlink(const char *path);

/* file_delete: delete a file by path
 * A five-byte thunk: jumps straight to the runtime unlink with the path in EAX
 * and returns its result (0 on success, -1 on failure).
 * Address: UFO2P.EXE 0x000C1440
 * Evidence: call: its whole body is jmp unlink_ (runtime); called from 0x0001DF40 and 0x000A3AF0
 */
int file_delete(const char *file_path)
{
    return unlink(file_path);
}
