/*
 * src/tacp/u_0003a830.c: translation unit u_0003a830 of TACP.EXE, 0x0003A830..0x0003B110 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0003a830`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0003A900);
INCLUDE_ASM(func_0003AED0);
INCLUDE_ASM(func_0003AF00);
INCLUDE_ASM(func_0003B070);

extern unsigned short D_000E60A8;

int func_0003A780(unsigned char c);

/*
 * func_0003A830: measures the widest wrapped line of the text at s, where every line is
 * a2 bytes wider than its text and the box is D_000E60A8 wide. A newline whose line still
 * fits ends the line (the running best is updated and both counters reset); a line that
 * overflows the box drops its leading space, keeps its own length as the next line's start
 * and updates the best with the finished line. sp records whether the current word starts
 * at a space; it is live across the call to func_0003A780, so it lives in memory.
 */
int func_0003A830(unsigned char *s, int a2)
{
    volatile int sp;
    int word;
    int line;
    int best;
    int t;
    unsigned char c;

    word = 0;
    line = 0;
    best = 0;
    do {
        sp = (*s == ' ');
        do {
            word += func_0003A780(*s);
            c = s[1];
            s++;
        } while (c != 0 && c != ' ' && c != '\n');
        if (*s == '\n') {
            t = line + word;
            if (t + a2 < D_000E60A8) {
                if (t > best) {
                    best = t;
                }
                line = 0;
                word = 0;
            }
        }
        t = line + word;
        if (t + a2 > D_000E60A8) {
            if (sp) {
                word -= func_0003A780(' ');
            }
            if (line > best) {
                best = line;
            }
            line = word;
        } else {
            line = t;
        }
        word = 0;
    } while (*s != 0);
    if (line > best) {
        best = line;
    }
    return best;
}
