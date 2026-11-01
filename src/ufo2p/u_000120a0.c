/*
 * src/ufo2p/u_000120a0.c: translation unit u_000120a0 of UFO2P.EXE, 0x000120A0..0x000126F0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000120a0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000120A0);
INCLUDE_ASM(func_000120D0);
INCLUDE_ASM(func_00012220);
INCLUDE_ASM(func_00012310);
INCLUDE_ASM(func_00012350);

/* debug_log_printf: debug log printf, compiled out
 * The target is a lone `ret`: the body was removed from the release build. Callers push a
 * format string and its values and pop them afterwards (a caller-cleaned varargs call), so
 * the original was printf-shaped. Kept as (void): an empty body emits the same `ret`, and
 * the prototype is left for a session that can prove it. void, since EAX is not set.
 * Address: UFO2P.EXE 0x000126E0
 * Evidence: call: 0x000120D0 pushes D_000D00F0 and one value, calls it, then add esp, 8
 * Evidence: call: 0x000120D0 also pushes D_000D0164 and two words, then add esp, 0xc
 * Evidence: call: 18 callers, main among them; it has no callees and no body
 */
void debug_log_printf(void)
{
}
