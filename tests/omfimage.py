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


def segdef16(name_idx: int, class_idx: int, length: int, *, attr: int = 0x68) -> bytes:
    """16-bit-numbered SEGDEF with a u16 length. attr 0x68: para, public, use16."""
    body = bytes([attr]) + struct.pack("<H", length) + index(name_idx) + index(class_idx)
    return record(0x98, body + index(1))


def segdef_easy(
    name_idx: int, class_idx: int, length: int, *, attr: int = 0x69, access: int | None = None
) -> bytes:
    """Easy OMF SEGDEF: record 0x98 with a u32 length, optionally one trailing access byte."""
    body = bytes([attr]) + struct.pack("<I", length) + index(name_idx) + index(class_idx)
    body += index(1) + (b"" if access is None else bytes([access]))
    return record(0x98, body)


def pubdef16(
    seg: int, entries: list[tuple[str, int]], *, group: int = 0, offset32: bool = False
) -> bytes:
    """Record 0x90; Easy OMF modules write u32 offsets in it."""
    fmt = "<I" if offset32 else "<H"
    body = index(group) + index(seg)
    for public, offset in entries:
        body += name(public) + struct.pack(fmt, offset) + index(0)
    return record(0x90, body)


def ledata16(seg: int, offset: int, data: bytes, *, offset32: bool = False) -> bytes:
    """Record 0xA0; Easy OMF modules write a u32 offset in it."""
    return record(0xA0, index(seg) + struct.pack("<I" if offset32 else "<H", offset) + data)


def _lidata_block(block: tuple[int, bytes | list], fmt: str) -> bytes:
    """fmt packs (repeat count, block count): "<IH" in LIDATA32, "<HH" in LIDATA."""
    repeat, content = block
    if isinstance(content, bytes):
        return struct.pack(fmt, repeat, 0) + bytes([len(content)]) + content
    nested = b"".join(_lidata_block(b, fmt) for b in content)
    return struct.pack(fmt, repeat, len(content)) + nested


def lidata32(seg: int, offset: int, blocks: list[tuple[int, bytes | list]]) -> bytes:
    """A block is (repeat, content bytes) or (repeat, [nested blocks])."""
    body = index(seg) + struct.pack("<I", offset)
    return record(0xA3, body + b"".join(_lidata_block(b, "<IH") for b in blocks))


def lidata16(
    seg: int, offset: int, blocks: list[tuple[int, bytes | list]], *, offset32: bool = False
) -> bytes:
    """Record 0xA2 with u16 repeat counts; Easy OMF modules write a u32 data offset in it."""
    body = index(seg) + struct.pack("<I" if offset32 else "<H", offset)
    return record(0xA2, body + b"".join(_lidata_block(b, "<HH") for b in blocks))


def fixup(
    locat_offset: int,
    *,
    location: int = 9,
    segment_relative: bool = True,
    frame: tuple = (5, None),
    target: tuple = (0, 1),
    displacement: int | None = None,
    use32: bool = True,
) -> bytes:
    """A FIXUP subrecord. frame/target are (method, index or None) or ("thread", number).

    A target method is given as 0-2; a displacement of None sets the P bit (methods 4-6).
    """
    locat = 0x8000 | (0x4000 if segment_relative else 0) | (location << 10) | locat_offset
    out = struct.pack(">H", locat)
    p_bit = 0 if displacement is not None else 1
    if frame[0] == "thread":
        f_bit, frame_field, frame_datum = 1, frame[1], b""
    else:
        f_bit, frame_field = 0, frame[0]
        frame_datum = b"" if frame[1] is None else index(frame[1])
    if target[0] == "thread":
        t_bit, targt, target_datum = 1, target[1], b""
    else:
        t_bit, targt, target_datum = 0, target[0] & 3, index(target[1])
    out += bytes([f_bit << 7 | frame_field << 4 | t_bit << 3 | p_bit << 2 | targt])
    out += frame_datum + target_datum
    if displacement is not None:
        out += struct.pack("<I" if use32 else "<H", displacement)
    return out


def thread(target_or_frame: str, number: int, method: int, idx: int | None = None) -> bytes:
    """A THREAD subrecord: D bit set for a frame thread, method in bits 2-4, number in 0-1."""
    d_bit = 0x40 if target_or_frame == "frame" else 0
    return bytes([d_bit | method << 2 | number]) + (b"" if idx is None else index(idx))


def fixupp32(*subrecords: bytes) -> bytes:
    return record(0x9D, b"".join(subrecords))


def fixupp16(*subrecords: bytes) -> bytes:
    return record(0x9C, b"".join(subrecords))


def coment(cls: int, payload: bytes, *, flags: int = 0x80) -> bytes:
    return record(0x88, bytes([flags, cls]) + payload)


def grpdef(name_idx: int, *seg_idxs: int) -> bytes:
    return record(0x9A, index(name_idx) + b"".join(b"\xff" + index(s) for s in seg_idxs))


def bakpat32(seg: int, location: int, patches: list[tuple[int, int]]) -> bytes:
    body = index(seg) + bytes([location])
    return record(0xB3, body + b"".join(struct.pack("<II", o, v) for o, v in patches))


def comdef(*entries: tuple[str, int]) -> bytes:
    """COMDEF with NEAR communal variables: (name, length) each, short length form."""
    return record(0xB0, b"".join(name(n) + index(0) + b"\x62" + bytes([size])
                                 for n, size in entries))  # fmt: skip


def lidata_blocks32(blocks: list[tuple[int, bytes | list]]) -> bytes:
    """LIDATA32-style blocks on their own, for an iterated COMDAT32."""
    return b"".join(_lidata_block(b, "<IH") for b in blocks)


def comdat32(
    name_idx: int,
    data: bytes,
    *,
    flags: int = 0,
    attributes: int = 0,
    alignment: int = 1,
    offset: int = 0,
    group: int = 0,
    seg: int = 1,
    frame: int = 0,
) -> bytes:
    """COMDAT32. flags 0x01 continuation, 0x02 iterated data; attributes low nibble 0 means
    explicit allocation, the only case with a public base (group, segment, frame if both 0)."""
    body = bytes([flags, attributes, alignment]) + struct.pack("<I", offset) + index(0)
    if attributes & 0x0F == 0:
        body += index(group) + index(seg)
        if group == 0 and seg == 0:
            body += struct.pack("<H", frame)
    return record(0xC3, body + index(name_idx) + data)


def cextdef(*lname_idxs: int) -> bytes:
    """COMDAT external names: LNAMES indexes, each with type index 0."""
    return record(0xBC, b"".join(index(i) + index(0) for i in lname_idxs))


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
