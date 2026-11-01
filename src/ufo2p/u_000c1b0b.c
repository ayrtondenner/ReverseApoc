/*
 * src/ufo2p/u_000c1b0b.c: translation unit u_000c1b0b of UFO2P.EXE, 0x000C1B0B..0x000C1B2A (D-11).
 *
 * Two small wrappers over the C runtime's ftell and fseek that read and restore a stream
 * position through a pointer, in the shape of fgetpos and fsetpos.
 */
#include "common.h"

int fseek(void *fp, long offset, int whence);
long ftell(void *fp);

/* stream_save_position: save the stream position
 * Stores ftell(stream) in *position; returns nonzero when ftell failed (returned -1).
 * Address: UFO2P.EXE 0x000C1B0B
 * Evidence: call: calls the runtime ftell and stores its result through the second argument
 */
int stream_save_position(void *stream, long *position)
{
    return (*position = ftell(stream)) == -1;
}

/* stream_restore_position: restore a saved stream position
 * Seeks the stream to *position from its start (whence 0, SEEK_SET); returns fseek's result.
 * Address: UFO2P.EXE 0x000C1B1E
 * Evidence: call: calls the runtime fseek with the value read through the second argument and whence 0
 */
int stream_restore_position(void *stream, long *position)
{
    return fseek(stream, *position, 0);
}
