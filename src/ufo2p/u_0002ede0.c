/*
 * src/ufo2p/u_0002ede0.c: translation unit u_0002ede0 of UFO2P.EXE, 0x0002EDE0..0x0002F220 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0002ede0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

extern unsigned short D_000D4D12;
int func_0002ED30(unsigned char c);

int func_0002EDE0(unsigned char *s, int a2)
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
            word += func_0002ED30(*s);
            c = s[1];
            s++;
        } while (c != 0 && c != ' ' && c != '\n');
        if (*s == '\n') {
            t = line + word;
            if (t + a2 < D_000D4D12) {
                if (t > best) {
                    best = t;
                }
                line = 0;
                word = 0;
            }
        }
        t = line + word;
        if (t + a2 > D_000D4D12) {
            if (sp) {
                word -= func_0002ED30(' ');
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
INCLUDE_ASM(func_0002EEB0);
INCLUDE_ASM(func_0002F160);
