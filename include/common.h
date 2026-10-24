/*
 * common.h -- included first by every src/<exe>/<unit>.c.
 *
 * Watcom C 10.x is a C89 compiler, so this header is C89 too: block comments only (no line
 * comments), declarations only, no C99 types or keywords. The rules for matched code are in
 * .claude/rules/src.md and docs/coding-style.md. `reverseapoc cc` puts this directory first
 * in its -i= list, ahead of the selected Watcom version's own H directory.
 */
#ifndef COMMON_H
#define COMMON_H

/*
 * INCLUDE_ASM(func_XXXXXXXX); marks a function of the unit that is not matched yet (D-12).
 * It declares an extern int that nothing uses: Watcom emits no EXTDEF, no public and no code
 * or data bytes for it, so the marker reserves nothing in the object. The original bytes of
 * the function stay in the rebuilt EXE because the in-place splice only replaces functions
 * the unit defines in C. A marker is never a substitute for matched code.
 */
#define INCLUDE_ASM(name) extern int INCLUDE_ASM_##name

/* Fixed-width integers. wcc386 (flat 32-bit) has 8-bit char, 16-bit short, 32-bit long. */
typedef signed char s8;
typedef unsigned char u8;
typedef signed short s16;
typedef unsigned short u16;
typedef signed long s32;
typedef unsigned long u32;

#endif /* COMMON_H */
