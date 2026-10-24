/*
 * watcom_compat.h -- lets clang read Watcom C sources for the C89 lint gate (D-14).
 *
 * `reverseapoc lint` force-includes this header (`-include include/watcom_compat.h`) into
 * every file it checks with `clang -fsyntax-only -std=gnu89`. It is active only under clang:
 * for wcc386 the whole body is skipped, so including it changes nothing in a Watcom build.
 * It is deliberately not guarded on __WATCOMC__, because the lint command itself defines
 * __WATCOMC__ (with __386__ and __FLAT__) to the version the game was built with.
 *
 * What it does under clang:
 *   - Watcom's calling-convention and pointer keywords become empty, so declarations such as
 *     `int __watcall f(int);` and `void __far __interrupt g(void);` parse.
 *   - Unknown pragmas are not reported, so `#pragma aux ...` is a no-op. A pragma cannot be
 *     redefined as a macro; silencing the warning is the only way.
 *
 * C89 like every header here: block comments only.
 */
#ifndef WATCOM_COMPAT_H
#define WATCOM_COMPAT_H

#ifdef __clang__

#pragma clang diagnostic ignored "-Wunknown-pragmas"

#define __far
#define __near
#define __huge
#define __interrupt
#define __loadds
#define __saveregs
#define __export
#define __pascal
#define __fortran
#define __syscall
#define __watcall
#define __cdecl
#define _far
#define _near
#define _cdecl

#endif /* __clang__ */

#endif /* WATCOM_COMPAT_H */
