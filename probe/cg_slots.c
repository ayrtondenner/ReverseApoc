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
extern int pr_get(void);
extern void pr_put(int a, int b, int c, int d);

struct pr_three {
    char a;
    char b;
    char c;
};

struct pr_six {
    short a;
    short b;
    short c;
};

struct pr_twelve {
    int a;
    int b;
    int c;
};

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

/* Arrays sort by total size, not by element: 12, 8 and 6 bytes, the last padded to 8. */
void pr_slot_array(void)
{
    int a[3];
    int b[2];
    char c[6];

    a[0] = 0x11;
    b[0] = 0x22;
    c[0] = 0x33;
    pr_take(a, b, c);
}

void pr_slot_array_rev(void)
{
    char c[6];
    int b[2];
    int a[3];

    a[0] = 0x11;
    b[0] = 0x22;
    c[0] = 0x33;
    pr_take(a, b, c);
}

/* Structs sort by total size too, beside a scalar. */
void pr_slot_struct(void)
{
    struct pr_three a;
    struct pr_six b;
    struct pr_twelve c;
    int d;

    a.a = 0x11;
    b.a = 0x22;
    c.a = 0x33;
    d = 0x44;
    pr_take(&a, &b, &c, &d);
}

void pr_slot_struct_rev(void)
{
    int d;
    struct pr_twelve c;
    struct pr_six b;
    struct pr_three a;

    a.a = 0x11;
    b.a = 0x22;
    c.a = 0x33;
    d = 0x44;
    pr_take(&a, &b, &c, &d);
}

/* Odd sizes pad to 4, and a 3-byte array still sits above a 4-byte int. */
void pr_slot_odd(void)
{
    char a[3];
    char b[5];
    char c[7];
    int d;

    a[0] = 0x11;
    b[0] = 0x22;
    c[0] = 0x33;
    d = 0x44;
    pr_take(a, b, c, &d);
}

void pr_slot_odd_rev(void)
{
    int d;
    char c[7];
    char b[5];
    char a[3];

    a[0] = 0x11;
    b[0] = 0x22;
    c[0] = 0x33;
    d = 0x44;
    pr_take(a, b, c, &d);
}

/* Nothing aligns past 4: this double sits at 0xC. */
void pr_slot_unaligned(void)
{
    char a[12];
    double d;
    int b;

    a[0] = 0x11;
    d = 2.5;
    b = 0x22;
    pr_take(a, &d, &b);
}

/* Ties of 1, 2 and 4 bytes together, scalars beside arrays of the same size. */
void pr_slot_small(void)
{
    char a;
    char b[1];
    short c;
    short d[1];
    int e;
    int f[1];

    a = 0x11;
    b[0] = 0x22;
    c = 0x33;
    d[0] = 0x44;
    e = 0x55;
    f[0] = 0x66;
    pr_take(&a, b, &c, d, &e, f);
}

void pr_slot_small_rev(void)
{
    int f[1];
    int e;
    short d[1];
    short c;
    char b[1];
    char a;

    a = 0x11;
    b[0] = 0x22;
    c = 0x33;
    d[0] = 0x44;
    e = 0x55;
    f[0] = 0x66;
    pr_take(&a, b, &c, d, &e, f);
}

/* The flat form of pr_slot_scope. */
void pr_slot_flat(void)
{
    int a;
    int b;
    int c;

    a = 0x11;
    b = 0x22;
    c = 0x33;
    pr_take(&a, &b, &c);
}

/* Nested blocks reverse pr_slot_flat: an earlier block sits lower, and no slot is shared. */
void pr_slot_scope(int x)
{
    int a;

    a = 0x11;
    if (x) {
        int b;

        b = 0x22;
        if (x > 1) {
            int c;

            c = 0x33;
            pr_take(&a, &b, &c);
        }
    }
}

/* Inside a block the first declared is still highest. */
void pr_slot_scope_pairs(int x)
{
    int a;
    int b;

    a = 0x11;
    b = 0x22;
    if (x) {
        int c;
        int d;

        c = 0x33;
        d = 0x44;
        pr_take(&a, &b, &c, &d);
    }
}

/* Size comes before scope: every int sits below every short. */
void pr_slot_scope_sizes(int x)
{
    int a;
    short b;

    a = 0x11;
    b = 0x22;
    if (x) {
        int c;
        short d;

        c = 0x33;
        d = 0x44;
        if (x > 1) {
            int e;
            short f;

            e = 0x55;
            f = 0x66;
            pr_take(&a, &b, &c, &d, &e, &f);
        }
    }
}

/* Sibling blocks share nothing either, and take offsets in source order. */
void pr_slot_siblings(int x)
{
    int a;

    a = 0x11;
    if (x) {
        int b;

        b = 0x22;
        pr_take(&a, &b);
    }
    if (x > 1) {
        int c;

        c = 0x33;
        pr_take(&a, &c);
    }
    if (x > 2) {
        int d;

        d = 0x44;
        pr_take(&a, &d);
    }
}

/* The key is the place of the block in the source, not its depth: d sits below the deeper c,
   and above the b of an earlier block as deep as its own. */
void pr_slot_block_order(int x)
{
    int a;

    a = 0x11;
    if (x) {
        int b;

        b = 0x22;
        pr_take(&a, &b);
    }
    if (x > 2) {
        int d;

        d = 0x44;
        if (x > 3) {
            int c;

            c = 0x33;
            pr_take(&a, &d, &c);
        }
    }
}

/* A local nothing uses takes no slot, an array included. */
void pr_slot_unused(void)
{
    int a;
    int b;
    int c[4];

    a = 0x11;
    pr_take(&a);
}

/*
 * The limit of the model. A tie that shares the frame with a local of another size, or a tie of
 * a size other than 1, 2 and 4, does not follow declaration order, and locals that are not part
 * of it change it. M1 and M3 still hold: each size stays together, in order, padded.
 */

/* Three equal aggregates alone: not reversed. */
void pr_tie_three(void)
{
    int a[2];
    int b[2];
    int c[2];

    a[0] = 0x11;
    b[0] = 0x22;
    c[0] = 0x33;
    pr_take(a, b, c);
}

/* The same three with an int after them: another order again. */
void pr_tie_three_int(void)
{
    int a[2];
    int b[2];
    int c[2];
    int d;

    a[0] = 0x11;
    b[0] = 0x22;
    c[0] = 0x33;
    d = 0x44;
    pr_take(a, b, c, &d);
}

/* Two equal arrays and an int: the pair is not reversed. */
void pr_tie_pair(void)
{
    int a[2];
    int b[2];
    int c;

    a[0] = 0x11;
    b[0] = 0x22;
    c = 0x33;
    pr_take(a, b, &c);
}

/* A tie of plain ints breaks too, beside larger locals declared first. */
void pr_tie_small(void)
{
    int d[2];
    int e[2];
    int c;
    int b;
    int a;

    a = 0x11;
    b = 0x22;
    c = 0x33;
    d[0] = 0x44;
    e[0] = 0x55;
    pr_take(&a, &b, &c, d, e);
}

/* A double tied with two arrays. */
void pr_tie_double(void)
{
    double d;
    int a[2];
    int b[2];

    a[0] = 0x11;
    b[0] = 0x22;
    d = 2.5;
    pr_take(a, b, &d);
}

/* Register candidates: eight values live across calls, more than the registers can hold. */
void pr_spill_decl(void)
{
    int a;
    int b;
    int c;
    int d;
    int e;
    int f;
    int g;
    int h;

    a = pr_get();
    b = pr_get();
    c = pr_get();
    d = pr_get();
    e = pr_get();
    f = pr_get();
    g = pr_get();
    h = pr_get();
    pr_put(a, b, c, d);
    pr_put(e, f, g, h);
    pr_put(a, c, e, g);
    pr_put(b, d, f, h);
}

/* Reversed declarations give the same code. */
void pr_spill_decl_rev(void)
{
    int h;
    int g;
    int f;
    int e;
    int d;
    int c;
    int b;
    int a;

    a = pr_get();
    b = pr_get();
    c = pr_get();
    d = pr_get();
    e = pr_get();
    f = pr_get();
    g = pr_get();
    h = pr_get();
    pr_put(a, b, c, d);
    pr_put(e, f, g, h);
    pr_put(a, c, e, g);
    pr_put(b, d, f, h);
}

/* Declaring them in a block gives the same code too. */
void pr_spill_scoped(void)
{
    int a;
    int b;
    int c;
    int d;

    a = pr_get();
    b = pr_get();
    c = pr_get();
    d = pr_get();
    {
        int e;
        int f;
        int g;
        int h;

        e = pr_get();
        f = pr_get();
        g = pr_get();
        h = pr_get();
        pr_put(a, b, c, d);
        pr_put(e, f, g, h);
        pr_put(a, c, e, g);
        pr_put(b, d, f, h);
    }
}

/* Assignment order moves them: pr_spill_decl with the assignments reversed. */
void pr_spill_assign(void)
{
    int a;
    int b;
    int c;
    int d;
    int e;
    int f;
    int g;
    int h;

    h = pr_get();
    g = pr_get();
    f = pr_get();
    e = pr_get();
    d = pr_get();
    c = pr_get();
    b = pr_get();
    a = pr_get();
    pr_put(a, b, c, d);
    pr_put(e, f, g, h);
    pr_put(a, c, e, g);
    pr_put(b, d, f, h);
}

/* Use order moves them: pr_spill_decl with the calls in another order. */
void pr_spill_use(void)
{
    int a;
    int b;
    int c;
    int d;
    int e;
    int f;
    int g;
    int h;

    a = pr_get();
    b = pr_get();
    c = pr_get();
    d = pr_get();
    e = pr_get();
    f = pr_get();
    g = pr_get();
    h = pr_get();
    pr_put(b, d, f, h);
    pr_put(a, c, e, g);
    pr_put(e, f, g, h);
    pr_put(a, b, c, d);
}

/* Type moves them: pr_spill_decl with two of the locals short. */
void pr_spill_type(void)
{
    int a;
    short b;
    int c;
    short d;
    int e;
    int f;
    int g;
    int h;

    a = pr_get();
    b = pr_get();
    c = pr_get();
    d = pr_get();
    e = pr_get();
    f = pr_get();
    g = pr_get();
    h = pr_get();
    pr_put(a, b, c, d);
    pr_put(e, f, g, h);
    pr_put(a, c, e, g);
    pr_put(b, d, f, h);
}

/* Loop weight moves them: a and b work in the loop here, g and h in the twin. */
void pr_spill_loop(int n)
{
    int a;
    int b;
    int c;
    int d;
    int e;
    int f;
    int g;
    int h;
    int i;

    a = pr_get();
    b = pr_get();
    c = pr_get();
    d = pr_get();
    e = pr_get();
    f = pr_get();
    g = pr_get();
    h = pr_get();
    for (i = 0; i < n; i++) {
        a += i;
        b += a;
    }
    pr_put(a, b, c, d);
    pr_put(e, f, g, h);
}

void pr_spill_loop_late(int n)
{
    int a;
    int b;
    int c;
    int d;
    int e;
    int f;
    int g;
    int h;
    int i;

    a = pr_get();
    b = pr_get();
    c = pr_get();
    d = pr_get();
    e = pr_get();
    f = pr_get();
    g = pr_get();
    h = pr_get();
    for (i = 0; i < n; i++) {
        g += i;
        h += g;
    }
    pr_put(a, b, c, d);
    pr_put(e, f, g, h);
}

/* Spills sit above the memory locals: m and q keep their offsets from 0. */
void pr_spill_memory(void)
{
    int a;
    int b;
    int c;
    int d;
    int e;
    int f;
    int g;
    int h;
    int m;
    int q[3];

    m = 0x711;
    q[0] = 0x722;
    a = pr_get();
    b = pr_get();
    c = pr_get();
    d = pr_get();
    e = pr_get();
    f = pr_get();
    g = pr_get();
    h = pr_get();
    pr_take(&m, q);
    pr_put(a, b, c, d);
    pr_put(e, f, g, h);
    pr_put(a, c, e, g);
    pr_put(b, d, f, h);
}
