"""Test-only builder of tiny synthetic OMF objects and libraries; every literal is made up here,
so the reader is checked against the format, not against its own constants.

A record is a u8 type, a u16 length that counts the body and the checksum byte, the body, then a
checksum that makes the bytes of the record sum to 0 mod 256 (TIS OMF 1.1). Library padding and
the dictionary area are filled with 0xA5 where the reader must not look at them.
"""

from __future__ import annotations

import struct

GARBAGE = 0xA5


def record(kind: int, body: bytes) -> bytes:
    """One record with its length and a checksum that zeroes the byte sum."""
    head = bytes([kind]) + struct.pack("<H", len(body) + 1) + body
    return head + bytes([-sum(head) & 0xFF])


def index(n: int) -> bytes:
    """An OMF index: one byte below 0x80, else two bytes with the high bit set on the first."""
    if n < 0x80:
        return bytes([n])
    return bytes([0x80 | (n >> 8), n & 0xFF])


def name(text: str) -> bytes:
    """A counted string: u8 length, then the characters."""
    raw = text.encode("latin-1")
    return bytes([len(raw)]) + raw


def theadr(module_name: str) -> bytes:
    return record(0x80, name(module_name))


def lnames(*names: str) -> bytes:
    return record(0x96, b"".join(name(n) for n in names))


def segdef32(name_idx: int, class_idx: int, length: int, *, attr: int = 0x69) -> bytes:
    """32-bit SEGDEF. attr 0x69: alignment 3 (para), combine 2 (public), use32 bit set.

    The overlay index points at LNAMES entry 1, which the tests keep as the empty name.
    """
    body = bytes([attr]) + struct.pack("<I", length) + index(name_idx) + index(class_idx)
    return record(0x99, body + index(1))


def pubdef32(seg: int, entries: list[tuple[str, int]], *, group: int = 0) -> bytes:
    body = index(group) + index(seg)
    for public, offset in entries:
        body += name(public) + struct.pack("<I", offset) + index(0)  # type index 0
    return record(0x91, body)


def extdef(*names: str) -> bytes:
    return record(0x8C, b"".join(name(n) + index(0) for n in names))


def ledata32(seg: int, offset: int, data: bytes) -> bytes:
    return record(0xA1, index(seg) + struct.pack("<I", offset) + data)


def modend32() -> bytes:
    return record(0x8B, b"\x00")  # module type: not a main module, no start address


def module(module_name: str, *records: bytes) -> bytes:
    """THEADR, the given records, MODEND32."""
    return theadr(module_name) + b"".join(records) + modend32()


def library(modules: list[bytes], *, page_size: int = 16) -> bytes:
    """A LIB: 0xF0 header one page long, page-aligned modules, the 0xF1 end record, and an empty
    dictionary right after it."""
    body = bytearray()
    for mod in modules:
        body += mod + bytes(-len(mod) % page_size)
    end = record(0xF1, b"")
    dictionary_offset = page_size + len(body) + len(end)
    fields = struct.pack("<IHB", dictionary_offset, 0, 0)  # offset, blocks, flags
    header = record(0xF0, fields + bytes(page_size - 4 - len(fields)))
    assert len(header) == page_size
    return header + bytes(body) + end
