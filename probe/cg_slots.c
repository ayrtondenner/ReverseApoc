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
extern double pr_getd(void);
extern void pr_putd(double a);
extern void pr_putf(float a);

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

/* Ties of one small size, in a frame of that size alone: scalars beside arrays. */
void pr_slot_bytes(void)
{
    char a;
    char b[1];
    char c;

    a = 0x11;
    b[0] = 0x22;
    c = 0x33;
    pr_take(&a, b, &c);
}

void pr_slot_bytes_rev(void)
{
    char c;
    char b[1];
    char a;

    a = 0x11;
    b[0] = 0x22;
    c = 0x33;
    pr_take(&a, b, &c);
}

void pr_slot_shorts(void)
{
    short a;
    short b[1];
    short c;

    a = 0x11;
    b[0] = 0x22;
    c = 0x33;
    pr_take(&a, b, &c);
}

void pr_slot_shorts_rev(void)
{
    short c;
    short b[1];
    short a;

    a = 0x11;
    b[0] = 0x22;
    c = 0x33;
    pr_take(&a, b, &c);
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

/* A volatile sits in the frame like a memory local, with no address taken: M2 places it. */
void pr_slot_volatile(void)
{
    int a;
    volatile int v;
    int b;

    a = 0x11;
    v = 0x22;
    b = 0x33;
    pr_take(&a, &b);
}

void pr_slot_volatile_rev(void)
{
    int b;
    volatile int v;
    int a;

    a = 0x11;
    v = 0x22;
    b = 0x33;
    pr_take(&a, &b);
}

/* The initializer alone gives a volatile its slot. */
void pr_slot_volatile_init(void)
{
    volatile int v = 0x22;
    int a;

    a = 0x11;
    pr_take(&a);
}

/* Floats whose address is taken follow M2 like any memory local. */
void pr_slot_float_taken(void)
{
    float a;
    float b;
    float c;

    a = 1.5f;
    b = 2.5f;
    c = 3.5f;
    pr_take(&a, &b, &c);
}

/* With no tie a float or a double live across a call sort by size: M1. */
void pr_slot_float_array(void)
{
    float f;
    int v[2];

    v[0] = 0x11;
    f = 1.5f;
    if (pr_get()) {
        f = 2.5f;
    }
    pr_take(v);
    pr_putf(f);
}

void pr_slot_double_int(void)
{
    int a;
    double d;

    a = 0x11;
    d = 2.5;
    if (pr_get()) {
        d = 3.5;
    }
    pr_take(&a);
    pr_putd(d);
}

/* In a tie a float with no address taken leaves M2, though the twins show declarations move it. */
void pr_float_ints(void)
{
    int a;
    int b;
    float f;

    a = 0x11;
    b = 0x22;
    f = 1.5f;
    if (pr_get()) {
        f = 2.5f;
    }
    pr_take(&a, &b);
    pr_putf(f);
}

void pr_float_tie(void)
{
    float a;
    float b;
    float c;

    a = 1.5f;
    b = 2.5f;
    c = 3.5f;
    if (pr_get()) {
        a = 4.5f;
        b = 5.5f;
        c = 6.5f;
    }
    pr_putf(a);
    pr_putf(b);
    pr_putf(c);
}

void pr_float_tie_rev(void)
{
    float c;
    float b;
    float a;

    a = 1.5f;
    b = 2.5f;
    c = 3.5f;
    if (pr_get()) {
        a = 4.5f;
        b = 5.5f;
        c = 6.5f;
    }
    pr_putf(a);
    pr_putf(b);
    pr_putf(c);
}

/* One declaration list, two uses of d: a and b swap, so no rule on declarations can place them. */
void pr_double_called(void)
{
    double d;
    int b;
    int a;

    a = 0x11;
    b = 0x22;
    d = pr_getd();
    pr_take(&a, &b);
    pr_putd(d);
}

void pr_double_stored(void)
{
    double d;
    int b;
    int a;

    a = 0x11;
    b = 0x22;
    d = 2.5;
    if (pr_get()) {
        d = 3.5;
    }
    pr_take(&a, &b);
    pr_putd(d);
}

/* Declaration twins for the search on a real slot map: only the order of the locals differs. */
void pr_twin_abc(void)
{
    int a;
    int b;
    int c;

    a = 0x11;
    b = 0x22;
    c = 0x33;
    pr_take(&a, &b, &c);
}

void pr_twin_bca(void)
{
    int b;
    int c;
    int a;

    a = 0x11;
    b = 0x22;
    c = 0x33;
    pr_take(&a, &b, &c);
}

/* The ints swap between these twins, and the double beside them leaves their order unknown. */
void pr_twin_ints_double(void)
{
    int a;
    int b;
    double p;

    a = 0x11;
    b = 0x22;
    p = pr_getd();
    pr_take(&a, &b);
    pr_putd(p);
}

void pr_twin_double_ints(void)
{
    double p;
    int a;
    int b;

    a = 0x11;
    b = 0x22;
    p = pr_getd();
    pr_take(&a, &b);
    pr_putd(p);
}

/* Twins whose bodies differ in c, so the slot map cannot place it. */
void pr_thin_ours(void)
{
    int a;
    int b;
    int c;

    a = 0x11;
    b = 0x22;
    c = 0x33;
    pr_take(&a, &b);
    pr_put((int)&c, 2, 3, 4);
}

void pr_thin_theirs(void)
{
    int b;
    int c;
    int a;

    c = pr_get();
    a = 0x11;
    b = 0x22;
    pr_take(&a, &b);
    pr_put(1, (int)&c, 3, 4);
}

/*
 * The limit of the model. A tie beside a local of another size, a tie of a size other than 1, 2
 * and 4, or a tie of chars or shorts across blocks does not follow declaration order, and locals
 * that are not part of it change it. M1 and M3 still hold: each size stays together, in order,
 * padded.
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

/* Two ints and two shorts: the ints reverse, the shorts do not. */
void pr_tie_sizes(void)
{
    int a;
    int b;
    short c;
    short d;

    a = 0x11;
    b = 0x22;
    c = 0x33;
    d = 0x44;
    pr_take(&a, &b, &c, &d);
}

/* Ints and shorts across blocks: every int stays below every short, whose order breaks. */
void pr_tie_scope_sizes(int x)
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

/* Shorts across blocks alone: only ints follow the blocks. */
void pr_tie_scope_shorts(int x)
{
    short a;

    a = 0x11;
    if (x) {
        short b;

        b = 0x22;
        if (x > 1) {
            short c;

            c = 0x33;
            pr_take(&a, &b, &c);
        }
    }
}

/*
 * Arrays of one total size, alone or beside scalars. Three or more multi-element arrays leave
 * M2 even alone in a frame of one size; beside other locals no count draws the line. Each
 * function has markers of its own, and a _rev twin shares its base's, so each shape keeps its
 * own last store.
 */

/* Three char[4]: the middle one sits highest. */
void pr_arr_char4_x3(void)
{
    char a[4];
    char b[4];
    char c[4];

    a[0] = 0x12;
    b[0] = 0x13;
    c[0] = 0x14;
    pr_take(a, b, c);
}

/* Its twin, declared backwards. */
void pr_arr_char4_x3_rev(void)
{
    char c[4];
    char b[4];
    char a[4];

    a[0] = 0x12;
    b[0] = 0x13;
    c[0] = 0x14;
    pr_take(a, b, c);
}

/* Four char[4]. */
void pr_arr_char4_x4(void)
{
    char a[4];
    char b[4];
    char c[4];
    char d[4];

    a[0] = 0x15;
    b[0] = 0x16;
    c[0] = 0x17;
    d[0] = 0x18;
    pr_take(a, b, c, d);
}

/* Three unsigned char[4]. */
void pr_arr_uchar4_x3(void)
{
    unsigned char a[4];
    unsigned char b[4];
    unsigned char c[4];

    a[0] = 0x19;
    b[0] = 0x1a;
    c[0] = 0x1b;
    pr_take(a, b, c);
}

/* Three short[2]. */
void pr_arr_short2_x3(void)
{
    short a[2];
    short b[2];
    short c[2];

    a[0] = 0x1c;
    b[0] = 0x1d;
    c[0] = 0x1e;
    pr_take(a, b, c);
}

/* Three char[2]: another order again. */
void pr_arr_char2_x3(void)
{
    char a[2];
    char b[2];
    char c[2];

    a[0] = 0x1f;
    b[0] = 0x20;
    c[0] = 0x21;
    pr_take(a, b, c);
}

/* Two char[4] keep the rule. */
void pr_arr_char4_x2(void)
{
    char a[4];
    char b[4];

    a[0] = 0x23;
    b[0] = 0x24;
    pr_take(a, b);
}

/* One char[4] beside two ints. */
void pr_arr_one_int(void)
{
    char a[4];
    int b;
    int c;

    a[0] = 0x25;
    b = 0x26;
    c = 0x27;
    pr_take(a, &b, &c);
}

/* The same with int[1]: one element is no array. */
void pr_arr_one_int1(void)
{
    char a[4];
    int b[1];
    int c[1];

    a[0] = 0x28;
    b[0] = 0x29;
    c[0] = 0x2a;
    pr_take(a, b, c);
}

/* Two char[4] beside an int. */
void pr_arr_two_int(void)
{
    char a[4];
    char b[4];
    int c;

    a[0] = 0x2b;
    b[0] = 0x2c;
    c = 0x2d;
    pr_take(a, b, &c);
}

/* The same with int[1]. */
void pr_arr_two_int1(void)
{
    char a[4];
    char b[4];
    int c[1];

    a[0] = 0x2e;
    b[0] = 0x2f;
    c[0] = 0x30;
    pr_take(a, b, c);
}

/* Two short[2]. */
void pr_arr_short2_x2(void)
{
    short a[2];
    short b[2];

    a[0] = 0x31;
    b[0] = 0x32;
    pr_take(a, b);
}

/* Two char[2]. */
void pr_arr_char2_x2(void)
{
    char a[2];
    char b[2];

    a[0] = 0x34;
    b[0] = 0x35;
    pr_take(a, b);
}

/* One short[2] beside two ints. */
void pr_arr_short2_int(void)
{
    short a[2];
    int b;
    int c;

    a[0] = 0x36;
    b = 0x37;
    c = 0x38;
    pr_take(a, &b, &c);
}

/* One char[4] beside one int. */
void pr_arr_one_one(void)
{
    char a[4];
    int b;

    a[0] = 0x39;
    b = 0x3a;
    pr_take(a, &b);
}

/* The boundary: two char[4] beside two ints. */
void pr_arr_two_two(void)
{
    char a[4];
    char b[4];
    int c;
    int d;

    a[0] = 0x3b;
    b[0] = 0x3c;
    c = 0x3d;
    d = 0x3e;
    pr_take(a, b, &c, &d);
}

/* Its twin, declared backwards. */
void pr_arr_two_two_rev(void)
{
    int d;
    int c;
    char b[4];
    char a[4];

    a[0] = 0x3b;
    b[0] = 0x3c;
    c = 0x3d;
    d = 0x3e;
    pr_take(a, b, &c, &d);
}

/* The boundary: one char[4] beside three ints. */
void pr_arr_one_three(void)
{
    char a[4];
    int b;
    int c;
    int d;

    a[0] = 0x3f;
    b = 0x40;
    c = 0x41;
    d = 0x42;
    pr_take(a, &b, &c, &d);
}

/* Its twin, declared backwards. */
void pr_arr_one_three_rev(void)
{
    int d;
    int c;
    int b;
    char a[4];

    a[0] = 0x3f;
    b = 0x40;
    c = 0x41;
    d = 0x42;
    pr_take(a, &b, &c, &d);
}

/* The boundary at size 2: two char[2] beside two shorts. */
void pr_arr_two_two_small(void)
{
    char a[2];
    char b[2];
    short c;
    short d;

    a[0] = 0x43;
    b[0] = 0x45;
    c = 0x46;
    d = 0x47;
    pr_take(a, b, &c, &d);
}

/* The boundary at size 2: one char[2] beside three shorts. */
void pr_arr_one_three_small(void)
{
    char a[2];
    short b;
    short c;
    short d;

    a[0] = 0x48;
    b = 0x49;
    c = 0x4a;
    d = 0x4b;
    pr_take(a, &b, &c, &d);
}

/*
 * The plan review's frames: size 2 beside plain locals, two arrays beside a later block, and
 * three arrays beside an int. The compiler's line runs through none of them by count, so the
 * model refuses these. Some leave declaration order and some hold.
 */

/* Two char[2] beside a short: a frame of three breaks where a frame of four held. */
void pr_arr_two_one_small(void)
{
    char a[2];
    char b[2];
    short c;

    a[0] = 0x4c;
    b[0] = 0x4d;
    c = 0x4e;
    pr_take(a, b, &c);
}

/* Its twin, declared backwards. */
void pr_arr_two_one_small_rev(void)
{
    short c;
    char b[2];
    char a[2];

    a[0] = 0x4c;
    b[0] = 0x4d;
    c = 0x4e;
    pr_take(a, b, &c);
}

/* One char[2] after two shorts: a single array is enough at this size. */
void pr_arr_one_two_small(void)
{
    short a;
    short b;
    char c[2];

    a = 0x4f;
    b = 0x50;
    c[0] = 0x51;
    pr_take(&a, &b, c);
}

/* Two char[4] beside a later block: M4 holds for ints, and this leaves it. */
void pr_arr_two_block(int x)
{
    char a[4];
    char b[4];

    a[0] = 0x52;
    b[0] = 0x53;
    pr_take(a, b);
    if (x) {
        int c;

        c = 0x54;
        pr_take(&c);
    }
}

/* Its twin, with the two arrays swapped. */
void pr_arr_two_block_rev(int x)
{
    char b[4];
    char a[4];

    a[0] = 0x52;
    b[0] = 0x53;
    pr_take(a, b);
    if (x) {
        int c;

        c = 0x54;
        pr_take(&c);
    }
}

/* The same with short[2]. */
void pr_arr_short2_block(int x)
{
    short a[2];
    short b[2];

    a[0] = 0x56;
    b[0] = 0x57;
    pr_take(a, b);
    if (x) {
        int c;

        c = 0x58;
        pr_take(&c);
    }
}

/* An int before the two arrays, and a later block. */
void pr_arr_int_two_block(int x)
{
    int a;
    char b[4];
    char c[4];

    a = 0x59;
    b[0] = 0x5a;
    c[0] = 0x5b;
    pr_take(&a, b, c);
    if (x) {
        int d;

        d = 0x5c;
        pr_take(&d);
    }
}

/* An int before three char[4]: it leaves declaration order. */
void pr_arr_int_three(void)
{
    int a;
    char b[4];
    char c[4];
    char d[4];

    a = 0x5d;
    b[0] = 0x5e;
    c[0] = 0x5f;
    d[0] = 0x60;
    pr_take(&a, b, c, d);
}

/* Three char[4] before an int: it holds, and the model refuses it all the same. */
void pr_arr_three_int(void)
{
    char a[4];
    char b[4];
    char c[4];
    int d;

    a[0] = 0x61;
    b[0] = 0x62;
    c[0] = 0x63;
    d = 0x64;
    pr_take(a, b, c, &d);
}

/* Two char[4] beside a block of two ints: it holds, and the model refuses it all the same. */
void pr_arr_two_two_block(int x)
{
    char a[4];
    char b[4];

    a[0] = 0x65;
    b[0] = 0x67;
    pr_take(a, b);
    if (x) {
        int c;
        int d;

        c = 0x68;
        d = 0x69;
        pr_take(&c, &d);
    }
}

/* One char[4] beside a later block: one array keeps M4. */
void pr_arr_one_block(int x)
{
    char a[4];

    a[0] = 0x6a;
    pr_take(a);
    if (x) {
        int b;

        b = 0x6b;
        pr_take(&b);
    }
}

/* Three int[1], the lifter's form for a 4-byte address-taken slot (07.2-14): one element is no
 * array, so M2 holds where three char[4] leave it. */
void pr_arr_int1_x3(void)
{
    int a[1];
    int b[1];
    int c[1];

    a[0] = 0x6c;
    b[0] = 0x6d;
    c[0] = 0x6e;
    pr_take(a, b, c);
}

/* Its twin, declared backwards. */
void pr_arr_int1_x3_rev(void)
{
    int c[1];
    int b[1];
    int a[1];

    a[0] = 0x6c;
    b[0] = 0x6d;
    c[0] = 0x6e;
    pr_take(a, b, c);
}

/*
 * A char[4] beside other multi-element shapes (07.2-14), frames the 07.1 sweep did not reach:
 * beside a short[2], beside a char[2] and an int, and two of them beside a short[2]. Each with a
 * _rev twin that shares its markers.
 */
void pr_arr_c4_s2(void)
{
    char a[4];
    short b[2];

    a[0] = 0x6f;
    b[0] = 0x70;
    pr_take(a, b);
}

void pr_arr_c4_s2_rev(void)
{
    short b[2];
    char a[4];

    a[0] = 0x6f;
    b[0] = 0x70;
    pr_take(a, b);
}

void pr_arr_c4_c2_int(void)
{
    char a[4];
    char b[2];
    int c;

    a[0] = 0x71;
    b[0] = 0x72;
    c = 0x73;
    pr_take(a, b, &c);
}

void pr_arr_c4_c2_int_rev(void)
{
    int c;
    char b[2];
    char a[4];

    a[0] = 0x71;
    b[0] = 0x72;
    c = 0x73;
    pr_take(a, b, &c);
}

void pr_arr_c4x2_s2(void)
{
    char a[4];
    char b[4];
    short c[2];

    a[0] = 0x74;
    b[0] = 0x75;
    c[0] = 0x76;
    pr_take(a, b, c);
}

void pr_arr_c4x2_s2_rev(void)
{
    short c[2];
    char b[4];
    char a[4];

    a[0] = 0x74;
    b[0] = 0x75;
    c[0] = 0x76;
    pr_take(a, b, c);
}

/*
 * Frames past the 07.1 sweep (quick 261112-fdx). Each tests one of four lines fixed before
 * anything was measured: A, one 2-byte array declared first beside shorts; B, two 4-byte arrays
 * then an int, beside later blocks of ints; C, three or more 4-byte arrays then ints; D, an
 * array and an int beside one 2-byte local. The pr_line_k_ frames check the side the model
 * already calls known. A _late frame stores and passes its top block's locals in reverse, and a
 * _split frame passes its array in a call of its own.
 */
void pr_line_a_c2_h(void)
{
    char a[2];
    short b;

    a[0] = 0x77;
    b = 0x177;
    pr_take(a, &b);
}

void pr_line_a_c2_h8(void)
{
    char a[2];
    short b;
    short c;
    short d;
    short e;
    short f;
    short g;
    short h;
    short i;

    a[0] = 0x78;
    b = 0x178;
    c = 0x179;
    d = 0x17a;
    e = 0x17b;
    f = 0x17c;
    g = 0x17d;
    h = 0x17e;
    i = 0x17f;
    pr_take(a, &b, &c, &d, &e, &f, &g, &h, &i);
}

void pr_line_a_c2_h11(void)
{
    char a[2];
    short b;
    short c;
    short d;
    short e;
    short f;
    short g;
    short h;
    short i;
    short j;
    short k;
    short l;

    a[0] = 0x79;
    b = 0x180;
    c = 0x181;
    d = 0x182;
    e = 0x183;
    f = 0x184;
    g = 0x185;
    h = 0x186;
    i = 0x187;
    j = 0x188;
    k = 0x189;
    l = 0x18a;
    pr_take(a, &b, &c, &d, &e, &f, &g, &h, &i, &j, &k, &l);
}

void pr_line_a_uc2_h3(void)
{
    unsigned char a[2];
    short b;
    short c;
    short d;

    a[0] = 0x7a;
    b = 0x18b;
    c = 0x18c;
    d = 0x18d;
    pr_take(a, &b, &c, &d);
}

void pr_line_a_c2_mixed(void)
{
    char a[2];
    short b;
    short c[1];
    unsigned short d;
    short e[1];

    a[0] = 0x7b;
    b = 0x18e;
    c[0] = 0x18f;
    d = 0x190;
    e[0] = 0x191;
    pr_take(a, &b, c, &d, e);
}

void pr_line_a_c2_h3_late(void)
{
    char a[2];
    short b;
    short c;
    short d;

    d = 0x194;
    c = 0x193;
    b = 0x192;
    a[0] = 0x7c;
    pr_take(&d, &c, &b, a);
}

void pr_line_a_c2_h3_split(void)
{
    char a[2];
    short b;
    short c;
    short d;

    a[0] = 0x7d;
    pr_take(a);
    b = 0x195;
    c = 0x196;
    d = 0x197;
    pr_take(&b, &c, &d);
}

void pr_line_k_c4_s2_i(void)
{
    char a[4];
    short b[2];
    int c;

    a[0] = 0x7e;
    b[0] = 0x198;
    c = 0x199;
    pr_take(a, b, &c);
}

void pr_line_k_c4x2_i10(void)
{
    char a[4];
    char b[4];
    int c;
    int d;
    int e;
    int f;
    int g;
    int h;
    int i;
    int j;
    int k;
    int l;

    a[0] = 0x7f;
    b[0] = 0x80;
    c = 0x19a;
    d = 0x19b;
    e = 0x19c;
    f = 0x19d;
    g = 0x19e;
    h = 0x19f;
    i = 0x1a0;
    j = 0x1a1;
    k = 0x1a2;
    l = 0x1a3;
    pr_take(a, b, &c, &d, &e, &f, &g, &h, &i, &j, &k, &l);
}

void pr_line_k_i_c4_i2_c4_i(void)
{
    int a;
    char b[4];
    int c;
    int d;
    char e[4];
    int f;

    a = 0x1a4;
    b[0] = 0x81;
    c = 0x1a5;
    d = 0x1a6;
    e[0] = 0x82;
    f = 0x1a7;
    pr_take(&a, b, &c, &d, e, &f);
}

void pr_line_k_c4x2_i_late(void)
{
    char a[4];
    char b[4];
    int c;

    c = 0x1a8;
    b[0] = 0x84;
    a[0] = 0x83;
    pr_take(&c, b, a);
}

void pr_line_b_c4x2_i_blk(int x)
{
    char a[4];
    char b[4];
    int c;

    a[0] = 0x85;
    b[0] = 0x86;
    c = 0x1a9;
    pr_take(a, b, &c);
    if (x) {
        int d;

        d = 0x1aa;
        pr_take(&d);
    }
}

void pr_line_b_c4x2_i3_blk(int x)
{
    char a[4];
    char b[4];
    int c;
    int d;
    int e;

    a[0] = 0x87;
    b[0] = 0x88;
    c = 0x1ab;
    d = 0x1ac;
    e = 0x1ad;
    pr_take(a, b, &c, &d, &e);
    if (x) {
        int f;

        f = 0x1ae;
        pr_take(&f);
    }
}

void pr_line_b_c4x2_i_blk5(int x)
{
    char a[4];
    char b[4];
    int c;

    a[0] = 0x89;
    b[0] = 0x8a;
    c = 0x1af;
    pr_take(a, b, &c);
    if (x) {
        int d;
        int e;
        int f;
        int g;
        int h;

        d = 0x1b0;
        e = 0x1b1;
        f = 0x1b2;
        g = 0x1b3;
        h = 0x1b4;
        pr_take(&d, &e, &f, &g, &h);
    }
}

void pr_line_b_c4x2_i_blk_blk(int x)
{
    char a[4];
    char b[4];
    int c;

    a[0] = 0x8b;
    b[0] = 0x8c;
    c = 0x1b5;
    pr_take(a, b, &c);
    if (x) {
        int d;

        d = 0x1b6;
        pr_take(&d);
    }
    if (x > 1) {
        int e;

        e = 0x1b7;
        pr_take(&e);
    }
}

void pr_line_b_c4_s2_i_blk(int x)
{
    char a[4];
    short b[2];
    int c;

    a[0] = 0x8d;
    b[0] = 0x1b8;
    c = 0x1b9;
    pr_take(a, b, &c);
    if (x) {
        int d;

        d = 0x1ba;
        pr_take(&d);
    }
}

void pr_line_b_c4x2_i_blk_late(int x)
{
    char a[4];
    char b[4];
    int c;

    c = 0x1bb;
    b[0] = 0x8f;
    a[0] = 0x8e;
    pr_take(&c, b, a);
    if (x) {
        int d;

        d = 0x1bc;
        pr_take(&d);
    }
}

void pr_line_c_c4x2_s2_i(void)
{
    char a[4];
    char b[4];
    short c[2];
    int d;

    a[0] = 0x90;
    b[0] = 0x91;
    c[0] = 0x1bd;
    d = 0x1be;
    pr_take(a, b, c, &d);
}

void pr_line_c_c4x3_i2(void)
{
    char a[4];
    char b[4];
    char c[4];
    int d;
    int e;

    a[0] = 0x92;
    b[0] = 0x93;
    c[0] = 0x94;
    d = 0x1bf;
    e = 0x1c0;
    pr_take(a, b, c, &d, &e);
}

void pr_line_c_c4x4_i(void)
{
    char a[4];
    char b[4];
    char c[4];
    char d[4];
    int e;

    a[0] = 0x95;
    b[0] = 0x96;
    c[0] = 0x97;
    d[0] = 0x98;
    e = 0x1c1;
    pr_take(a, b, c, d, &e);
}

void pr_line_c_c4x3_i_late(void)
{
    char a[4];
    char b[4];
    char c[4];
    int d;

    d = 0x1c2;
    c[0] = 0x9b;
    b[0] = 0x9a;
    a[0] = 0x99;
    pr_take(&d, c, b, a);
}

void pr_line_d_i2_h(void)
{
    int a;
    int b;
    short c;

    a = 0x1c3;
    b = 0x1c4;
    c = 0x1c5;
    pr_take(&a, &b, &c);
}

void pr_line_d_c4_i_h(void)
{
    char a[4];
    int b;
    short c;

    a[0] = 0x9c;
    b = 0x1c6;
    c = 0x1c7;
    pr_take(a, &b, &c);
}

void pr_line_d_c4_i_c2(void)
{
    char a[4];
    int b;
    char c[2];

    a[0] = 0x9d;
    b = 0x1c8;
    c[0] = 0x9e;
    pr_take(a, &b, c);
}

void pr_line_d_h_i_c4(void)
{
    short a;
    int b;
    char c[4];

    a = 0x1c9;
    b = 0x1ca;
    c[0] = 0x9f;
    pr_take(&a, &b, c);
}

void pr_line_d_i_c4_h(void)
{
    int a;
    char b[4];
    short c;

    a = 0x1cb;
    b[0] = 0xa0;
    c = 0x1cc;
    pr_take(&a, b, &c);
}

void pr_line_d_c4_c2_i_late(void)
{
    char a[4];
    char b[2];
    int c;

    c = 0x1cd;
    b[0] = 0xa2;
    a[0] = 0xa1;
    pr_take(&c, b, a);
}

/*
 * Line D refit (todo slot-model-array-ties, 2026-11-13): 4-byte locals, some of them arrays,
 * beside one local of 1 or 2 bytes, in one block. Each frame changes one thing against a
 * neighbour: where the small local stands, whether it or a 4-byte local after the first is an
 * array, and how many arrays and plain locals there are.
 */
void pr_line_d_c4_h_i(void)
{
    char a[4];
    short b;
    int c;

    a[0] = 0xa3;
    b = 0x1ce;
    c = 0x1cf;
    pr_take(a, &b, &c);
}

void pr_line_d_i_h_c4(void)
{
    int a;
    short b;
    char c[4];

    a = 0x1d0;
    b = 0x1d1;
    c[0] = 0xa4;
    pr_take(&a, &b, c);
}

void pr_line_d_h_c4_i(void)
{
    short a;
    char b[4];
    int c;

    a = 0x1d2;
    b[0] = 0xa5;
    c = 0x1d3;
    pr_take(&a, b, &c);
}

void pr_line_d_c2_c4_i(void)
{
    char a[2];
    char b[4];
    int c;

    a[0] = 0xa6;
    b[0] = 0xa7;
    c = 0x1d4;
    pr_take(a, b, &c);
}

void pr_line_d_c4_h_c4(void)
{
    char a[4];
    short b;
    char c[4];

    a[0] = 0xa8;
    b = 0x1d5;
    c[0] = 0xa9;
    pr_take(a, &b, c);
}

void pr_line_d_i_c4_h_i(void)
{
    int a;
    char b[4];
    short c;
    int d;

    a = 0x1d6;
    b[0] = 0xaa;
    c = 0x1d7;
    d = 0x1d8;
    pr_take(&a, b, &c, &d);
}

void pr_line_d_c4x2_h_i2(void)
{
    char a[4];
    char b[4];
    short c;
    int d;
    int e;

    a[0] = 0xab;
    b[0] = 0xac;
    c = 0x1d9;
    d = 0x1da;
    e = 0x1db;
    pr_take(a, b, &c, &d, &e);
}

void pr_line_d_i_c_c4_i(void)
{
    int a;
    char b;
    char c[4];
    int d;

    a = 0x1dc;
    b = 0xad;
    c[0] = 0xae;
    d = 0x1dd;
    pr_take(&a, &b, c, &d);
}

void pr_line_d_h_c4_i5_c4(void)
{
    short a;
    char b[4];
    int c;
    int d;
    int e;
    int f;
    int g;
    char h[4];

    a = 0x1de;
    b[0] = 0xaf;
    c = 0x1df;
    d = 0x1e0;
    e = 0x1e1;
    f = 0x1e2;
    g = 0x1e3;
    h[0] = 0xb0;
    pr_take(&a, b, &c, &d, &e, &f, &g, h);
}

void pr_line_d_i_c4_c2_i(void)
{
    int a;
    char b[4];
    char c[2];
    int d;

    a = 0x1e4;
    b[0] = 0xb1;
    c[0] = 0xb2;
    d = 0x1e5;
    pr_take(&a, b, c, &d);
}

void pr_line_d_c4_h_i_late(void)
{
    char a[4];
    short b;
    int c;

    c = 0x1e7;
    b = 0x1e6;
    a[0] = 0xb3;
    pr_take(&c, &b, a);
}

void pr_line_d_c4_i2_h(void)
{
    char a[4];
    int b;
    int c;
    short d;

    a[0] = 0xb4;
    b = 0x1e8;
    c = 0x1e9;
    d = 0x1ea;
    pr_take(a, &b, &c, &d);
}

void pr_line_d_c4_i8_h(void)
{
    char a[4];
    int b;
    int c;
    int d;
    int e;
    int f;
    int g;
    int h;
    int i;
    short j;

    a[0] = 0xb5;
    b = 0x1eb;
    c = 0x1ec;
    d = 0x1ed;
    e = 0x1ee;
    f = 0x1ef;
    g = 0x1f0;
    h = 0x1f1;
    i = 0x1f2;
    j = 0x1f3;
    pr_take(a, &b, &c, &d, &e, &f, &g, &h, &i, &j);
}

void pr_line_d_s2_i_c(void)
{
    short a[2];
    int b;
    char c;

    a[0] = 0x1f4;
    b = 0x1f5;
    c = 0xb6;
    pr_take(a, &b, &c);
}

void pr_line_d_i6_h(void)
{
    int a;
    int b;
    int c;
    int d;
    int e;
    int f;
    short g;

    a = 0x1f6;
    b = 0x1f7;
    c = 0x1f8;
    d = 0x1f9;
    e = 0x1fa;
    f = 0x1fb;
    g = 0x1fc;
    pr_take(&a, &b, &c, &d, &e, &f, &g);
}

void pr_line_d_c4_i_h_late(void)
{
    char a[4];
    int b;
    short c;

    c = 0x1fe;
    b = 0x1fd;
    a[0] = 0xb7;
    pr_take(&c, &b, a);
}

void pr_line_d_c4x2_h(void)
{
    char a[4];
    char b[4];
    short c;

    a[0] = 0xb8;
    b[0] = 0xb9;
    c = 0x1ff;
    pr_take(a, b, &c);
}

void pr_line_d_c4x2_i2_h(void)
{
    char a[4];
    char b[4];
    int c;
    int d;
    short e;

    a[0] = 0xba;
    b[0] = 0xbb;
    c = 0x200;
    d = 0x201;
    e = 0x202;
    pr_take(a, b, &c, &d, &e);
}

void pr_line_d_i2_c2(void)
{
    int a;
    int b;
    char c[2];

    a = 0x203;
    b = 0x204;
    c[0] = 0xbc;
    pr_take(&a, &b, c);
}

void pr_line_d_i_c4_c(void)
{
    int a;
    char b[4];
    char c;

    a = 0x205;
    b[0] = 0xbd;
    c = 0xbe;
    pr_take(&a, b, &c);
}

void pr_line_d_c4x2_c2_i(void)
{
    char a[4];
    char b[4];
    char c[2];
    int d;

    a[0] = 0xbf;
    b[0] = 0xc0;
    c[0] = 0xc1;
    d = 0x206;
    pr_take(a, b, c, &d);
}

void pr_line_d_c4_h_c4x2(void)
{
    char a[4];
    short b;
    char c[4];
    char d[4];

    a[0] = 0xc2;
    b = 0x207;
    c[0] = 0xc3;
    d[0] = 0xc4;
    pr_take(a, &b, c, d);
}

void pr_line_d_c4_h_i_h(void)
{
    char a[4];
    short b;
    int c;
    short d;

    a[0] = 0xc5;
    b = 0x208;
    c = 0x209;
    d = 0x20a;
    pr_take(a, &b, &c, &d);
}

void pr_line_d_c4x2_i_h(void)
{
    char a[4];
    char b[4];
    int c;
    short d;

    a[0] = 0xc6;
    b[0] = 0xc7;
    c = 0x20b;
    d = 0x20c;
    pr_take(a, b, &c, &d);
}

void pr_line_d_h_c4x3(void)
{
    short a;
    char b[4];
    char c[4];
    char d[4];

    a = 0x20d;
    b[0] = 0xc8;
    c[0] = 0xc9;
    d[0] = 0xca;
    pr_take(&a, b, c, d);
}

void pr_line_d_c4x3_h(void)
{
    char a[4];
    char b[4];
    char c[4];
    short d;

    a[0] = 0xcb;
    b[0] = 0xcc;
    c[0] = 0xcd;
    d = 0x20e;
    pr_take(a, b, c, &d);
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

/* Spills sort by size with the memory locals: m and q sit below them, from 0. */
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

/* Shorts sit above the int spills, at the top of the frame. */
void pr_spill_small(void)
{
    int a;
    int b;
    int c;
    int d;
    int e;
    int f;
    int g;
    int h;
    short m;
    short n;

    m = 0x711;
    n = 0x722;
    a = pr_get();
    b = pr_get();
    c = pr_get();
    d = pr_get();
    e = pr_get();
    f = pr_get();
    g = pr_get();
    h = pr_get();
    pr_take(&m, &n);
    pr_put(a, b, c, d);
    pr_put(e, f, g, h);
    pr_put(a, c, e, g);
    pr_put(b, d, f, h);
}

/* The one case where declaration moves a register candidate: shorts spilled beside a short in
   memory. Under -oneatx these two differ, and every other pair of this file with declarations
   alone changed gives the same code. */
void pr_spill_short(void)
{
    short q;
    short a;
    short b;
    short c;
    short d;
    int e;
    int f;
    int g;
    int h;

    q = 0x711;
    a = pr_get();
    b = pr_get();
    c = pr_get();
    d = pr_get();
    e = pr_get();
    f = pr_get();
    g = pr_get();
    h = pr_get();
    pr_take(&q);
    pr_put(a, b, c, d);
    pr_put(e, f, g, h);
    pr_put(a, c, e, g);
    pr_put(b, d, f, h);
}

void pr_spill_short_rev(void)
{
    short q;
    int h;
    int g;
    int f;
    int e;
    short d;
    short c;
    short b;
    short a;

    q = 0x711;
    a = pr_get();
    b = pr_get();
    c = pr_get();
    d = pr_get();
    e = pr_get();
    f = pr_get();
    g = pr_get();
    h = pr_get();
    pr_take(&q);
    pr_put(a, b, c, d);
    pr_put(e, f, g, h);
    pr_put(a, c, e, g);
    pr_put(b, d, f, h);
}
