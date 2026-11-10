/*
 * cg_lift.c: the C forms tools/reverseapoc/lift.py writes back, under wcc386 10.6 (quick task
 * 261107-qkd).
 *
 * Clean-room C89 written for ReverseApoc. No game code and no third-party code is copied here:
 * every function is written in the shape the lifter writes, with register-named parameters, to
 * measure that the compiler gives that shape back the bytes the lifter read.
 *
 * tests/test_lift_probe_real.py compiles this file through batch.compile_batch under -4r -s -fpi
 * and -4r -oneatx -s -fpi, lifts each function's bytes from a stub row and compiles the draft
 * under the same cell back to the same bytes. No function calls or reads a global: the stub row
 * has no fixups. Every function keeps a tail of its own, because -4r -s merges identical tails
 * across the functions of one file. It stays out of probe.PROBE_SOURCES, because the Phase 4
 * calibration table sums over that list. See probe/README.md.
 */

#include <math.h>
#include <string.h>

/* Struct copies: up to four dwords unrolled, a rep movsd from five, then movsw and movsb. */
struct copy_3 { char b[3]; };
struct copy_5 { char b[5]; };
struct copy_6 { char b[6]; };
struct copy_7 { char b[7]; };
struct copy_8 { char b[8]; };
struct copy_9 { char b[9]; };
struct copy_10 { char b[10]; };
struct copy_11 { char b[11]; };
struct copy_12 { char b[12]; };
struct copy_16 { char b[16]; };
struct copy_17 { char b[17]; };
struct copy_18 { char b[18]; };
struct copy_19 { char b[19]; };
struct copy_20 { char b[20]; };
struct copy_21 { char b[21]; };
struct copy_24 { char b[24]; };
struct copy_46 { char b[46]; };

void pr_lift_copy_3(int r_eax, int r_edx)
{
    *(struct copy_3 *)r_eax = *(struct copy_3 *)r_edx;
}

void pr_lift_copy_5(int r_eax, int r_edx)
{
    *(struct copy_5 *)r_eax = *(struct copy_5 *)r_edx;
}

void pr_lift_copy_6(int r_eax, int r_edx)
{
    *(struct copy_6 *)r_eax = *(struct copy_6 *)r_edx;
}

void pr_lift_copy_7(int r_eax, int r_edx)
{
    *(struct copy_7 *)r_eax = *(struct copy_7 *)r_edx;
}

void pr_lift_copy_8(int r_eax, int r_edx)
{
    *(struct copy_8 *)r_eax = *(struct copy_8 *)r_edx;
}

void pr_lift_copy_9(int r_eax, int r_edx)
{
    *(struct copy_9 *)r_eax = *(struct copy_9 *)r_edx;
}

void pr_lift_copy_10(int r_eax, int r_edx)
{
    *(struct copy_10 *)r_eax = *(struct copy_10 *)r_edx;
}

void pr_lift_copy_11(int r_eax, int r_edx)
{
    *(struct copy_11 *)r_eax = *(struct copy_11 *)r_edx;
}

void pr_lift_copy_12(int r_eax, int r_edx)
{
    *(struct copy_12 *)r_eax = *(struct copy_12 *)r_edx;
}

void pr_lift_copy_16(int r_eax, int r_edx)
{
    *(struct copy_16 *)r_eax = *(struct copy_16 *)r_edx;
}

void pr_lift_copy_17(int r_eax, int r_edx)
{
    *(struct copy_17 *)r_eax = *(struct copy_17 *)r_edx;
}

void pr_lift_copy_18(int r_eax, int r_edx)
{
    *(struct copy_18 *)r_eax = *(struct copy_18 *)r_edx;
}

void pr_lift_copy_19(int r_eax, int r_edx)
{
    *(struct copy_19 *)r_eax = *(struct copy_19 *)r_edx;
}

/*
 * The rep cases copy between their own register pairs. A rep with no movsw or movsb after it
 * ends the same way whatever the registers, so the 24-byte copy reads its destination back
 * after it: else -4r -s jumps into the 20-byte copy's rep movsd.
 */
void pr_lift_copy_20(int r_eax, int r_edx)
{
    *(struct copy_20 *)r_eax = *(struct copy_20 *)r_edx;
}

void pr_lift_copy_21(int r_eax, int r_edx)
{
    *(struct copy_21 *)r_eax = *(struct copy_21 *)r_edx;
}

int pr_lift_copy_24(int r_eax, int r_edx)
{
    *(struct copy_24 *)r_edx = *(struct copy_24 *)r_eax;
    return *(int *)r_edx;
}

void pr_lift_copy_46(int r_eax, int r_edx)
{
    *(struct copy_46 *)r_eax = *(struct copy_46 *)r_edx;
}

/*
 * Inline strlen and memcpy: string.h's intrinsic pragma needs -oi, which -oneatx holds. Plain
 * -4r -s calls strlen_ and memcpy_. A stub row has no caller to say its eax goes unread, so
 * what a void function leaves in eax reads back as returned: the inline strlen leaves 0, and the
 * store case returns that 0; a memcpy leaves its count, so the memcpy case returns its
 * destination.
 */
int pr_lift_strlen(int r_eax)
{
    return strlen((char *)r_eax);
}

int pr_lift_strlen_store(int r_eax, int r_edx)
{
    *(unsigned *)r_edx = strlen((char *)r_eax);
    return 0;
}

int pr_lift_memcpy(int r_eax, int r_edx, int r_ebx)
{
    memcpy((void *)r_eax, (void *)r_edx, r_ebx);
    return r_eax;
}

/*
 * x87 forms. math.h's intrinsic pragma inlines sqrt and log only with -om, which -oneatx holds
 * (plain calls IF@DSQRT and IF@DLOG); fabs inlines in both cells, but only through math.h: a
 * bare prototype compiles to call fabs_. log is fldln2; fxch st(1); fyl2x.
 */
void pr_lift_sqrt(int r_eax, int r_edx)
{
    *(double *)r_eax = sqrt(*(double *)r_edx);
}

void pr_lift_log(int r_eax, int r_edx)
{
    *(double *)r_eax = log(*(double *)r_edx);
}

void pr_lift_fabs(int r_eax, int r_edx)
{
    *(double *)r_eax = fabs(*(double *)r_edx);
}

void pr_lift_one_minus(int r_eax, int r_edx)
{
    *(double *)r_eax = 1.0 - *(double *)r_edx;
}

void pr_lift_plus_one(int r_eax, int r_edx)
{
    *(double *)r_edx = *(double *)r_eax + 1.0;
}

int pr_lift_below_zero(int r_eax)
{
    return *(double *)r_eax < 0.0;
}

/*
 * Address-taken stack slots of 4 bytes (07.2-14). The lifter declares each one int[1], which
 * keeps M2 on wcc386 10.6 where three char[4] in a call's frame do not (probe/cg_slots.c,
 * pr_arr_char4_x3). Each address is stored through r_eax, which keeps the slots in memory without
 * a call. The byte case reaches inside a slot, which on an int array steps through a char
 * pointer. The chars case is a char[4] original: plain only, because -oneatx builds its byte
 * constants in one register, a form the lifter writes as a mask that does not compile back.
 */
void pr_lift_taken_x3(int r_eax)
{
    int a[1];
    int b[1];
    int c[1];

    a[0] = 0x11;
    b[0] = 0x22;
    c[0] = 0x33;
    ((int *)r_eax)[0] = (int)a;
    ((int *)r_eax)[1] = (int)b;
    ((int *)r_eax)[2] = (int)c;
}

void pr_lift_taken_byte(int r_eax)
{
    int a[1];
    int b[1];
    int c[1];

    a[0] = 0x44;
    ((char *)b)[1] = 0x55;
    c[0] = 0x66;
    ((int *)r_eax)[3] = (int)a;
    ((int *)r_eax)[4] = (int)b;
    ((int *)r_eax)[5] = (int)c;
}

void pr_lift_taken_chars(int r_eax)
{
    char a[4];
    char b[4];
    char c[4];

    a[0] = 0x21;
    b[0] = 0x22;
    c[0] = 0x23;
    ((int *)r_eax)[6] = (int)a;
    ((int *)r_eax)[7] = (int)b;
    ((int *)r_eax)[8] = (int)c;
}
