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
