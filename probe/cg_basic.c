/*
 * cg_basic.c: codegen probe for compiler identification (Phase 4, CID-03).
 *
 * Clean-room C89 written for ReverseApoc. The constructs were chosen from mosura's documented
 * list (byte compare return, counted loop, switch order) plus the constructs the flag scans
 * need (struct copy, constant division, floating point, calls). No third-party code is copied
 * here: mosura's licence is unverified, so only its list of constructs was used.
 *
 * Each function is compiled with every swept Watcom version and flag set by
 * tools/reverseapoc/probe.py, which counts the idioms in the objects. See probe/README.md.
 */

/* Byte compare returned as int: setcc al, then "and eax,0FFh" or "movzx eax,al" or a branch. */
int pr_eq5(unsigned char c)
{
    return c == 5;
}

/* Counted loop: rotated (jump to a bottom test) or top-tested (exit test, jump back). */
int pr_sum(int *a, int n)
{
    int i;
    int s;

    s = 0;
    for (i = 0; i < n; i++) {
        s += a[i];
    }
    return s;
}

/* Sparse switch: the order of the compares against 1, 2, 3 and 10. */
int pr_switch(int x)
{
    switch (x) {
    case 1:
        return 11;
    case 2:
        return 22;
    case 3:
        return 33;
    case 10:
        return 44;
    default:
        return 55;
    }
}

/* Five-dword struct: copied with unrolled movsd or with "mov ecx,5; rep movsd". */
struct pr_s5 {
    long a, b, c, d, e;
};

void pr_copy(struct pr_s5 *dst, struct pr_s5 *src)
{
    *dst = *src;
}

/* Division by a constant: an idiv or a multiply by a reciprocal. */
int pr_div10(int x)
{
    return x / 10;
}

/* Floating point: inline x87 (-fpi, -fpi87) asks for emu387 or noemu387. */
double pr_fexpr(double a, double b, double c)
{
    return a * b + c;
}

/* A function calling others, so a stack-check prologue (__CHK) and calls exist. */
int pr_call(int x)
{
    return pr_div10(x) + pr_eq5((unsigned char)x);
}
