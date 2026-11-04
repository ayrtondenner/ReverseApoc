/*
 * cg_slots.c: stack-slot probe for the wcc386 10.6 frame model (Phase 7.1, D-02).
 *
 * Clean-room C89 written for ReverseApoc. No game code and no third-party code is copied here:
 * every shape was written to measure one rule of tools/reverseapoc/slots.py.
 *
 * Each function stores a distinct marker constant in each local, then passes every address to
 * the extern pr_take, so every local is forced into memory and its marker names its slot. Each
 * reversed twin declares the same locals backwards. tests/test_slots_real.py compiles this file
 * through batch.compile_batch under -4r -s -fpi and -4r -oneatx -s -fpi. It stays out of
 * probe.PROBE_SOURCES, because the Phase 4 calibration table sums over that list. See
 * probe/README.md.
 */

extern void pr_take(void *first, ...);

/* Equal sizes: the first declared takes the highest offset. */
void pr_slot_same_size(void)
{
    int a;
    int b;
    int c;
    int d;

    a = 0x11;
    b = 0x22;
    c = 0x33;
    d = 0x44;
    pr_take(&a, &b, &c, &d);
}

void pr_slot_same_size_rev(void)
{
    int d;
    int c;
    int b;
    int a;

    a = 0x11;
    b = 0x22;
    c = 0x33;
    d = 0x44;
    pr_take(&a, &b, &c, &d);
}

/* Four sizes: the largest sits lowest whatever the declaration order, each padded to 4. */
void pr_slot_mixed(void)
{
    char a;
    int b;
    short c;
    double d;

    a = 0x11;
    b = 0x22;
    c = 0x33;
    d = 2.5;
    pr_take(&a, &b, &c, &d);
}

void pr_slot_mixed_rev(void)
{
    double d;
    short c;
    int b;
    char a;

    a = 0x11;
    b = 0x22;
    c = 0x33;
    d = 2.5;
    pr_take(&a, &b, &c, &d);
}
