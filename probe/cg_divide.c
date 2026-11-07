/*
 * cg_divide.c: signed divide by a power of two under wcc386 10.6 (quick task 261107-qkb).
 *
 * Clean-room C89 written for ReverseApoc. No game code and no third-party code is copied here:
 * every shape was written to measure the form the compiler gives `x / 2^n` for a signed int,
 * which tools/reverseapoc/lift.py turns back into that divide.
 *
 * tests/test_lift_divide_real.py compiles this file through batch.compile_batch under the `*`
 * rule of config/cflags.txt (-4r -s -fpi), lifts each function's bytes and compiles the draft
 * back to the same bytes. It stays out of probe.PROBE_SOURCES, because the Phase 4 calibration
 * table sums over that list. See probe/README.md.
 */

/* x / 2: the sign is subtracted, then one shift. */
int pr_div2(int x)
{
    return x / 2;
}

/* x / 4: the sign, shifted left, is the borrow sbb subtracts with it. */
int pr_div4(int x)
{
    return x / 4;
}

/* x / 16: the same form with a wider shift. */
int pr_div16(int x)
{
    return x / 16;
}

/* A dividend loaded from memory. */
int pr_div8_load(int *p)
{
    return *p / 8;
}

/* A dividend that arrives in edx, not eax, beside a parameter the sum still reads. */
int pr_div2_second(int a, int b)
{
    return a + b / 2;
}
