/*
 * src/ufo2p/u_0006ee50.c: translation unit u_0006ee50 of UFO2P.EXE, 0x0006EE50..0x0006FE10 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0006ee50`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0006EE50);
INCLUDE_ASM(func_0006EEF0);
INCLUDE_ASM(func_0006F3C0);
INCLUDE_ASM(func_0006F750);

extern char D_000D5060[];
void func_0006F830(int);
extern char D_00183A68[];
extern u8 *D_0018276C;

int func_00070B70(int);
unsigned short func_0005CD00(int);

u8 *func_0006F600(u8 *arg)
{
    u8 *items[15];
    u8 *result;
    int x, y, xx, yy, count, i;
    u8 *p;

    count = 0;
    result = 0;
    for (i = 0; i < 10; i++) items[i] = 0;
    x = *(s16 *)(arg + 2) + (*(s16 *)(arg + 4) - *(s16 *)(arg + 2)) / 2;
    y = *(s16 *)(arg + 6) + (*(s16 *)(arg + 8) - *(s16 *)(arg + 6)) / 2;
    for (p = D_0018276C; p < D_0018276C + *(u16 *)D_00183A68 * 0xe2; p += 0xe2) {
        if (p != arg) {
            xx = *(s16 *)(p + 2) + (*(s16 *)(p + 4) - *(s16 *)(p + 2)) / 2;
            yy = *(s16 *)(p + 6) + (*(s16 *)(p + 8) - *(s16 *)(p + 6)) / 2;
            if (xx - 15 < x && xx + 15 > x && yy - 15 < y && yy + 15 > y &&
                func_00070B70((p - D_0018276C) / 0xe2) == 0 && count < 15) {
                items[count] = p;
                count++;
            }
        }
    }
    if (count != 0) result = items[func_0005CD00((short)(count - 1))];
    return result;
}

void func_0006F800(void)
{
    int r_edx;

    if ((*(signed char *)((D_000D5060))) != 0) goto L6F822;
    r_edx = 0;
    goto L6F816;
L6F80E:;
    func_0006F830(r_edx);
    r_edx = r_edx + 1;
L6F816:;
    if (r_edx < (*(unsigned short *)((D_00183A68)))) goto L6F80E;
L6F822:;
    return;
}

extern int D_000E0D0C[];
extern int D_000E0CCC;
extern u8 D_000D96EA[];
extern u8 *D_0017FB4C;
s16 func_0005EDB0(s16);
int func_000922B0(s16, s16);
void func_0004DFD0(void);

/* The callers do not use a result. */
void func_0006F830(int arg)
{
    int amounts[14];
    int total, random, i, chance, id;
    u8 *source, *dest;

    source = D_0018276C + arg * 0xe2;
    total = 0;
    random = func_0005CD00(30);
    for (i = 0; i < 14; i++) {
        amounts[i] = source[0xd4 + i] * (D_000E0D0C[i] + random) / 100;
        total += amounts[i];
    }
    if (total < 3) return;
    dest = func_0006F600(source);
    if (dest == 0) return;
    chance = total * 3 + 15;
    if (D_0017FB4C[source[0xc8] * 0x1b6 + 0x11] != 0 ||
        (short)func_000922B0(source[0xc8], 1) != 0)
        chance += 20;
    if (func_0005CD00(100) >= chance) return;
    id = func_0005EDB0((short)((dest - D_0018276C) / 0xe2));
    if (id != -1 && func_0005CD00(100) < total * 5)
        *(short *)(D_000D96EA + id * 0x2be) = 1;
    for (i = 0; i < 14; i++) {
        source[0xd4 + i] -= amounts[i];
        dest[0xd4 + i] += amounts[i];
    }
    if (D_000E0CCC != 0) func_0004DFD0();
}
INCLUDE_ASM(func_0006F9B0);

extern int D_000F3D78[];
extern int D_000E0D48[];
extern int D_000E0E0C[];
extern u8 *D_0018276C;

int func_0006FC80(int arg)
{
    int row_index;
    int total;
    int sum;
    int k;
    u8 *row;

    total = 0;
    row = D_0018276C;
    for (row_index = 0; row_index < *(unsigned short *)(D_00183A68);) {
        sum = 0;
        if (row[0xc8] == arg) {
            for (k = 0; k < 14; k++) {
                sum += row[0xd4 + k] * D_000F3D78[k];
            }
            sum *= D_000E0D48[*(s16 *)(row + 0xaa)];
            sum *= D_000E0E0C[arg];
        }
        row_index++;
        row += 0xe2;
        total += sum;
    }
    return total;
}

#define DAILY_HISTORY_ROWS 27
#define DAILY_HISTORY_SLOTS 56
#define DAILY_HISTORY_LAST_SLOT 55

/* daily_history_from_slot1 is the same table as daily_history, seen from slot 1 (4 bytes on); objdiff pairs
 * the copy only with two externs. */
extern int daily_history[DAILY_HISTORY_ROWS][DAILY_HISTORY_SLOTS];
extern int daily_history_from_slot1[DAILY_HISTORY_ROWS][DAILY_HISTORY_SLOTS];

extern unsigned char *D_0017FB4C;
extern short D_000E0C9C;
extern short D_000D4D68;

/* EAX is unused by the callers. */
void func_0006FD20(void)
{
    int i;
    int offset;
    int history_offset;

    i = 0;
    offset = 0;
    history_offset = 0;
    do {
        if (D_0017FB4C[offset + 0x11] == 1) {
            *(int *)((char *)daily_history + history_offset) = 200;
        } else {
            *(int *)((char *)daily_history + history_offset) += func_0006FC80(i) / (42 - D_000E0C9C);
            if (D_000D4D68 % 2 != 0)
                --*(int *)((char *)daily_history + history_offset);
            if (*(int *)((char *)daily_history + history_offset) > 200)
                *(int *)((char *)daily_history + history_offset) = 200;
            if (*(int *)((char *)daily_history + history_offset) < 0)
                *(int *)((char *)daily_history + history_offset) = 0;
        }
        offset += 0x1b6;
        i++;
        history_offset += 0xe0;
    } while (i < 27);
}

/* daily_history_age: age the daily history table by one day
 * Moves every slot of each of the 27 rows of 56 ints one slot on (slot k to k + 1), dropping
 * the last slot; slot 0 keeps its old value for the caller to overwrite. Row stride 0xE0.
 * EAX is unused: void.
 * Address: UFO2P.EXE 0x0006FDD0
 * Evidence: call: 0x0004AB30 calls it once the hour counter at 0x000D4D68 reaches 0x18 (a new day)
 * Evidence: call: 0x0004AAF0 calls it between 0x0007A5D0 and 0x00098180, as 0x0004AB30 does daily
 */
void daily_history_age(void)
{
    int row;
    int slot;

    for (row = 0; row < DAILY_HISTORY_ROWS; row++) {
        for (slot = DAILY_HISTORY_LAST_SLOT; slot > 0; slot--) {
            daily_history_from_slot1[row][slot - 1] = daily_history[row][slot - 1];
        }
    }
}
