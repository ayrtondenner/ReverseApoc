"""The one atomic file writer of the package (DI-18, D-41).

Every generated or committed file the tools write (rebuilt EXEs, listings, CSVs, stamps, status
tables) goes through `write_atomic`. The target is either replaced whole by os.replace or left as
it was, never half-written, and a link at the target is replaced rather than written through.
Nothing is fsynced, so this is not a durability guarantee across a power loss, and a process
killed mid-write can leave its `.<name>.<hex>.tmp` file next to the target.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path


def write_atomic(path: Path, data: bytes) -> None:
    """Write `data` to a temporary file next to `path`, then swap it in with os.replace: a write
    that fails leaves the previous `path` as it was and no temporary file behind, and a link at
    `path` is replaced, never written through (WR-03). Each call writes a temporary file of its
    own, so parallel writers of one path (ninja -j) never publish each other's partial data."""
    # A random name opened exclusively: never an existing file, a link or another writer's file.
    # Not tempfile.mkstemp, whose 0600 mode would differ from a plain write's umask-based mode.
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    fh = tmp.open("xb")
    try:
        with fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
